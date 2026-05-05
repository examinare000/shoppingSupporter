"""GET /api/me/profile と PUT /api/me/profile の統合テスト。

Spec: docs/plans/phase1-foundation.md (T-05)
Design: docs/design/user-profile.md
ADR: docs/adr/013-api-schema-conventions.md
Plan: .takt/runs/20260505-124344-userprofile-api-t-05-t-05-user/reports/plan.md

レイヤー:
    - リポジトリ層（`api.repositories.user_profiles`）の SELECT / UPSERT /
      Card 存在確認の単位仕様は本ファイル末尾のリポジトリテストで担保する。
      Postgres 固有の挙動（FK CASCADE、joined load）を観測するため、
      tests/unit/ ではなく tests/integration/ に置く。
    - エンドポイントの HTTP 契約は TestClient 経由で end-to-end に検証する。

主な契約（plan.md「実装ガイドライン」と user-profile.md より）:
    - レスポンスは camelCase（`rakutenRank` / `isAmazonPrime` / `yahooPremium`
      / `defaultCardId` / `defaultCard` / `updatedAt`）。
    - GET 未保存時は 200 + デフォルト値 + `updatedAt: null` + `defaultCard: null`
      を返し、DB レコードは作成しない。
    - PUT は全フィールド必須の全置換。`defaultCardId: null` は受理する。
    - バリデーション順序: (1) Pydantic（型・Enum・extra=forbid）→
      (2) 認証 401 → (3) Card 存在確認 422。
    - `RakutenRank` は wire format 上 value（小文字、例: "diamond"）。
    - `defaultCard` は CardResponse 形を nested で同梱する（N+1 を起こさない）。

意図的にテストする観点:
    - リクエストは body で送る（query / response envelope 形を流用していないか）。
    - extra="forbid" で未知フィールド（accessToken など envelope の流用）を 422 で弾く。
    - rakuten_rank の大文字 ("REGULAR") は 422（Pydantic v2 既定の value 経由）。
"""
from __future__ import annotations

import uuid

import pytest

from api.common.models import RakutenRank, User, UserProfile
from api.repositories.user_profiles import (
    card_exists,
    get_profile_by_user_id,
    upsert_profile,
)


PROFILE_ENDPOINT = "/api/me/profile"
SIGNUP_ENDPOINT = "/api/auth/signup"
LOGIN_ENDPOINT = "/api/auth/login"


# レスポンスボディの camelCase 形は 1 箇所で正本化する。各キー個別の
# assert ではなく集合一致で見ることで、欠落・余分の双方を 1 テストで検出する。
EXPECTED_PROFILE_KEYS = {
    "rakutenRank",
    "isAmazonPrime",
    "yahooPremium",
    "defaultCardId",
    "defaultCard",
    "updatedAt",
}

# CardResponse の camelCase キー（test_cards.py と同期）。`defaultCard` の
# nested 構造はカード一覧と同形であることを契約として固定する。
EXPECTED_CARD_KEYS = {
    "id",
    "name",
    "baseRewardRate",
    "annualFee",
    "specialRewards",
}


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


def _make_payload(
    *,
    rakuten_rank: str = "regular",
    is_amazon_prime: bool = False,
    yahoo_premium: bool = False,
    default_card_id=None,
) -> dict:
    """PUT /api/me/profile の正規 body を camelCase で構築するファクトリ。

    全フィールド必須の全置換セマンティクス（user-profile.md §3.2）を
    1 箇所で表現する。テスト側のキー名を間違えるとリクエスト contract が
    検証できないため、camelCase（`rakutenRank` 等）で固定する。
    """
    return {
        "rakutenRank": rakuten_rank,
        "isAmazonPrime": is_amazon_prime,
        "yahooPremium": yahoo_premium,
        "defaultCardId": default_card_id,
    }


@pytest.fixture
def auth_token(client):
    """認証済みユーザー 1 名を作成し、その JWT を返す。"""
    email = "alice@example.com"
    password = "StrongPass1!"
    signup = _signup(client, email=email, password=password)
    assert signup.status_code == 201
    login = _login(client, email=email, password=password)
    assert login.status_code == 200
    return {
        "token": login.json()["accessToken"],
        "email": email,
        "user_id": uuid.UUID(signup.json()["id"]),
    }


