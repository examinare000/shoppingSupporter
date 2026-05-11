"""POST /api/auth/signup, POST /api/auth/login, GET /api/auth/me の統合テスト。

Spec: docs/plans/phase1-foundation.md (T-03)
Plan: .takt/runs/20260505-001506-t-03-jwt-docs-plans-phase1-fou/reports/plan.md

レイヤー:
    - 単位仕様（hash/decode 等）は `tests/unit/test_security.py` で担保。
    - 本ファイルは TestClient + Postgres で signup→login→/me の HTTP 契約を
      end-to-end に検証する。

主な契約（plan.md「実装ガイドライン」より）:
    - レスポンスは camelCase（`accessToken` / `tokenType` / `createdAt`）。
    - signup は `id` / `email` / `createdAt` のみ返し、`hashedPassword` 等を
      漏らさない。
    - login 失敗（未登録 email でもパスワード違いでも）は 401 で同一の
      汎用メッセージを返し、内部状態を区別させない。
    - JWT は Authorization: Bearer <token> ヘッダで /me に提示する。

意図的にテストする観点:
    - リクエストは body で送る（body 以外の場所からの読み取りに依存していないか）。
    - レスポンス envelope の形を request 解釈に流用していないか。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from api.common import security as security_module


SIGNUP_ENDPOINT = "/api/auth/signup"
LOGIN_ENDPOINT = "/api/auth/login"
ME_ENDPOINT = "/api/auth/me"


# 既存の `tests/integration/test_product_search.py` の `EXPECTED_*_KEYS`
# パターンに揃え、レスポンス形を一箇所に集約する。
EXPECTED_USER_KEYS = {"id", "email", "createdAt"}
EXPECTED_TOKEN_KEYS = {"accessToken", "tokenType"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signup(client, *, email: str, password: str):
    return client.post(
        SIGNUP_ENDPOINT, json={"email": email, "password": password}
    )


def _login(client, *, email: str, password: str):
    return client.post(
        LOGIN_ENDPOINT, json={"email": email, "password": password}
    )


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------


class TestSignup:
    def test_should_return_201_with_user_envelope_on_success(self, client):
        # Given: 未登録の正常入力
        # When: signup する
        response = _signup(
            client, email="alice@example.com", password="StrongPass1!"
        )

        # Then: 201 Created とユーザー情報が返る
        assert response.status_code == 201
        body = response.json()
        assert set(body.keys()) == EXPECTED_USER_KEYS
        assert body["email"] == "alice@example.com"
        # id は UUID 文字列、createdAt は ISO 形式の文字列
        assert isinstance(body["id"], str)
        assert isinstance(body["createdAt"], str)

    def test_should_not_leak_password_or_hash_in_response(self, client):
        # Given: signup する
        response = _signup(
            client, email="alice@example.com", password="StrongPass1!"
        )

        # Then: パスワード関連のキーが一切露出しない
        assert response.status_code == 201
        body = response.json()
        forbidden_keys = {
            "password",
            "hashed_password",
            "hashedPassword",
        }
        assert forbidden_keys.isdisjoint(body.keys())

    def test_should_persist_user_in_database(self, client, db_session):
        from api.common.models import User

        # When: signup
        response = _signup(
            client, email="alice@example.com", password="StrongPass1!"
        )
        assert response.status_code == 201

        # Then: DB に bcrypt ハッシュ済みのユーザが永続化されている
        user = db_session.query(User).filter_by(email="alice@example.com").one()
        assert user.hashed_password != "StrongPass1!"
        # bcrypt ハッシュは `$2b$` 等のプレフィクスを持つ
        assert user.hashed_password.startswith("$2")

    def test_should_return_409_when_email_is_already_registered(self, client):
        # Given: 既に登録済みのメールアドレス
        first = _signup(
            client, email="alice@example.com", password="StrongPass1!"
        )
        assert first.status_code == 201

        # When: 同じメールで再度 signup
        second = _signup(
            client, email="alice@example.com", password="DifferentPass2!"
        )

        # Then: 409 Conflict（plan.md の「重複 email 409」決定）
        assert second.status_code == 409

    def test_should_return_422_when_email_is_malformed(self, client):
        response = _signup(
            client, email="not-an-email", password="StrongPass1!"
        )
        assert response.status_code == 422

    def test_should_return_422_when_password_is_too_short(self, client):
        # Given: 8 文字未満のパスワード（agent-rules/12: 「最小8文字以上」）
        response = _signup(
            client, email="alice@example.com", password="short"
        )
        assert response.status_code == 422

    def test_should_return_422_when_email_field_missing(self, client):
        response = client.post(
            SIGNUP_ENDPOINT, json={"password": "StrongPass1!"}
        )
        assert response.status_code == 422

    def test_should_return_422_when_password_field_missing(self, client):
        response = client.post(
            SIGNUP_ENDPOINT, json={"email": "alice@example.com"}
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    @pytest.fixture
    def signed_up_user(self, client):
        email = "alice@example.com"
        password = "StrongPass1!"
        response = _signup(client, email=email, password=password)
        assert response.status_code == 201
        return {"email": email, "password": password}

    def test_should_return_200_with_access_token_on_success(
        self, client, signed_up_user
    ):
        # When: 正しいパスワードで login
        response = _login(
            client,
            email=signed_up_user["email"],
            password=signed_up_user["password"],
        )

        # Then: 200 とトークン envelope を返す
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == EXPECTED_TOKEN_KEYS
        assert body["tokenType"] == "bearer"
        assert isinstance(body["accessToken"], str)
        assert body["accessToken"]

    def test_access_token_should_be_decodable_and_carry_user_id(
        self, client, signed_up_user, db_session
    ):
        from api.common.models import User

        response = _login(
            client,
            email=signed_up_user["email"],
            password=signed_up_user["password"],
        )
        assert response.status_code == 200
        token = response.json()["accessToken"]

        # サーバ側のデコード関数で `sub` を取り出すと、対応する User の id と一致する
        payload = security_module.decode_access_token(token)
        user = (
            db_session.query(User)
            .filter_by(email=signed_up_user["email"])
            .one()
        )
        assert payload["sub"] == str(user.id)

    def test_should_return_401_when_password_is_wrong(
        self, client, signed_up_user
    ):
        response = _login(
            client, email=signed_up_user["email"], password="WrongPass1!"
        )
        assert response.status_code == 401

    def test_should_return_401_when_email_is_not_registered(self, client):
        response = _login(
            client, email="ghost@example.com", password="StrongPass1!"
        )
        assert response.status_code == 401

    def test_should_use_identical_message_for_unknown_email_and_wrong_password(
        self, client, signed_up_user
    ):
        # Why: ユーザー存在有無の漏洩防止。401 の本文を区別させない（plan.md）。
        wrong_password = _login(
            client, email=signed_up_user["email"], password="WrongPass1!"
        )
        unknown_email = _login(
            client, email="ghost@example.com", password="StrongPass1!"
        )
        assert wrong_password.status_code == 401
        assert unknown_email.status_code == 401
        assert wrong_password.json() == unknown_email.json()

    def test_should_return_422_when_email_field_missing(self, client):
        response = client.post(
            LOGIN_ENDPOINT, json={"password": "StrongPass1!"}
        )
        assert response.status_code == 422

    def test_should_return_422_when_password_field_missing(self, client):
        response = client.post(
            LOGIN_ENDPOINT, json={"email": "alice@example.com"}
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


class TestMe:
    @pytest.fixture
    def auth_token(self, client):
        email = "alice@example.com"
        password = "StrongPass1!"
        signup_response = _signup(client, email=email, password=password)
        assert signup_response.status_code == 201
        login_response = _login(client, email=email, password=password)
        assert login_response.status_code == 200
        return {
            "token": login_response.json()["accessToken"],
            "email": email,
        }

    def test_should_return_authenticated_user_envelope(self, client, auth_token):
        response = client.get(
            ME_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == EXPECTED_USER_KEYS
        assert body["email"] == auth_token["email"]

    def test_should_not_expose_hashed_password(self, client, auth_token):
        response = client.get(
            ME_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        assert response.status_code == 200
        body = response.json()
        assert "hashedPassword" not in body
        assert "hashed_password" not in body
        assert "password" not in body

    def test_should_return_401_when_authorization_header_missing(self, client):
        response = client.get(ME_ENDPOINT)
        assert response.status_code == 401

    def test_should_return_401_when_authorization_scheme_is_not_bearer(
        self, client, auth_token
    ):
        # Given: `Bearer ` プレフィクスを欠いた値
        response = client.get(
            ME_ENDPOINT,
            headers={"Authorization": auth_token["token"]},
        )
        assert response.status_code == 401

    def test_should_return_401_when_token_is_tampered(self, client, auth_token):
        # Given: 末尾を改ざんしたトークン
        tampered = auth_token["token"] + "x"
        response = client.get(ME_ENDPOINT, headers=_auth_header(tampered))
        assert response.status_code == 401

    def test_should_return_401_when_token_is_expired(self, client, db_session):
        from api.common.models import User

        # Given: 既に登録された User と、過去に exp を持つ自前生成トークン
        # （signup で永続化された User を流用するために、まず signup する）
        signup_response = _signup(
            client, email="alice@example.com", password="StrongPass1!"
        )
        assert signup_response.status_code == 201
        user = (
            db_session.query(User).filter_by(email="alice@example.com").one()
        )
        expired_token = pyjwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
                "iat": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
            # conftest.py で setdefault した値と同期させる。
            "test-jwt-secret-for-integration-only",
            algorithm="HS256",
        )

        # When: 期限切れトークンで /me
        response = client.get(
            ME_ENDPOINT, headers=_auth_header(expired_token)
        )

        # Then: 401（期限切れの取り扱い）
        assert response.status_code == 401

    def test_should_return_401_when_token_signed_with_different_secret(
        self, client, db_session
    ):
        from api.common.models import User

        # Given: 同じ User のトークンを別秘密鍵で署名
        signup_response = _signup(
            client, email="alice@example.com", password="StrongPass1!"
        )
        assert signup_response.status_code == 201
        user = (
            db_session.query(User).filter_by(email="alice@example.com").one()
        )
        foreign_token = pyjwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
                "iat": datetime.now(timezone.utc),
            },
            "totally-different-secret-32-chars-long-min",
            algorithm="HS256",
        )

        # When/Then: 異なる秘密鍵では署名検証に失敗 → 401
        response = client.get(
            ME_ENDPOINT, headers=_auth_header(foreign_token)
        )
        assert response.status_code == 401

    def test_should_return_401_when_user_id_no_longer_exists(
        self, client, db_session, auth_token
    ):
        from api.common.models import User

        # Given: 取得済みの正規トークンに対し、対応する User を削除
        db_session.query(User).filter_by(email=auth_token["email"]).delete()
        db_session.commit()

        # When: 既に存在しない sub を持つトークンで /me
        response = client.get(
            ME_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: 401（認証主体が確定できないため Unauthorized 相当）
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# 一気通貫
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    def test_signup_then_login_then_me_should_succeed(self, client):
        # Given: 新規ユーザー
        email = "alice@example.com"
        password = "StrongPass1!"

        # When/Then: signup で 201
        signup = _signup(client, email=email, password=password)
        assert signup.status_code == 201
        signup_user = signup.json()

        # When/Then: login で 200 + accessToken
        login = _login(client, email=email, password=password)
        assert login.status_code == 200
        token = login.json()["accessToken"]

        # When/Then: /me で signup と同じ user envelope が得られる
        me = client.get(ME_ENDPOINT, headers=_auth_header(token))
        assert me.status_code == 200
        me_user = me.json()
        assert me_user["id"] == signup_user["id"]
        assert me_user["email"] == signup_user["email"]


# ---------------------------------------------------------------------------
# 入力位置の契約
# ---------------------------------------------------------------------------


class TestRequestBodyContract:
    """signup/login の入力は JSON body から読み取る契約を保護する。

    Why:
        実装が誤って query string や response envelope の構造から入力を
        拾うと、外部契約が崩れる。tests/integration/test_product_search.py
        の `TestEndpointQueryStringContract` と対になるテスト。
    """

    def test_signup_should_ignore_query_string_credentials(self, client):
        # Given: body は欠落、credentials は query string に置く
        response = client.post(
            SIGNUP_ENDPOINT,
            params={"email": "alice@example.com", "password": "StrongPass1!"},
        )

        # Then: body が必須なので 422（query は読まない）
        assert response.status_code == 422

    def test_login_should_ignore_query_string_credentials(self, client):
        # Given: 事前に signup された User
        _signup(
            client, email="alice@example.com", password="StrongPass1!"
        )

        # When: credentials を query string で送る
        response = client.post(
            LOGIN_ENDPOINT,
            params={"email": "alice@example.com", "password": "StrongPass1!"},
        )

        # Then: body が必須なので 422
        assert response.status_code == 422

    def test_login_should_not_misread_envelope_shaped_body(self, client):
        # Given: response envelope を真似た body
        envelope_shaped_body = {
            "accessToken": "fake-token",
            "tokenType": "bearer",
        }

        # When: その body で login を呼ぶ
        response = client.post(LOGIN_ENDPOINT, json=envelope_shaped_body)

        # Then: envelope の形は credentials として解釈されず 422
        assert response.status_code == 422
