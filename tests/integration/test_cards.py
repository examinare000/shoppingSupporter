"""Tests for GET /api/cards and the cards seed script.

Spec: docs/plans/phase1-foundation.md (T-04)
Plan: .takt/runs/20260504-161546-docs-plans-phase1-foundation-m/reports/plan.md

Layered as:
- Endpoint integration tests via FastAPI TestClient that exercise routing,
  list/detail behavior, ordering contract, response shape, public access,
  and 404/422 boundaries.
- Seed integration tests that drive `api.common.seed.cards.seed_cards(db)`
  against the same Postgres test container and assert the documented seed
  contents and idempotency.

Why integration (not unit): all behavior under test crosses the SQLAlchemy
ORM boundary into Postgres, where JSON column round-tripping and the
ordering contract are observable. Mocking the session would only re-test
SQLAlchemy itself.
"""

from __future__ import annotations

from api.common.models import Card, SiteType
from api.common.seed.cards import CARDS_SEED_DATA, seed_cards


LIST_ENDPOINT = "/api/cards"


def _detail_endpoint(card_id) -> str:
    return f"/api/cards/{card_id}"


# Source of truth for the camelCase response shape. Asserting on this set
# (rather than each key individually) lets a single test detect both
# missing and unexpected keys.
EXPECTED_CARD_KEYS = {
    "id",
    "name",
    "baseRewardRate",
    "annualFee",
    "specialRewards",
}


# Fixed names per docs/plans/phase1-foundation.md T-04 と
# docs/plans/user-profile-enhancement.md §2.2 によるシード校正。
# 楽天プレミアムカードは楽天カードの直後に挿入する（ファミリー隣接）。
# tests/integration/test_cards.py は `CARDS_SEED_DATA` の name 列を
# このリストと厳密一致で比較するため、seed 側のリネームは即検出される。
EXPECTED_SEED_NAMES = [
    "楽天カード",
    "楽天プレミアムカード",
    "Amazon Mastercard",
    "Yahoo! JAPAN カード",
    "一般 1% 還元カード",
]


def _seed(session, cards):
    for card in cards:
        session.add(card)
    session.commit()


# ---------------------------------------------------------------------------
# GET /api/cards (list)
# ---------------------------------------------------------------------------


class TestEndpointList:
    def test_should_return_empty_array_when_no_cards(self, client):
        # Given: an empty cards table (per-test _clean_db fixture)
        # When: hitting the list endpoint
        response = client.get(LIST_ENDPOINT)

        # Then: 200 + bare empty array (no envelope per planner decision)
        assert response.status_code == 200
        assert response.json() == []

    def test_should_return_all_cards(self, client, db_session, make_card):
        # Given: four cards in the table
        _seed(
            db_session,
            [
                make_card(name="A"),
                make_card(name="B"),
                make_card(name="C"),
                make_card(name="D"),
            ],
        )

        # When: hitting the list endpoint
        response = client.get(LIST_ENDPOINT)

        # Then: every row is returned
        body = response.json()
        assert response.status_code == 200
        assert isinstance(body, list)
        assert len(body) == 4

    def test_should_order_by_id_ascending(self, client, db_session, make_card):
        # Given: cards inserted in non-id order (insertion order != id order
        # only matters once we have an autoincrement id; we stage three rows
        # to make any ordering-by-insertion bug visible)
        _seed(
            db_session,
            [
                make_card(name="first"),
                make_card(name="second"),
                make_card(name="third"),
            ],
        )

        # When: requesting the list twice
        first = client.get(LIST_ENDPOINT).json()
        second = client.get(LIST_ENDPOINT).json()

        # Then: both responses are sorted by id ascending and are stable
        ids = [item["id"] for item in first]
        assert ids == sorted(ids)
        assert first == second

    def test_should_expose_exactly_camelcase_keys_per_item(
        self, client, db_session, make_card
    ):
        # Given: a card with every field populated
        _seed(
            db_session,
            [
                make_card(
                    name="楽天カード",
                    base_reward_rate=1.0,
                    annual_fee=0,
                    special_rewards={"rakuten": 1.0},
                )
            ],
        )

        # When: hitting the list endpoint
        response = client.get(LIST_ENDPOINT)

        # Then: each item exposes exactly the camelCase contract keys
        body = response.json()
        assert len(body) == 1
        item = body[0]
        assert set(item.keys()) == EXPECTED_CARD_KEYS

    def test_should_use_camelcase_spelling_not_snakecase(
        self, client, db_session, make_card
    ):
        # Given: a card with non-default values so swapped keys are visible
        _seed(
            db_session,
            [
                make_card(
                    name="annual paid",
                    base_reward_rate=1.5,
                    annual_fee=11000,
                    special_rewards={"rakuten": 2.0},
                )
            ],
        )

        # When: hitting the list endpoint
        response = client.get(LIST_ENDPOINT)

        # Then: the camelCase spellings carry the values (and snake_case
        # variants are absent — guards against a half-migrated alias config)
        item = response.json()[0]
        assert item["baseRewardRate"] == 1.5
        assert item["annualFee"] == 11000
        assert item["specialRewards"] == {"rakuten": 2.0}
        assert "base_reward_rate" not in item
        assert "annual_fee" not in item
        assert "special_rewards" not in item