@pytest.fixture
def seeded_card(db_session, make_card):
    """1 枚のカードを永続化して返す。`defaultCardId` 指定系のテストで利用する。"""
    card = make_card(
        name="楽天カード",
        base_reward_rate=1.0,
        annual_fee=0,
        special_rewards={"rakuten": 1.0},
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    return card


# ---------------------------------------------------------------------------
# GET /api/me/profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_should_return_200_with_default_values_when_no_profile_saved(
        self, client, auth_token
    ):
        # Given: 認証済みだが profile を一度も保存していないユーザー
        # When: GET /api/me/profile
        response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: 200（404 ではない。user-profile.md §3.1）
        assert response.status_code == 200
        body = response.json()
        # デフォルト値: rank=regular / 全 false / カード ID は null /
        # nested card も null / `updatedAt` は null（未保存マーカー）
        assert body["rakutenRank"] == "regular"
        assert body["isAmazonPrime"] is False
        assert body["yahooPremium"] is False
        assert body["defaultCardId"] is None
        assert body["defaultCard"] is None
        assert body["updatedAt"] is None

    def test_should_expose_exactly_camelcase_keys(self, client, auth_token):
        # Given: 認証済みユーザー
        # When: GET（未保存状態でも camelCase 契約は同じ）
        response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: キー集合がぴったり一致する（snake_case のリーク検出）
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == EXPECTED_PROFILE_KEYS

    def test_should_not_persist_record_when_profile_unsaved(
        self, client, db_session, auth_token
    ):
        # Why: user-profile.md §3.1「DB へのレコード作成は行わない」
        # When: GET /api/me/profile を呼ぶ（未保存状態）
        response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )
        assert response.status_code == 200

        # Then: user_profiles テーブルに行が増えていない（GET の冪等性）
        assert (
            db_session.query(UserProfile)
            .filter_by(user_id=auth_token["user_id"])
            .count()
            == 0
        )

    def test_should_return_saved_profile_with_nested_default_card(
        self, client, db_session, auth_token, seeded_card
    ):
        # Given: 認証済みユーザーの profile が DB に保存済みで、card を指定済み
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.GOLD,
                is_amazon_prime=True,
                yahoo_premium=False,
                default_card_id=seeded_card.id,
            )
        )
        db_session.commit()

        # When: GET
        response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: 200 + 保存済み値 + nested defaultCard が CardResponse 形
        assert response.status_code == 200
        body = response.json()
        assert body["rakutenRank"] == "gold"
        assert body["isAmazonPrime"] is True
        assert body["yahooPremium"] is False
        assert body["defaultCardId"] == seeded_card.id
        assert body["defaultCard"] is not None
        assert set(body["defaultCard"].keys()) == EXPECTED_CARD_KEYS
        assert body["defaultCard"]["id"] == seeded_card.id
        assert body["defaultCard"]["name"] == "楽天カード"

    def test_should_return_iso8601_updated_at_when_saved(
        self, client, db_session, auth_token
    ):
        # Given: profile を保存（updated_at は ORM の onupdate / default に
        # 任せる）
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.SILVER,
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=None,
            )
        )
        db_session.commit()

        # When: GET
        response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: updatedAt は文字列（ISO 8601）。null ではない。
        # (ADR-013 §6: datetime は ISO 8601 / Pydantic 既定挙動)
        assert response.status_code == 200
        updated_at = response.json()["updatedAt"]
        assert isinstance(updated_at, str)
        # ISO 8601 は "T" 区切りで日付と時刻を結合する。Safari 互換のため
        # スペース区切りは禁止（ADR-013 §6）。
        assert "T" in updated_at

    def test_should_return_default_card_null_when_no_card_assigned(
        self, client, db_session, auth_token
    ):
        # Given: profile は保存済みだが default_card_id が null
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=None,
            )
        )
        db_session.commit()

        # When: GET
        response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: defaultCardId と defaultCard の双方が null
        assert response.status_code == 200
        body = response.json()
        assert body["defaultCardId"] is None
        assert body["defaultCard"] is None


# ---------------------------------------------------------------------------
# Authentication on GET / PUT
# ---------------------------------------------------------------------------


