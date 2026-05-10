"""GET /api/me/usage と PUT /api/me/usage の統合テスト。

Spec: docs/plans/phase3-analytics-suggestion.md (T-17) §4 / §3.2

主な契約:
    GET /api/me/usage:
        - 当月全3サイトの利用実績を返す
        - 未保存は 200 + 0 デフォルト（404 ではない。profile と同パターン）
        - レスポンス: {"month": "YYYY-MM", "items": [...]}
        - 各エントリ: {"site": "amazon", "amountSpent": 0, "pointsEarned": 0, "shopCount": 0}
    PUT /api/me/usage:
        - body: {"site": "amazon", "month": "YYYY-MM", "amountSpent": ..., "pointsEarned": ..., "shopCount": ...}
        - 1サイト×1月の UPSERT
        - 全フィールド必須（extra="forbid"）
        - レスポンス: 更新後のエントリ 1 件

意図的にテストする観点:
    - リクエストは body で送る（query string は読まない）
    - extra="forbid" で未知フィールドを 422 で弾く
    - site は小文字 value（"amazon"）。大文字 "AMAZON" は 422
    - month は YYYY-MM 形式のみ受理
    - amount_spent / points_earned は非負整数
    - GET レスポンスの形（month + items）を PUT body に流用すると 422
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import pytest

from api.common.models import MonthlyUsage, SiteType, User

USAGE_ENDPOINT = "/api/me/usage"
SIGNUP_ENDPOINT = "/api/auth/signup"
LOGIN_ENDPOINT = "/api/auth/login"

SITES = ["amazon", "rakuten", "yahoo"]

# Why datetime.now(timezone.utc): docs/plans/phase3-analytics-suggestion.md §3.2
# 「当月計算は datetime.now(timezone.utc).strftime("%Y-%m") を使用」に合わせる。
CURRENT_MONTH = datetime.now(timezone.utc).strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signup(client, *, email: str, password: str):
    return client.post(SIGNUP_ENDPOINT, json={"email": email, "password": password})


def _login(client, *, email: str, password: str):
    return client.post(LOGIN_ENDPOINT, json={"email": email, "password": password})


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_put_payload(
    *,
    site: str = "amazon",
    month: str = CURRENT_MONTH,
    amount_spent: int = 0,
    points_earned: int = 0,
    shop_count: int = 0,
) -> dict:
    """PUT /api/me/usage の正規 body を camelCase で構築するファクトリ。

    全フィールド必須の UPSERT セマンティクスに合わせ、camelCase で固定する。
    """
    return {
        "site": site,
        "month": month,
        "amountSpent": amount_spent,
        "pointsEarned": points_earned,
        "shopCount": shop_count,
    }


@pytest.fixture
def auth_token(client):
    """認証済みユーザー 1 名を作成し、その JWT を返す。"""
    email = "usage_user@example.com"
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


# ---------------------------------------------------------------------------
# GET /api/me/usage
# ---------------------------------------------------------------------------


class TestGetUsage:
    def test_should_return_200_with_default_zeros_when_no_usage_saved(
        self, client, auth_token
    ):
        """未保存時は 200 + 全3サイト 0 デフォルトを返す（404 ではない）。

        Why: docs/plans/phase3-analytics-suggestion.md §3.2 profile と同パターン。
        """
        # Given: 認証済みだが利用実績を一度も保存していないユーザー
        # When
        response = client.get(USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]))
        # Then
        assert response.status_code == 200
        body = response.json()
        assert "month" in body
        assert "items" in body
        # 3サイト分のエントリが返る
        assert len(body["items"]) == 3
        site_names = {item["site"] for item in body["items"]}
        assert site_names == {"amazon", "rakuten", "yahoo"}
        # すべてのフィールドが 0 デフォルト
        for item in body["items"]:
            assert item["amountSpent"] == 0
            assert item["pointsEarned"] == 0
            assert item["shopCount"] == 0

    def test_should_return_current_month_in_yyyy_mm_format(self, client, auth_token):
        """レスポンスの month フィールドが YYYY-MM 形式の当月。"""
        # When
        response = client.get(USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]))
        # Then
        assert response.status_code == 200
        month = response.json()["month"]
        assert re.match(r"^\d{4}-\d{2}$", month)
        assert month == CURRENT_MONTH

    def test_should_expose_exactly_camelcase_keys_per_item(self, client, auth_token):
        """各サイトエントリの camelCase キーが正確に揃っている。"""
        # When
        response = client.get(USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]))
        # Then
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert set(item.keys()) == {"site", "amountSpent", "pointsEarned", "shopCount"}

    def test_should_return_saved_usage_for_current_month(
        self, client, db_session, auth_token
    ):
        """保存済みの利用実績が正しく返される（未保存サイトは 0）。"""
        # Given: AMAZON の利用実績を直接 DB に保存
        db_session.add(
            MonthlyUsage(
                user_id=auth_token["user_id"],
                site=SiteType.AMAZON,
                recorded_month=CURRENT_MONTH,
                amount_spent=10000,
                points_earned=100,
                shop_count=0,
            )
        )
        db_session.commit()

        # When
        response = client.get(USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]))

        # Then: AMAZON は保存値、RAKUTEN / YAHOO は 0 デフォルト
        assert response.status_code == 200
        items = response.json()["items"]
        amazon = next(i for i in items if i["site"] == "amazon")
        assert amazon["amountSpent"] == 10000
        assert amazon["pointsEarned"] == 100
        rakuten = next(i for i in items if i["site"] == "rakuten")
        assert rakuten["amountSpent"] == 0

    def test_should_not_return_previous_month_usage(
        self, client, db_session, auth_token
    ):
        """先月の利用実績は GET レスポンスに含まれない（当月のみ）。"""
        # Given: 先月分のデータを保存
        last_month = "2026-04"
        db_session.add(
            MonthlyUsage(
                user_id=auth_token["user_id"],
                site=SiteType.AMAZON,
                recorded_month=last_month,
                amount_spent=99999,
                points_earned=999,
                shop_count=10,
            )
        )
        db_session.commit()

        # When: GET（当月）
        response = client.get(USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]))

        # Then: 当月分は 0 デフォルト（先月のデータが混入しない）
        assert response.status_code == 200
        amazon = next(i for i in response.json()["items"] if i["site"] == "amazon")
        assert amazon["amountSpent"] == 0


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestUsageAuth:
    """Usage エンドポイントは認証必須。ヘッダ欠落で 401 を返す。"""

    def test_get_should_return_401_when_authorization_header_missing(self, client):
        assert client.get(USAGE_ENDPOINT).status_code == 401

    def test_put_should_return_401_when_authorization_header_missing(self, client):
        # Why: 正しい body でも認証なしなら 401（Pydantic 後 → auth の順序）
        response = client.put(USAGE_ENDPOINT, json=_make_put_payload())
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/me/usage
# ---------------------------------------------------------------------------


class TestPutUsage:
    def test_should_return_200_and_persist_on_first_save(
        self, client, db_session, auth_token
    ):
        """初回 PUT が 200 を返し DB に保存される。"""
        # When
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(
                site="amazon",
                month=CURRENT_MONTH,
                amount_spent=5000,
                points_earned=50,
                shop_count=0,
            ),
        )
        # Then: レスポンス
        assert response.status_code == 200
        body = response.json()
        assert body["site"] == "amazon"
        assert body["month"] == CURRENT_MONTH
        assert body["amountSpent"] == 5000
        assert body["pointsEarned"] == 50
        assert body["shopCount"] == 0

        # DB に保存されている
        persisted = (
            db_session.query(MonthlyUsage)
            .filter_by(
                user_id=auth_token["user_id"],
                site=SiteType.AMAZON,
                recorded_month=CURRENT_MONTH,
            )
            .one()
        )
        assert persisted.amount_spent == 5000
        assert persisted.points_earned == 50

    def test_should_expose_exactly_camelcase_keys_in_response(
        self, client, auth_token
    ):
        """PUT レスポンスのキーが正確に揃っている（snake_case リーク検出）。"""
        # When
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(),
        )
        # Then
        assert response.status_code == 200
        assert set(response.json().keys()) == {
            "site", "month", "amountSpent", "pointsEarned", "shopCount"
        }

    def test_should_update_existing_record_on_second_put(
        self, client, db_session, auth_token
    ):
        """同じサイト×月への再 PUT は値を上書きする（UPSERT）。"""
        # Given: 初回保存
        first = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="rakuten", amount_spent=1000),
        )
        assert first.status_code == 200

        # When: 同じサイト×月で値を上書き
        second = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="rakuten", amount_spent=9999),
        )

        # Then: 200、値が更新
        assert second.status_code == 200
        assert second.json()["amountSpent"] == 9999

        # DB 行は 1 つのまま（INSERT されない）
        rows = (
            db_session.query(MonthlyUsage)
            .filter_by(user_id=auth_token["user_id"], site=SiteType.RAKUTEN)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].amount_spent == 9999

    def test_should_not_affect_other_sites_on_put(
        self, client, db_session, auth_token
    ):
        """一方のサイトを PUT しても他サイトに影響しない。"""
        # Given: AMAZON の利用実績を事前保存
        db_session.add(
            MonthlyUsage(
                user_id=auth_token["user_id"],
                site=SiteType.AMAZON,
                recorded_month=CURRENT_MONTH,
                amount_spent=10000,
                points_earned=100,
                shop_count=0,
            )
        )
        db_session.commit()

        # When: RAKUTEN だけ PUT
        client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="rakuten", amount_spent=5000),
        )

        # Then: AMAZON の値はそのまま
        amazon = (
            db_session.query(MonthlyUsage)
            .filter_by(
                user_id=auth_token["user_id"],
                site=SiteType.AMAZON,
                recorded_month=CURRENT_MONTH,
            )
            .one()
        )
        assert amazon.amount_spent == 10000

    def test_should_allow_different_month_entries(
        self, client, db_session, auth_token
    ):
        """異なる月への PUT は別エントリとして保存される（月は PK の一部）。"""
        # When: 当月と先月の両方を PUT
        client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="amazon", month=CURRENT_MONTH, amount_spent=5000),
        )
        client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="amazon", month="2026-04", amount_spent=9000),
        )

        # Then: 2 件が別エントリとして存在する
        rows = (
            db_session.query(MonthlyUsage)
            .filter_by(user_id=auth_token["user_id"], site=SiteType.AMAZON)
            .all()
        )
        assert len(rows) == 2
        months = {r.recorded_month for r in rows}
        assert months == {CURRENT_MONTH, "2026-04"}

    @pytest.mark.parametrize("site", SITES)
    def test_should_accept_all_three_sites(self, client, auth_token, site):
        """全3サイトへの PUT が受理される。"""
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site=site),
        )
        assert response.status_code == 200
        assert response.json()["site"] == site


# ---------------------------------------------------------------------------
# PUT → GET round trip
# ---------------------------------------------------------------------------


class TestUsageRoundTrip:
    """PUT で書き、GET で読んだ値が一致することを保証する。"""

    @pytest.mark.parametrize("site", SITES)
    def test_should_round_trip_each_site(self, client, auth_token, site):
        """全サイトで PUT → GET のラウンドトリップが一致する。"""
        # Given: PUT
        amount = 10000
        points = 100
        shop = 2
        put = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(
                site=site, amount_spent=amount, points_earned=points, shop_count=shop
            ),
        )
        assert put.status_code == 200

        # When: GET
        get = client.get(USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]))
        assert get.status_code == 200

        # Then: GET のサイトエントリが PUT 値と一致する
        items = get.json()["items"]
        item = next(i for i in items if i["site"] == site)
        assert item["amountSpent"] == amount
        assert item["pointsEarned"] == points
        assert item["shopCount"] == shop

    def test_get_shows_all_three_sites_after_put(self, client, auth_token):
        """1サイトを PUT しても GET は 3サイト全件を返す（保存済み + 0 デフォルト）。"""
        # Given: YAHOO だけ PUT
        client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="yahoo", amount_spent=3000),
        )
        # When: GET
        response = client.get(USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]))
        # Then: 3サイト全件
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 3
        yahoo = next(i for i in items if i["site"] == "yahoo")
        assert yahoo["amountSpent"] == 3000
        amazon = next(i for i in items if i["site"] == "amazon")
        assert amazon["amountSpent"] == 0


# ---------------------------------------------------------------------------
# PUT validation (Pydantic-level 422)
# ---------------------------------------------------------------------------


class TestPutUsageValidation:
    """Pydantic レイヤで弾かれる 422 群。"""

    def test_should_return_422_when_site_field_missing(self, client, auth_token):
        body = _make_put_payload()
        del body["site"]
        response = client.put(
            USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]), json=body
        )
        assert response.status_code == 422

    def test_should_return_422_when_month_field_missing(self, client, auth_token):
        body = _make_put_payload()
        del body["month"]
        response = client.put(
            USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]), json=body
        )
        assert response.status_code == 422

    def test_should_return_422_when_amount_spent_missing(self, client, auth_token):
        body = _make_put_payload()
        del body["amountSpent"]
        response = client.put(
            USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]), json=body
        )
        assert response.status_code == 422

    def test_should_return_422_when_points_earned_missing(self, client, auth_token):
        body = _make_put_payload()
        del body["pointsEarned"]
        response = client.put(
            USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]), json=body
        )
        assert response.status_code == 422

    def test_should_return_422_when_shop_count_missing(self, client, auth_token):
        body = _make_put_payload()
        del body["shopCount"]
        response = client.put(
            USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]), json=body
        )
        assert response.status_code == 422

    def test_should_return_422_when_site_is_invalid_enum_value(
        self, client, auth_token
    ):
        """無効なサイト名は 422。"""
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="unknown"),
        )
        assert response.status_code == 422

    def test_should_return_422_when_site_is_uppercase(self, client, auth_token):
        """大文字のサイト名 (AMAZON) は 422（wire format は小文字 value）。

        Why: ADR-013 §5 / docs/plans/phase3-analytics-suggestion.md と同様に
        wire format は Enum の value（小文字）に固定する。
        """
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(site="AMAZON"),
        )
        assert response.status_code == 422

    def test_should_return_422_when_month_format_is_invalid(self, client, auth_token):
        """YYYY-MM 以外の month フォーマットは 422。"""
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(month="2026/05"),
        )
        assert response.status_code == 422

    def test_should_return_422_when_amount_spent_is_negative(self, client, auth_token):
        """amount_spent が負数の場合は 422。"""
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(amount_spent=-1),
        )
        assert response.status_code == 422

    def test_should_return_422_when_points_earned_is_negative(self, client, auth_token):
        """points_earned が負数の場合は 422。"""
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=_make_put_payload(points_earned=-1),
        )
        assert response.status_code == 422

    def test_should_return_422_when_extra_field_present(self, client, auth_token):
        """extra="forbid"。未知フィールドは 422。"""
        body = _make_put_payload()
        body["extraField"] = "unexpected"
        response = client.put(
            USAGE_ENDPOINT, headers=_auth_header(auth_token["token"]), json=body
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Validation order: Pydantic → 401
# ---------------------------------------------------------------------------


class TestValidationOrder:
    """バリデーション順序: (1) Pydantic 422 → (2) 認証 401。"""

    def test_invalid_body_without_auth_should_return_422_pydantic_first(
        self, client
    ):
        """Pydantic は認証より先に評価される（不正な body + 未認証 → 422）。"""
        response = client.put(
            USAGE_ENDPOINT,
            json=_make_put_payload(site="INVALID_UPPERCASE"),  # Pydantic が 422
        )
        assert response.status_code == 422

    def test_valid_body_without_auth_should_return_401(self, client):
        """正しい body + 認証なし → 401（Pydantic パス後に認証チェック）。"""
        response = client.put(
            USAGE_ENDPOINT,
            json=_make_put_payload(),  # valid body
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Request body contract
# ---------------------------------------------------------------------------


class TestUsageRequestBodyContract:
    """PUT の入力位置が JSON body であることを保護する。

    Why:
        実装が誤って query string や GET レスポンス形から入力を拾うと外部
        契約が崩れる。test_profile.py の TestRequestBodyContract と対になる。
    """

    def test_put_should_ignore_query_string_payload(self, client, auth_token):
        """body 欠落、payload を query string に置くと 422（query は読まない）。"""
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            params={
                "site": "amazon",
                "month": CURRENT_MONTH,
                "amountSpent": "0",
                "pointsEarned": "0",
                "shopCount": "0",
            },
        )
        assert response.status_code == 422

    def test_put_should_not_misread_get_response_shape_as_body(
        self, client, auth_token
    ):
        """GET レスポンスの形（month + items）を PUT body に使うと 422。

        Why: GET と PUT のスキーマは異なる。GET の形（month + items のネスト）を
        そのまま PUT body に流用するバグを extra="forbid" で検出する。
        """
        get_response_shaped_body = {
            "month": CURRENT_MONTH,
            "items": [
                {
                    "site": "amazon",
                    "amountSpent": 0,
                    "pointsEarned": 0,
                    "shopCount": 0,
                },
            ],
        }
        response = client.put(
            USAGE_ENDPOINT,
            headers=_auth_header(auth_token["token"]),
            json=get_response_shaped_body,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Repository unit tests (Postgres specific)
# ---------------------------------------------------------------------------
#
# 直接 Postgres を叩くので tests/unit/ ではなく tests/integration/ に置く。
# MonthlyUsage の PK は (user_id, site, recorded_month) の複合キー。
# UPSERT は PostgreSQL INSERT ... ON CONFLICT DO UPDATE を使う。


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


class TestRepositoryGetUsageByUserAndMonth:
    def test_should_return_empty_list_when_no_records(self, db_session):
        """利用実績なしのユーザーは空リストが返る。"""
        from api.repositories.monthly_usage import get_usage_by_user_and_month

        user = _create_user(db_session)
        result = get_usage_by_user_and_month(db_session, user.id, CURRENT_MONTH)
        assert result == []

    def test_should_return_records_for_specified_month(self, db_session):
        """指定月の記録を返す。"""
        from api.repositories.monthly_usage import get_usage_by_user_and_month

        user = _create_user(db_session)
        db_session.add(
            MonthlyUsage(
                user_id=user.id,
                site=SiteType.AMAZON,
                recorded_month=CURRENT_MONTH,
                amount_spent=5000,
                points_earned=50,
                shop_count=0,
            )
        )
        db_session.commit()

        result = get_usage_by_user_and_month(db_session, user.id, CURRENT_MONTH)
        assert len(result) == 1
        assert result[0].amount_spent == 5000

    def test_should_not_return_records_from_other_month(self, db_session):
        """異なる月の記録は含まれない。"""
        from api.repositories.monthly_usage import get_usage_by_user_and_month

        user = _create_user(db_session)
        db_session.add(
            MonthlyUsage(
                user_id=user.id,
                site=SiteType.AMAZON,
                recorded_month="2026-04",  # 先月
                amount_spent=99999,
                points_earned=999,
                shop_count=10,
            )
        )
        db_session.commit()

        result = get_usage_by_user_and_month(db_session, user.id, CURRENT_MONTH)
        assert result == []


class TestRepositoryUpsertUsage:
    def test_should_insert_new_record(self, db_session):
        """初回 upsert でレコードが作成される。"""
        from api.repositories.monthly_usage import upsert_usage

        user = _create_user(db_session)
        result = upsert_usage(
            db_session,
            user_id=user.id,
            site=SiteType.AMAZON,
            recorded_month=CURRENT_MONTH,
            amount_spent=5000,
            points_earned=50,
            shop_count=0,
        )
        # Then
        assert result.user_id == user.id
        assert result.site == SiteType.AMAZON
        assert result.recorded_month == CURRENT_MONTH
        assert result.amount_spent == 5000
        assert result.points_earned == 50
        assert result.shop_count == 0

    def test_should_update_on_conflict(self, db_session):
        """同キーへの再 upsert は値を上書きする（INSERT...ON CONFLICT DO UPDATE）。"""
        from api.repositories.monthly_usage import upsert_usage

        user = _create_user(db_session)
        upsert_usage(
            db_session,
            user_id=user.id,
            site=SiteType.AMAZON,
            recorded_month=CURRENT_MONTH,
            amount_spent=1000,
            points_earned=10,
            shop_count=0,
        )
        result = upsert_usage(
            db_session,
            user_id=user.id,
            site=SiteType.AMAZON,
            recorded_month=CURRENT_MONTH,
            amount_spent=9999,
            points_earned=99,
            shop_count=3,
        )
        # DB 行は 1 つのまま
        rows = (
            db_session.query(MonthlyUsage)
            .filter_by(user_id=user.id, site=SiteType.AMAZON)
            .all()
        )
        assert len(rows) == 1
        assert result.amount_spent == 9999
        assert result.points_earned == 99
        assert result.shop_count == 3

    def test_should_maintain_separate_records_per_site(self, db_session):
        """サイトごとに別レコードとして保存される。"""
        from api.repositories.monthly_usage import upsert_usage

        user = _create_user(db_session)
        for site in [SiteType.AMAZON, SiteType.RAKUTEN, SiteType.YAHOO]:
            upsert_usage(
                db_session,
                user_id=user.id,
                site=site,
                recorded_month=CURRENT_MONTH,
                amount_spent=1000,
                points_earned=10,
                shop_count=0,
            )

        rows = (
            db_session.query(MonthlyUsage)
            .filter_by(user_id=user.id, recorded_month=CURRENT_MONTH)
            .all()
        )
        assert len(rows) == 3

    def test_should_cascade_delete_when_user_is_deleted(self, db_session):
        """User 削除時に MonthlyUsage も自動削除される（ON DELETE CASCADE）。"""
        from api.repositories.monthly_usage import upsert_usage

        user = _create_user(db_session)
        upsert_usage(
            db_session,
            user_id=user.id,
            site=SiteType.AMAZON,
            recorded_month=CURRENT_MONTH,
            amount_spent=5000,
            points_earned=50,
            shop_count=0,
        )
        assert db_session.query(MonthlyUsage).filter_by(user_id=user.id).count() == 1

        # When: User を削除
        db_session.query(User).filter_by(id=user.id).delete()
        db_session.commit()

        # Then: MonthlyUsage も自動削除
        assert db_session.query(MonthlyUsage).filter_by(user_id=user.id).count() == 0
