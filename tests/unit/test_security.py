"""`api.common.security` の単体テスト。

Why:
    - bcrypt と JWT の操作は `api/common/security.py` に集約される（plan.md
      「操作の一覧性」）。本ファイルではその純粋関数（DB 不要）に対する
      Red-Green-Refactor の Red を先行配置する。
    - 統合層（TestClient + Postgres）は `tests/integration/test_auth.py` で
      担保し、ここでは「ハッシュ化」「トークン発行・検証」「fail-fast」
      の単位仕様のみを検証する。

カバーする観点:
    - パスワードハッシュ: 出力 != 入力 / 同入力でもソルト差 / 正パスで
      verify True / 誤パスで verify False。
    - アクセストークン: `sub` クレームに user id 文字列が乗ること /
      `exp` クレームが現在時刻より未来であること / 改ざんトークンで例外 /
      期限切れトークンで例外 / `JWT_SECRET` 未設定で `RuntimeError`。

Why monkeypatch.setenv を使うか:
    `api.common.security._get_jwt_secret()` が遅延参照する想定（plan.md の
    「アプローチ」セクション）。プロセスグローバルの `os.environ` を直接
    書き換えるとテスト間で漏れるため、monkeypatch でテスト境界に閉じ込める。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi import status


# Why: 実装ステップで `api/common/security.py` が新規追加される（plan.md の
# 「変更対象（新規）」）。write_tests の段階では import 失敗で Red になるが、
# テストとしては正しい契約を表現することを優先する。
from api.common import security as security_module


# 既存慣習に揃える定数（plan.md の「実装ガイドライン」）。
# Why: テスト側でアルゴリズム定数を直書きしない。ライブラリ実装側の
# 定数に同期するため、モジュール属性経由で参照する。
JWT_ALGORITHM = "HS256"


@pytest.fixture
def jwt_secret(monkeypatch):
    """テスト用の JWT_SECRET を環境変数に注入する。"""
    secret = "unit-test-jwt-secret"
    monkeypatch.setenv("JWT_SECRET", secret)
    return secret


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    """`hash_password` / `verify_password` の単位仕様。"""

    def test_should_produce_hash_distinct_from_plain_text(self):
        # Given: 任意の平文パスワード
        plain = "correct horse battery staple"

        # When: ハッシュ化する
        hashed = security_module.hash_password(plain)

        # Then: 出力は平文と一致しない
        assert isinstance(hashed, str)
        assert hashed != plain

    def test_should_produce_different_hash_for_same_password_due_to_salt(self):
        # Given: 同一の平文パスワード
        plain = "correct horse battery staple"

        # When: 二回ハッシュ化する
        first = security_module.hash_password(plain)
        second = security_module.hash_password(plain)

        # Then: ソルトが毎回異なるため、ハッシュ値も異なる
        assert first != second

    def test_should_verify_true_for_matching_password(self):
        plain = "correct horse battery staple"
        hashed = security_module.hash_password(plain)

        assert security_module.verify_password(plain, hashed) is True

    def test_should_verify_false_for_mismatched_password(self):
        hashed = security_module.hash_password("correct horse battery staple")

        assert security_module.verify_password("wrong-password", hashed) is False

    def test_should_verify_false_for_empty_password_against_real_hash(self):
        # Given: 実在のパスワードのハッシュ
        hashed = security_module.hash_password("correct horse battery staple")

        # When/Then: 空文字を検証しても True にならない（境界値）
        assert security_module.verify_password("", hashed) is False


# ---------------------------------------------------------------------------
# Access token (issue / decode)
# ---------------------------------------------------------------------------


class TestAccessToken:
    """`create_access_token` / `decode_access_token` の単位仕様。"""

    def test_should_round_trip_user_id_through_sub_claim(self, jwt_secret):
        # Given: 任意のユーザー ID（UUID）
        user_id = uuid.uuid4()

        # When: トークンを発行してデコードする
        token = security_module.create_access_token(user_id)
        payload = security_module.decode_access_token(token)

        # Then: `sub` に user id が文字列として保存されている
        assert payload["sub"] == str(user_id)

    def test_should_set_exp_claim_in_the_future(self, jwt_secret):
        # Given: 任意のユーザー ID
        user_id = uuid.uuid4()
        before = datetime.now(timezone.utc)

        # When: トークンを発行する
        token = security_module.create_access_token(user_id)
        payload = security_module.decode_access_token(token)

        # Then: `exp` クレームが現在時刻より未来である
        assert "exp" in payload
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > before

    def test_should_raise_when_token_signature_is_tampered(self, jwt_secret):
        # Given: 正規発行されたトークン
        token = security_module.create_access_token(uuid.uuid4())

        # When: 末尾の署名部分を改ざん
        tampered = token + "x"

        # Then: デコードで例外
        with pytest.raises(Exception):
            security_module.decode_access_token(tampered)

    def test_should_raise_when_token_signed_with_different_secret(
        self, jwt_secret
    ):
        # Given: 別の秘密鍵で署名された他人のトークン（攻撃者シナリオ）
        foreign_token = pyjwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
            },
            "different-secret",
            algorithm=JWT_ALGORITHM,
        )

        # When/Then: 自分の秘密鍵では検証に失敗する
        with pytest.raises(Exception):
            security_module.decode_access_token(foreign_token)

    def test_should_raise_when_token_is_expired(self, jwt_secret):
        # Given: 既に期限切れのトークンを直接発行（実装側の有効期限を待たずに検証）
        expired_token = pyjwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
                "iat": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
            jwt_secret,
            algorithm=JWT_ALGORITHM,
        )

        # When/Then: デコードで `ExpiredSignatureError` 系の例外
        with pytest.raises(pyjwt.ExpiredSignatureError):
            security_module.decode_access_token(expired_token)

    def test_should_raise_runtime_error_when_jwt_secret_is_missing(
        self, monkeypatch
    ):
        # Given: JWT_SECRET が一切設定されていない
        monkeypatch.delenv("JWT_SECRET", raising=False)

        # When/Then: トークン発行時に fail-fast（フォールバック禁止ポリシー）
        with pytest.raises(RuntimeError):
            security_module.create_access_token(uuid.uuid4())

    def test_should_raise_runtime_error_when_jwt_secret_is_empty(
        self, monkeypatch
    ):
        # Given: JWT_SECRET が空文字（誤って設定された状態）
        monkeypatch.setenv("JWT_SECRET", "")

        # When/Then: 空文字を「設定済み」と扱わず、fail-fast
        with pytest.raises(RuntimeError):
            security_module.create_access_token(uuid.uuid4())


# ---------------------------------------------------------------------------
# 401 helper（DRY 統合の契約ロック）
# ---------------------------------------------------------------------------


class TestUnauthorizedHelper:
    """`_unauthorized` ヘルパが返す HTTPException の契約を 1 点で固定する。

    Why:
        arch-review `ARCH-NEW-security-401-raise-duplication` 対応で
        `get_current_user` 経路の 401 構築を `_unauthorized()` に集約した。
        将来、誰かが「このヘルパを経由せず inline で `HTTPException` を構築する」
        変更を入れると Shotgun Surgery が再発する。本テストは
        ヘルパの (status, detail) 契約を独立に固定することで、再発時に
        単体テストレベルで気付けるようにする。
    """

    def test_should_return_http_exception_with_401_and_canonical_detail(self):
        # When: ヘルパを呼び出す
        exc = security_module._unauthorized()

        # Then: 401 と共通メッセージで構築された HTTPException が返る
        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.detail == security_module.INVALID_CREDENTIALS_MESSAGE