class TestProfileAuth:
    """Profile エンドポイントは認証必須。ヘッダ欠落で 401 を返す。

    Why スモークだけ:
        トークン改ざん・期限切れ・スキーム違いは `tests/integration/test_auth.py`
        の `TestMe` で網羅済み。本ファイルでは「認証経路に乗っているか」だけ
        固定する。
    """

    def test_get_should_return_401_when_authorization_header_missing(
        self, client
    ):
        response = client.get(PROFILE_ENDPOINT)
        assert response.status_code == 401

    def test_put_should_return_401_when_authorization_header_missing(
        self, client
    ):
        response = client.put(PROFILE_ENDPOINT, json=_make_payload())
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/me/profile
# ---------------------------------------------------------------------------


class TestPutProfile:
    def test_should_return_200_and_persist_on_first_save(
        self, client, db_session, auth_token, seeded_card
    ):
        # Given: 認証済み + profile が未保存
        # When: 全フィールド入りの PUT を投げる
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(
                rakuten_rank="gold",
                is_amazon_prime=True,
                yahoo_premium=True,
                default_card_id=seeded_card.id,
            ),
        )

        # Then: 200 + 送信値そのまま + DB に行が新規作成されている
        assert response.status_code == 200
        body = response.json()
        assert body["rakutenRank"] == "gold"
        assert body["isAmazonPrime"] is True
        assert body["yahooPremium"] is True
        assert body["defaultCardId"] == seeded_card.id

        persisted = (
            db_session.query(UserProfile)
            .filter_by(user_id=auth_token["user_id"])
            .one()
        )
        assert persisted.rakuten_rank == RakutenRank.GOLD
        assert persisted.is_amazon_prime is True
        assert persisted.yahoo_premium is True
        assert persisted.default_card_id == seeded_card.id

    def test_should_expose_exactly_camelcase_keys(
        self, client, auth_token
    ):
        # When: PUT が成功したレスポンス
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(),
        )

        # Then: GET と同じ camelCase キー集合
        assert response.status_code == 200
        assert set(response.json().keys()) == EXPECTED_PROFILE_KEYS

    def test_should_replace_existing_profile_on_subsequent_put(
        self, client, db_session, auth_token, seeded_card
    ):
        # Given: 既に保存済みの profile
        first = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(
                rakuten_rank="regular",
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=seeded_card.id,
            ),
        )
        assert first.status_code == 200

        # When: 全フィールドを書き換える PUT
        second = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(
                rakuten_rank="diamond",
                is_amazon_prime=True,
                yahoo_premium=True,
                default_card_id=None,
            ),
        )

        # Then: 200 + DB の値も最新の PUT が反映されている
        assert second.status_code == 200
        body = second.json()
        assert body["rakutenRank"] == "diamond"
        assert body["isAmazonPrime"] is True
        assert body["yahooPremium"] is True
        assert body["defaultCardId"] is None
        assert body["defaultCard"] is None

        # DB 側にも反映（行は 1 つのまま）
        rows = (
            db_session.query(UserProfile)
            .filter_by(user_id=auth_token["user_id"])
            .all()
        )
        assert len(rows) == 1
        assert rows[0].rakuten_rank == RakutenRank.DIAMOND
        assert rows[0].default_card_id is None

    def test_should_accept_default_card_id_null_to_clear_card(
        self, client, db_session, auth_token, seeded_card
    ):
        # Given: 一度カードを登録した状態
        first = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(default_card_id=seeded_card.id),
        )
        assert first.status_code == 200
        assert first.json()["defaultCardId"] == seeded_card.id

        # When: defaultCardId=null で再度 PUT する（user-profile.md §3.2:
        #   「カード未設定状態への戻し」を意味する。422 ではない）
        second = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(default_card_id=None),
        )

        # Then: 200 で受理され、DB 側でも null になる
        assert second.status_code == 200
        assert second.json()["defaultCardId"] is None
        persisted = (
            db_session.query(UserProfile)
            .filter_by(user_id=auth_token["user_id"])
            .one()
        )
        assert persisted.default_card_id is None

    def test_should_advance_updated_at_on_subsequent_put(
        self, client, auth_token
    ):
        # Why: user-profile.md §2.1「`onupdate=datetime.utcnow` で自動更新」
        # の動作を契約として固定する。Phase 2 で `If-Unmodified-Since` 楽観
        # ロックの種にする伏線（同 §3.2）。
        # When: 2 回 PUT する
        first = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(rakuten_rank="regular"),
        )
        second = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(rakuten_rank="silver"),
        )

        # Then: updatedAt は単調増加する
        assert first.status_code == 200
        assert second.status_code == 200
        first_at = first.json()["updatedAt"]
        second_at = second.json()["updatedAt"]
        assert isinstance(first_at, str) and first_at
        assert isinstance(second_at, str) and second_at
        # 文字列の辞書順比較が時刻比較として成立するのは ISO 8601 の性質
        assert second_at >= first_at

    def test_should_serialize_rakuten_rank_as_lowercase_value(
        self, client, auth_token
    ):
        # Why: ADR-013 §5 / user-profile.md §2.2「value（小文字）」を契約として固定。
        # When: 大文字定義 (`RakutenRank.DIAMOND`) を value 形 ("diamond") で受け取る
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(rakuten_rank="diamond"),
        )

        # Then: レスポンス側も "diamond"（"DIAMOND" や "Diamond" ではない）
        assert response.status_code == 200
        assert response.json()["rakutenRank"] == "diamond"