# ---------------------------------------------------------------------------
# GET /api/cards/{id} (detail)
# ---------------------------------------------------------------------------


class TestEndpointDetail:
    def test_should_return_single_card_when_id_exists(
        self, client, db_session, make_card
    ):
        # Given: one persisted card
        card = make_card(
            name="楽天カード",
            base_reward_rate=1.0,
            annual_fee=0,
            special_rewards={"rakuten": 1.0},
        )
        _seed(db_session, [card])

        # When: requesting the detail by id
        response = client.get(_detail_endpoint(card.id))

        # Then: the response is a single object (not wrapped) with the
        # documented camelCase fields and matching values
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)
        assert set(body.keys()) == EXPECTED_CARD_KEYS
        assert body["id"] == card.id
        assert body["name"] == "楽天カード"
        assert body["baseRewardRate"] == 1.0
        assert body["annualFee"] == 0
        assert body["specialRewards"] == {"rakuten": 1.0}

    def test_should_return_404_when_id_does_not_exist(
        self, client, db_session, make_card
    ):
        # Given: a single unrelated card so the table is non-empty (proves
        # the 404 is about the requested id, not about an empty table)
        _seed(db_session, [make_card(name="someone-else")])

        # When: requesting an id that has not been issued
        response = client.get(_detail_endpoint(99999))

        # Then: 404 (must not silently fall back to 200 + null/empty)
        assert response.status_code == 404

    def test_should_return_404_when_table_is_empty(self, client):
        # Given: empty cards table
        # When: requesting any id
        response = client.get(_detail_endpoint(1))

        # Then: 404 (not 200 + null)
        assert response.status_code == 404

    def test_should_return_422_when_id_is_not_an_integer(self, client):
        # When: requesting with a non-integer path parameter
        response = client.get(_detail_endpoint("abc"))

        # Then: FastAPI's path-parameter validation surfaces 422 (not 404)
        # so callers can distinguish bad input from a missing resource.
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Authentication contract
# ---------------------------------------------------------------------------


class TestEndpointPublic:
    """Read endpoints must be reachable without an Authorization header.

    Per docs/plans/phase1-foundation.md T-04, only write endpoints are
    admin-restricted; GET stays public so the frontend can render the card
    catalog before login.
    """

    def test_list_should_not_require_authentication(
        self, client, db_session, make_card
    ):
        # Given: at least one card so 200 is meaningful
        _seed(db_session, [make_card(name="public-list")])

        # When: calling without any auth header
        response = client.get(LIST_ENDPOINT)

        # Then: 200 (not 401/403)
        assert response.status_code == 200

    def test_detail_should_not_require_authentication(
        self, client, db_session, make_card
    ):
        # Given: a persisted card
        card = make_card(name="public-detail")
        _seed(db_session, [card])

        # When: calling without any auth header
        response = client.get(_detail_endpoint(card.id))

        # Then: 200 (not 401/403)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# api/common/seed/cards.py
# ---------------------------------------------------------------------------