# ---------------------------------------------------------------------------
# PUT validation (Pydantic-level 422)
# ---------------------------------------------------------------------------


class TestPutProfileValidation:
    """Pydantic レイヤで弾かれる 422 群。

    バリデーション順序の (1) Pydantic（型・Enum・extra=forbid）に対応する。
    認証 401 / カード存在確認 422 は別クラス（TestValidationOrder）で扱う。
    """

    def test_should_return_422_when_rakuten_rank_field_missing(
        self, client, auth_token
    ):
        body = _make_payload()
        del body["rakutenRank"]
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=body,
        )
        assert response.status_code == 422

    def test_should_return_422_when_is_amazon_prime_field_missing(
        self, client, auth_token
    ):
        body = _make_payload()
        del body["isAmazonPrime"]
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=body,
        )
        assert response.status_code == 422

    def test_should_return_422_when_yahoo_premium_field_missing(
        self, client, auth_token
    ):
        body = _make_payload()
        del body["yahooPremium"]
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=body,
        )
        assert response.status_code == 422

    def test_should_return_422_when_default_card_id_field_missing(
        self, client, auth_token
    ):
        # Why: PUT は **全置換** なので `defaultCardId` 自体の省略は不可。
        # 「カード未設定」を表現したい場合は明示的に null を送る（§3.2）。
        body = _make_payload()
        del body["defaultCardId"]
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=body,
        )
        assert response.status_code == 422

    def test_should_return_422_when_extra_field_is_present(
        self, client, auth_token
    ):
        # Why: extra="forbid"。response envelope の流用やタイポを 422 で弾く
        # （ADR-013 §2 / user-profile.md §3.3）。
        body = _make_payload()
        body["accessToken"] = "leaking-from-token-response"
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=body,
        )
        assert response.status_code == 422

    def test_should_return_422_when_rakuten_rank_value_is_uppercase(
        self, client, auth_token
    ):
        # Why: ADR-013 §5 / user-profile.md §2.2 で wire format は value（小文字）。
        # Pydantic v2 の既定挙動（value 経由）を変更しないことを契約として固定し、
        # `"REGULAR"` の入力は 422 にする。
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(rakuten_rank="REGULAR"),
        )
        assert response.status_code == 422

    def test_should_return_422_when_rakuten_rank_value_is_unknown(
        self, client, auth_token
    ):
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(rakuten_rank="legendary"),
        )
        assert response.status_code == 422

    def test_should_return_422_when_is_amazon_prime_is_not_boolean(
        self, client, auth_token
    ):
        # Why: 型違反は Pydantic レベルで 422。"yes" 等の文字列を受理しない。
        body = _make_payload()
        body["isAmazonPrime"] = "yes"
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=body,
        )
        assert response.status_code == 422

    def test_should_return_422_when_default_card_id_references_missing_card(
        self, client, auth_token
    ):
        # Why: user-profile.md §3.2「リポジトリ層でカード存在確認 → 422」。
        # FK IntegrityError 経由ではなく事前 SELECT で意味的に 422 を返す。
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(default_card_id=99999),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Validation order: Pydantic -> 401 -> 422 (card existence)
# ---------------------------------------------------------------------------


class TestValidationOrder:
    """user-profile.md §3.2 のバリデーション順序を契約として固定する。

    順序: (1) Pydantic（型・Enum・extra=forbid）→ (2) 認証 401 →
    (3) リポジトリ層でカード存在確認 422。
    """

    def test_invalid_body_without_auth_should_return_422_pydantic_first(
        self, client
    ):
        # Why: Pydantic は認証より前に評価される。FastAPI の依存解決順に
        # 関係なく、body の型違反は 422 が優先する（ADR-013 / user-profile §3.2）。
        # When: 認証なし + body が壊れている
        response = client.put(
            PROFILE_ENDPOINT,
            json=_make_payload(rakuten_rank="REGULAR"),  # 大文字＝422
        )

        # Then: 401 ではなく 422（Pydantic 先）
        assert response.status_code == 422

    def test_valid_body_without_auth_should_return_401(self, client):
        # Given: body は完全に正しいが認証ヘッダなし
        # When: PUT
        response = client.put(
            PROFILE_ENDPOINT, json=_make_payload(default_card_id=99999)
        )

        # Then: 401（カード存在確認まで進まない。422 にしてはいけない）
        assert response.status_code == 401

    def test_invalid_default_card_id_with_auth_should_return_422(
        self, client, auth_token
    ):
        # Given: 認証あり + body は型としては正しいが defaultCardId が不存在
        # When: PUT
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(default_card_id=99999),
        )

        # Then: 422（リポジトリ層の Card 存在確認）
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT -> GET round trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """PUT で書き、GET で読んだ値が一致することを保証する。

    Why:
        PUT 系の 200 ボディ単独ではキャッシュや遅延書き込みのバグを検出
        できないため、別リクエストで GET し直して整合性を確認する。
    """

    @pytest.mark.parametrize(
        "rank",
        # 全 5 ランクを網羅する（境界の "diamond" を含む）。
        ["regular", "silver", "gold", "platinum", "diamond"],
    )
    def test_should_round_trip_each_rakuten_rank(
        self, client, auth_token, rank
    ):
        # Given: PUT で各ランクを書き込む
        put_response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(rakuten_rank=rank),
        )
        assert put_response.status_code == 200

        # When: GET で読み返す
        get_response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: GET の値が PUT 直後と一致する
        assert get_response.status_code == 200
        assert get_response.json()["rakutenRank"] == rank

    def test_should_round_trip_full_payload_with_card(
        self, client, auth_token, seeded_card
    ):
        # Given: 全フィールドをセットして PUT
        put_response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_payload(
                rakuten_rank="platinum",
                is_amazon_prime=True,
                yahoo_premium=True,
                default_card_id=seeded_card.id,
            ),
        )
        assert put_response.status_code == 200

        # When: GET
        get_response = client.get(
            PROFILE_ENDPOINT, headers=_auth_header(auth_token["token"])
        )

        # Then: PUT と GET のスカラー値群が完全一致する。`updatedAt` は
        # サーバ側で `onupdate` 自動更新されるためここでは比較しない。
        assert get_response.status_code == 200
        assert get_response.json()["rakutenRank"] == put_response.json()["rakutenRank"]
        assert get_response.json()["isAmazonPrime"] == put_response.json()["isAmazonPrime"]
        assert get_response.json()["yahooPremium"] == put_response.json()["yahooPremium"]
        assert get_response.json()["defaultCardId"] == put_response.json()["defaultCardId"]
        # nested defaultCard の id も一致する（GET 経路でも joinedload 済）
        assert get_response.json()["defaultCard"]["id"] == seeded_card.id


# ---------------------------------------------------------------------------
# Request body contract
# ---------------------------------------------------------------------------