class TestSeedCards:
    def test_should_insert_exactly_five_rows_into_empty_table(self, db_session):
        # Given: empty cards table
        assert db_session.query(Card).count() == 0

        # When: running the seed
        seed_cards(db_session)

        # Then: 5 rows are present。docs/plans/user-profile-enhancement.md §2.2
        # により楽天プレミアムカードを追加した。T-04 の元基準（4 件）は
        # この校正で 5 件に置き換わるため、テスト名・件数を本値に更新する。
        assert db_session.query(Card).count() == 5

    def test_should_insert_the_documented_card_names_verbatim(self, db_session):
        # When: running the seed against an empty table
        seed_cards(db_session)

        # Then: the names are the four spec strings, in spec order
        names = [c.name for c in db_session.query(Card).order_by(Card.id).all()]
        assert names == EXPECTED_SEED_NAMES

    def test_seed_data_constant_should_match_documented_names(self):
        # Given: the module-level CARDS_SEED_DATA constant (the source of
        # truth that the seed function iterates over)
        # Then: the spec names appear in spec order. Asserting on the
        # constant — not just the post-insert rows — makes a rename in
        # CARDS_SEED_DATA fail this test even before a DB round trip.
        assert [row["name"] for row in CARDS_SEED_DATA] == EXPECTED_SEED_NAMES

    def test_seed_data_constant_should_match_documented_special_rewards(self):
        # Why: 2025/2026 年 SPU / Amazon Mastercard 仕様の最新還元率を
        # 契約として固定する（docs/plans/user-profile-enhancement.md §2.2）。
        # 還元率は T-06 ポイント算出ロジックの入力値そのものなので、
        # シード段階での値ズレを seed 直値で検出できるようにする。
        # 値は CARDS_SEED_DATA を直接 dict 検査する（DB 経路を経由しなくても
        # 契約違反が観測できるよう、定数に対して直接 assert する）。
        by_name = {row["name"]: row for row in CARDS_SEED_DATA}
        assert by_name["楽天カード"]["special_rewards"] == {"rakuten": 2.0}
        assert by_name["楽天プレミアムカード"]["special_rewards"] == {"rakuten": 4.0}
        assert by_name["楽天プレミアムカード"]["base_reward_rate"] == 1.0
        assert by_name["楽天プレミアムカード"]["annual_fee"] == 11000
        assert by_name["Amazon Mastercard"]["special_rewards"] == {"amazon": 1.5}
        # 据え置き対象（誤って編集されていないか確認）
        assert by_name["Yahoo! JAPAN カード"]["special_rewards"] == {"yahoo": 1.0}
        assert by_name["一般 1% 還元カード"]["special_rewards"] == {}

    def test_special_rewards_keys_should_be_valid_site_types_or_empty(
        self, db_session
    ):
        # When: running the seed
        seed_cards(db_session)

        # Then: every persisted card's special_rewards has only SiteType
        # values as keys (or is an empty dict for the generic card).
        # This is the structural contract that docs/api/cards.md will
        # publish; T-06's pricing logic depends on it.
        valid_keys = {site.value for site in SiteType}
        for card in db_session.query(Card).all():
            assert isinstance(card.special_rewards, dict)
            assert set(card.special_rewards.keys()).issubset(valid_keys)

    def test_should_be_idempotent_when_run_twice(self, db_session):
        # Given: the seed has already been applied once
        seed_cards(db_session)
        first_count = db_session.query(Card).count()
        first_ids = [c.id for c in db_session.query(Card).order_by(Card.id).all()]

        # When: running it again
        seed_cards(db_session)

        # Then: the row count is unchanged (no duplicate inserts) and the
        # existing primary keys are preserved (no destructive re-seed,
        # which would invalidate UserProfile.default_card_id FKs in T-05)
        assert db_session.query(Card).count() == first_count
        second_ids = [c.id for c in db_session.query(Card).order_by(Card.id).all()]
        assert second_ids == first_ids

    def test_should_skip_when_any_card_already_exists(
        self, db_session, make_card
    ):
        # Given: a single pre-existing card placed by some other path
        # (e.g. a manual insert in a prior environment)
        _seed(db_session, [make_card(name="pre-existing")])

        # When: running the seed
        seed_cards(db_session)

        # Then: the seed treats "non-empty table" as "already seeded" and
        # does not append the 4 spec rows on top. This matches the planner's
        # explicit choice (count==0 gate) and avoids accidental duplication
        # when no unique constraint exists on cards.name.
        assert db_session.query(Card).count() == 1
        assert db_session.query(Card).one().name == "pre-existing"