class TestRequestBodyContract:
    """PUT の入力位置が JSON body であることを保護する。

    Why:
        実装が誤って query string や response envelope の構造から入力を
        拾うと、外部契約が崩れる。`tests/integration/test_auth.py` の
        `TestRequestBodyContract` と対になるテスト。
    """

    def test_put_should_ignore_query_string_payload(self, client, auth_token):
        # Given: body 欠落、payload を query string に置く
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            params={
                "rakutenRank": "regular",
                "isAmazonPrime": "false",
                "yahooPremium": "false",
                "defaultCardId": "",
            },
        )

        # Then: body 必須なので 422（query は読まない）
        assert response.status_code == 422

    def test_put_should_not_misread_token_envelope_shaped_body(
        self, client, auth_token
    ):
        # Given: response envelope を真似た body
        envelope_shaped_body = {
            "accessToken": "fake-token",
            "tokenType": "bearer",
        }

        # When: その body で PUT
        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=envelope_shaped_body,
        )

        # Then: 422（`extra="forbid"` で `accessToken` を弾き、必須欠落でも 422）
        assert response.status_code == 422

    def test_put_should_not_misread_get_response_shaped_body(
        self, client, auth_token
    ):
        # Why: GET レスポンスをそのまま body に貼り付けても受理しない。
        # `defaultCard` / `updatedAt` は UserProfileUpdate に存在しない
        # フィールドなので extra="forbid" が拒否する。
        get_response_shaped_body = {
            "rakutenRank": "regular",
            "isAmazonPrime": False,
            "yahooPremium": False,
            "defaultCardId": None,
            "defaultCard": None,
            "updatedAt": None,
        }

        response = client.put(
            PROFILE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=get_response_shaped_body,
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# CASCADE delete (data integrity)
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """`users.id` 削除時に `user_profiles` 行も自動削除されることを担保する。

    Why:
        user-profile.md §2.1「カスケード」を契約として固定する。Alembic の
        マイグレーションで `ON DELETE CASCADE` を張り直す対象なので、
        マイグレーション漏れを観測する。
    """

    def test_user_delete_should_cascade_to_user_profile(
        self, db_session, auth_token
    ):
        # Given: profile を保存
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=None,
            )
        )
        db_session.commit()
        assert (
            db_session.query(UserProfile)
            .filter_by(user_id=auth_token["user_id"])
            .count()
            == 1
        )

        # When: 親 User を削除
        db_session.query(User).filter_by(id=auth_token["user_id"]).delete()
        db_session.commit()

        # Then: 子の UserProfile も自動削除される（ON DELETE CASCADE）
        assert (
            db_session.query(UserProfile)
            .filter_by(user_id=auth_token["user_id"])
            .count()
            == 0
        )


# ---------------------------------------------------------------------------
# Repository unit tests
# ---------------------------------------------------------------------------
#
# 直接 Postgres を叩くので tests/unit/ ではなく tests/integration/ に置く。
# joined load の挙動と FK 存在確認は SQLite では正確に再現できない。


def _create_user(db_session) -> User:
    """テスト用の最小 User を直接作成して返す（auth 経路を介さない）。"""
    user = User(
        email=f"user-{uuid.uuid4()}@example.com",
        hashed_password="$2b$12$dummyhashforrepositorytestsdummyhashforrepositorytests",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestRepositoryGetProfileByUserId:
    def test_should_return_none_when_no_profile_exists(self, db_session):
        # Given: profile 行のないユーザー
        user = _create_user(db_session)

        # When: 取得
        result = get_profile_by_user_id(db_session, user.id)

        # Then: None が返る（HTTP 層でデフォルトに変換される前提）
        assert result is None

    def test_should_return_profile_when_exists(self, db_session):
        # Given: 保存済み profile
        user = _create_user(db_session)
        db_session.add(
            UserProfile(
                user_id=user.id,
                rakuten_rank=RakutenRank.SILVER,
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=None,
            )
        )
        db_session.commit()

        # When: 取得
        result = get_profile_by_user_id(db_session, user.id)

        # Then: 該当行が返る
        assert result is not None
        assert result.user_id == user.id
        assert result.rakuten_rank == RakutenRank.SILVER

    def test_should_eagerly_load_default_card_to_avoid_n_plus_one(
        self, db_session, make_card
    ):
        # Why: user-profile.md §3.3 / plan.md「joinedload(UserProfile.default_card)」
        # で N+1 を回避する契約。リポジトリ呼び出し後に session を閉じても
        # default_card にアクセスできることで eager load を担保する。
        # Given: card を持つ profile
        user = _create_user(db_session)
        card = make_card(name="楽天カード", base_reward_rate=1.0)
        db_session.add(card)
        db_session.commit()
        db_session.refresh(card)
        db_session.add(
            UserProfile(
                user_id=user.id,
                rakuten_rank=RakutenRank.GOLD,
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=card.id,
            )
        )
        db_session.commit()

        # When: リポジトリで取得 → セッションを切り離す
        result = get_profile_by_user_id(db_session, user.id)
        db_session.expunge_all()

        # Then: default_card にアクセスしても Lazy load 用の DB クエリが
        #   発行されず、属性が取れる（joinedload されている）
        assert result is not None
        assert result.default_card is not None
        assert result.default_card.id == card.id
        assert result.default_card.name == "楽天カード"


class TestRepositoryCardExists:
    def test_should_return_true_for_existing_card(self, db_session, make_card):
        card = make_card(name="存在するカード")
        db_session.add(card)
        db_session.commit()
        db_session.refresh(card)

        assert card_exists(db_session, card.id) is True

    def test_should_return_false_for_unknown_card(self, db_session):
        # Why: FK IntegrityError を待たずに 422 へ繋ぐためのチェック。
        assert card_exists(db_session, 99999) is False

    def test_should_return_false_when_table_is_empty(self, db_session):
        assert card_exists(db_session, 1) is False


class TestRepositoryUpsertProfile:
    def test_should_insert_when_no_row_exists_for_user(self, db_session):
        # Given: profile 行が無いユーザー
        user = _create_user(db_session)

        # When: upsert
        result = upsert_profile(
            db_session,
            user_id=user.id,
            rakuten_rank=RakutenRank.GOLD,
            is_amazon_prime=True,
            yahoo_premium=False,
            default_card_id=None,
        )

        # Then: 新規行が作られ、戻り値も同一
        assert result.user_id == user.id
        assert result.rakuten_rank == RakutenRank.GOLD
        assert result.is_amazon_prime is True
        assert result.yahoo_premium is False
        assert result.default_card_id is None

        rows = db_session.query(UserProfile).filter_by(user_id=user.id).all()
        assert len(rows) == 1

    def test_should_update_when_row_already_exists(self, db_session):
        # Given: 既に行がある状態
        user = _create_user(db_session)
        db_session.add(
            UserProfile(
                user_id=user.id,
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=None,
            )
        )
        db_session.commit()

        # When: 同じユーザーの値を全置換 upsert
        result = upsert_profile(
            db_session,
            user_id=user.id,
            rakuten_rank=RakutenRank.DIAMOND,
            is_amazon_prime=True,
            yahoo_premium=True,
            default_card_id=None,
        )

        # Then: 行は 1 つのまま（INSERT ではなく UPDATE）、値が新しい方
        rows = db_session.query(UserProfile).filter_by(user_id=user.id).all()
        assert len(rows) == 1
        assert result.rakuten_rank == RakutenRank.DIAMOND
        assert result.is_amazon_prime is True
        assert result.yahoo_premium is True

    def test_should_set_default_card_id_when_card_specified(
        self, db_session, make_card
    ):
        # Given: 既存カード
        user = _create_user(db_session)
        card = make_card(name="セットされるカード")
        db_session.add(card)
        db_session.commit()
        db_session.refresh(card)

        # When: default_card_id 指定で upsert
        result = upsert_profile(
            db_session,
            user_id=user.id,
            rakuten_rank=RakutenRank.REGULAR,
            is_amazon_prime=False,
            yahoo_premium=False,
            default_card_id=card.id,
        )

        # Then: 値が反映され、joined load 済みで default_card もアクセス可
        assert result.default_card_id == card.id
        assert result.default_card is not None
        assert result.default_card.id == card.id

    def test_should_clear_default_card_id_to_null(self, db_session, make_card):
        # Why: user-profile.md §3.2「カード未設定状態への戻し」。
        # Given: 既にカード付きで保存済みの profile
        user = _create_user(db_session)
        card = make_card(name="後で外すカード")
        db_session.add(card)
        db_session.commit()
        db_session.refresh(card)
        db_session.add(
            UserProfile(
                user_id=user.id,
                rakuten_rank=RakutenRank.GOLD,
                is_amazon_prime=False,
                yahoo_premium=False,
                default_card_id=card.id,
            )
        )
        db_session.commit()

        # When: default_card_id=None で upsert
        result = upsert_profile(
            db_session,
            user_id=user.id,
            rakuten_rank=RakutenRank.GOLD,
            is_amazon_prime=False,
            yahoo_premium=False,
            default_card_id=None,
        )

        # Then: null に書き戻されている
        assert result.default_card_id is None
        persisted = (
            db_session.query(UserProfile).filter_by(user_id=user.id).one()
        )
        assert persisted.default_card_id is None
