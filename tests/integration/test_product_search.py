"""Tests for GET /api/products/search.

Spec: .takt/runs/20260503-153723-get-api-products-search/context/task/order.md
Plan: .takt/runs/20260503-153723-get-api-products-search/reports/plan.md

Layered as:
- Repository unit tests against `search_products(db, params)` in
  `api.repositories.products`. These exercise FTS, trigram fuzzy match,
  filters, sort, and pagination directly against Postgres.
- Endpoint integration tests via FastAPI TestClient that exercise routing,
  validation handling, response envelope shape, and end-to-end behavior.

The endpoint contract differs from any prior `/api/products/search`
implementation:
- Validation failures return 422 (not 200 + []).
- Response is a `{items, page, totalPages, totalCount}` envelope (not a
  bare array).
- Query params are `q`, `inStock`, `priceMin`, `priceMax`, `sort`, `page`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from api.common.models import RakutenRank, UserProfile
from api.repositories.products import SearchParams, search_products


ENDPOINT = "/api/products/search"
SIGNUP_ENDPOINT = "/api/auth/signup"
LOGIN_ENDPOINT = "/api/auth/login"

# Source of truth for the camelCase response item shape. Asserting on this
# set (rather than each key individually) lets a single test detect both
# missing and unexpected keys.
# `listings` was added as part of T-08 personalization integration.
EXPECTED_ITEM_KEYS = {
    "id",
    "name",
    "description",
    "imageUrl",
    "tags",
    "inStock",
    "currentPrice",
    "listings",
}

# `meta` was added as part of T-08 personalization integration.
EXPECTED_ENVELOPE_KEYS = {"items", "page", "totalPages", "totalCount", "meta"}

# Source of truth for the nested listing shape within each item.
EXPECTED_LISTING_KEYS = {
    "siteType",
    "siteProductId",
    "url",
    "points",
    "effectivePrice",
    "breakdown",
}

# Source of truth for each breakdown entry within a listing.
EXPECTED_BREAKDOWN_ENTRY_KEYS = {"label", "rate", "points", "note"}

# Source of truth for the meta.personalization shape.
EXPECTED_META_KEYS = {"personalization"}
EXPECTED_PERSONALIZATION_KEYS = {"applied", "rakutenRank", "hasCard"}


def _seed(session, products):
    for product in products:
        session.add(product)
    session.commit()


def _params(
    q,
    *,
    in_stock=None,
    price_min=None,
    price_max=None,
    sort="relevance",
    page=1,
):
    """Build a `SearchParams` with explicit defaults.

    Snake-case kwargs match Pythonic SearchParams field names; the camelCase
    URL parameters (`inStock` etc.) are translated by the FastAPI handler.
    """
    return SearchParams(
        q=q,
        in_stock=in_stock,
        price_min=price_min,
        price_max=price_max,
        sort=sort,
        page=page,
    )


# ---------------------------------------------------------------------------
# Repository unit tests: search_products(db, params) -> (items, total_count)
# ---------------------------------------------------------------------------


class TestRepositoryFullTextSearch:
    def test_should_match_full_word_in_name(self, db_session, make_product):
        # Given: products with one full-word match in `name`
        _seed(
            db_session,
            [
                make_product(name="リンゴジュース"),
                make_product(name="バナナケーキ"),
            ],
        )

        # When: searching by a word contained in one product's name
        items, total = search_products(db_session, _params("リンゴ"))

        # Then: only the matching product is returned, and total_count agrees
        assert total == 1
        assert [p.name for p in items] == ["リンゴジュース"]

    def test_should_match_full_word_in_description(self, db_session, make_product):
        # Given: a product whose only match is in the description
        _seed(
            db_session,
            [
                make_product(name="無関係", description="apple flavored juice"),
                make_product(name="banana", description="just a banana"),
            ],
        )

        # When: searching with a description-only keyword
        items, total = search_products(db_session, _params("apple"))

        # Then: the product is returned via description match
        assert total == 1
        assert items[0].name == "無関係"

    def test_should_match_tag_content(self, db_session, make_product):
        # Given: products with disjoint tag sets
        _seed(
            db_session,
            [
                make_product(name="商品A", tags=["organic", "fruit"]),
                make_product(name="商品B", tags=["dairy"]),
            ],
        )

        # When: searching with a keyword present only in tags
        items, total = search_products(db_session, _params("organic"))

        # Then: the tag-matched product is returned
        assert total == 1
        assert items[0].name == "商品A"

    def test_should_return_empty_when_no_match(self, db_session, make_product):
        _seed(db_session, [make_product(name="apple")])
        items, total = search_products(db_session, _params("totally-unrelated-term"))
        assert items == []
        assert total == 0

    def test_should_handle_null_description_without_error(
        self, db_session, make_product
    ):
        # Given: a product with NULL description but matching name
        _seed(db_session, [make_product(name="apple", description=None)])

        # When: searching by a name-matching keyword
        items, total = search_products(db_session, _params("apple"))

        # Then: NULL description does not break the FTS / trigram concat
        assert total == 1
        assert items[0].name == "apple"


class TestRepositoryTrigramFuzzyMatch:
    def test_should_match_typo_via_trigram(self, db_session, make_product):
        # Given: a product whose name differs from the query by one character
        _seed(db_session, [make_product(name="strawberry")])

        # When: searching with a single-character typo
        items, total = search_products(db_session, _params("strawbery"))

        # Then: trigram similarity yields a match (FTS alone would miss this)
        assert total == 1
        assert items[0].name == "strawberry"

    def test_should_not_match_completely_unrelated_term(
        self, db_session, make_product
    ):
        # Given: a product
        _seed(db_session, [make_product(name="apple")])

        # When: searching with a term sharing no trigrams above threshold
        items, total = search_products(db_session, _params("xyz"))

        # Then: the trigram threshold filters it out
        assert items == []
        assert total == 0


class TestRepositoryFilterInStock:
    def test_should_return_only_in_stock_when_true(self, db_session, make_product):
        _seed(
            db_session,
            [
                make_product(name="apple A", in_stock=True),
                make_product(name="apple B", in_stock=False),
            ],
        )
        items, total = search_products(db_session, _params("apple", in_stock=True))
        assert total == 1
        assert [p.name for p in items] == ["apple A"]

    def test_should_return_only_out_of_stock_when_false(
        self, db_session, make_product
    ):
        _seed(
            db_session,
            [
                make_product(name="apple A", in_stock=True),
                make_product(name="apple B", in_stock=False),
            ],
        )
        items, total = search_products(db_session, _params("apple", in_stock=False))
        assert total == 1
        assert [p.name for p in items] == ["apple B"]

    def test_should_return_both_when_filter_unset(self, db_session, make_product):
        # Given: products at both stock states
        _seed(
            db_session,
            [
                make_product(name="apple A", in_stock=True),
                make_product(name="apple B", in_stock=False),
            ],
        )

        # When: in_stock is None (filter unset)
        _, total = search_products(db_session, _params("apple", in_stock=None))

        # Then: both products are counted (filter not applied)
        assert total == 2


class TestRepositoryFilterPrice:
    @pytest.fixture
    def priced(self, db_session, make_product):
        _seed(
            db_session,
            [
                make_product(name="apple cheap", current_price=500),
                make_product(name="apple mid", current_price=1500),
                make_product(name="apple expensive", current_price=5000),
            ],
        )

    def test_should_filter_by_price_min_inclusive(self, db_session, priced):
        items, total = search_products(db_session, _params("apple", price_min=1500))
        names = sorted(p.name for p in items)
        assert names == ["apple expensive", "apple mid"]
        assert total == 2

    def test_should_filter_by_price_max_inclusive(self, db_session, priced):
        items, total = search_products(db_session, _params("apple", price_max=1500))
        names = sorted(p.name for p in items)
        assert names == ["apple cheap", "apple mid"]
        assert total == 2

    def test_should_filter_by_price_range(self, db_session, priced):
        items, total = search_products(
            db_session, _params("apple", price_min=1000, price_max=2000)
        )
        assert total == 1
        assert items[0].name == "apple mid"

    def test_should_exclude_products_with_null_current_price_when_filtered(
        self, db_session, make_product
    ):
        # Given: products with and without current_price
        _seed(
            db_session,
            [
                make_product(name="apple priced", current_price=1000),
                make_product(name="apple unpriced", current_price=None),
            ],
        )

        # When: any price filter is applied
        items, total = search_products(db_session, _params("apple", price_min=0))

        # Then: NULL current_price products are excluded by the price predicate
        # (NULL comparisons fail; products without a price cannot satisfy a
        # numeric range filter)
        assert total == 1
        assert items[0].name == "apple priced"


class TestRepositorySort:
    def test_should_sort_price_ascending(self, db_session, make_product):
        _seed(
            db_session,
            [
                make_product(name="apple A", current_price=3000),
                make_product(name="apple B", current_price=1000),
                make_product(name="apple C", current_price=2000),
            ],
        )
        items, _ = search_products(db_session, _params("apple", sort="price_asc"))
        assert [p.current_price for p in items] == [1000, 2000, 3000]

    def test_should_sort_price_descending(self, db_session, make_product):
        _seed(
            db_session,
            [
                make_product(name="apple A", current_price=3000),
                make_product(name="apple B", current_price=1000),
                make_product(name="apple C", current_price=2000),
            ],
        )
        items, _ = search_products(db_session, _params("apple", sort="price_desc"))
        assert [p.current_price for p in items] == [3000, 2000, 1000]

    def test_should_sort_newest_first(self, db_session, make_product):
        # Given: products with distinct created_at timestamps
        now = datetime.utcnow()
        old = make_product(name="apple old")
        old.created_at = now - timedelta(days=2)
        mid = make_product(name="apple mid")
        mid.created_at = now - timedelta(days=1)
        new = make_product(name="apple new")
        new.created_at = now
        _seed(db_session, [old, new, mid])

        # When: sorting by newest
        items, _ = search_products(db_session, _params("apple", sort="newest"))

        # Then: results are in descending created_at order
        assert [p.name for p in items] == ["apple new", "apple mid", "apple old"]

    def test_relevance_sort_should_rank_exact_match_above_fuzzy_match(
        self, db_session, make_product
    ):
        # Given: an exact-match product and a fuzzy/typo-distance product
        _seed(
            db_session,
            [
                make_product(name="apple"),
                make_product(name="appel"),
            ],
        )

        # When: sorting by relevance (default)
        items, total = search_products(db_session, _params("apple", sort="relevance"))

        # Then: exact match outranks the typo neighbor
        assert total == 2
        assert items[0].name == "apple"


class TestRepositoryPagination:
    PAGE_SIZE = 10

    def test_should_return_at_most_page_size_items(self, db_session, make_product):
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(15)])
        items, total = search_products(db_session, _params("apple", page=1))
        assert len(items) == self.PAGE_SIZE
        # total_count is the unpaginated total, not the page slice size
        assert total == 15

    def test_should_return_remainder_on_final_page(self, db_session, make_product):
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(15)])
        items, total = search_products(db_session, _params("apple", page=2))
        assert len(items) == 5
        assert total == 15

    def test_should_return_empty_when_page_beyond_total(
        self, db_session, make_product
    ):
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(5)])
        items, total = search_products(db_session, _params("apple", page=99))
        assert items == []
        # total is still the unpaginated total even when the page is empty
        assert total == 5


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------


class TestEndpointEnvelopeShape:
    def test_should_return_envelope_with_expected_top_level_keys(
        self, client, db_session, make_product
    ):
        _seed(db_session, [make_product(name="apple")])
        response = client.get(ENDPOINT, params={"q": "apple"})
        assert response.status_code == 200
        body = response.json()
        # envelope is an object, not a bare array
        assert isinstance(body, dict)
        assert set(body.keys()) == EXPECTED_ENVELOPE_KEYS

    def test_should_expose_camelcase_summary_keys_in_items(
        self, client, db_session, make_product
    ):
        # Given: a fully populated product so all fields are non-null
        _seed(
            db_session,
            [
                make_product(
                    name="apple",
                    description="a red fruit",
                    image_url="https://example.com/a.png",
                    tags=["fruit", "fresh"],
                    in_stock=True,
                    current_price=300,
                ),
            ],
        )

        # When: hitting the endpoint
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: every item exposes exactly the camelCase summary fields
        body = response.json()
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert set(item.keys()) == EXPECTED_ITEM_KEYS
        # spot-check that camelCase is actually used (not snake_case)
        assert item["imageUrl"] == "https://example.com/a.png"
        assert item["inStock"] is True
        assert item["currentPrice"] == 300


class TestEndpointPagination:
    PAGE_SIZE = 10

    def test_should_apply_fixed_page_size_of_10(
        self, client, db_session, make_product
    ):
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(25)])

        response = client.get(ENDPOINT, params={"q": "apple"})

        body = response.json()
        assert len(body["items"]) == self.PAGE_SIZE
        assert body["totalCount"] == 25
        assert body["totalPages"] == 3
        assert body["page"] == 1

    def test_should_return_remainder_on_last_page(
        self, client, db_session, make_product
    ):
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(25)])

        response = client.get(ENDPOINT, params={"q": "apple", "page": 3})

        body = response.json()
        assert len(body["items"]) == 5
        assert body["page"] == 3
        assert body["totalPages"] == 3

    def test_should_compute_totalPages_on_exact_multiple(
        self, client, db_session, make_product
    ):
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(20)])

        response = client.get(ENDPOINT, params={"q": "apple"})

        body = response.json()
        assert body["totalCount"] == 20
        assert body["totalPages"] == 2

    def test_should_report_zero_totalPages_when_no_match(self, client):
        # Given: no products
        # When: a query that matches nothing
        response = client.get(ENDPOINT, params={"q": "apple"})

        body = response.json()
        assert response.status_code == 200
        assert body["items"] == []
        assert body["totalCount"] == 0
        assert body["totalPages"] == 0

    def test_should_default_page_to_1_when_omitted(
        self, client, db_session, make_product
    ):
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(15)])
        response = client.get(ENDPOINT, params={"q": "apple"})
        body = response.json()
        assert body["page"] == 1

    def test_should_return_empty_items_when_page_beyond_total(
        self, client, db_session, make_product
    ):
        _seed(db_session, [make_product(name="apple")])
        response = client.get(ENDPOINT, params={"q": "apple", "page": 999})
        body = response.json()
        assert body["items"] == []
        assert body["totalCount"] == 1
        # `page` echoes the request page even when no items exist there;
        # the client decides whether to redirect/clamp.
        assert body["page"] == 999


class TestEndpointFilters:
    def test_should_apply_inStock_filter(self, client, db_session, make_product):
        _seed(
            db_session,
            [
                make_product(name="apple A", in_stock=True),
                make_product(name="apple B", in_stock=False),
            ],
        )

        response = client.get(ENDPOINT, params={"q": "apple", "inStock": "true"})

        body = response.json()
        assert body["totalCount"] == 1
        assert [i["name"] for i in body["items"]] == ["apple A"]

    def test_should_apply_priceMin_and_priceMax_together(
        self, client, db_session, make_product
    ):
        _seed(
            db_session,
            [
                make_product(name="apple cheap", current_price=500),
                make_product(name="apple mid", current_price=1500),
                make_product(name="apple expensive", current_price=5000),
            ],
        )

        response = client.get(
            ENDPOINT,
            params={"q": "apple", "priceMin": 1000, "priceMax": 2000},
        )

        body = response.json()
        assert body["totalCount"] == 1
        assert body["items"][0]["name"] == "apple mid"


class TestEndpointSort:
    def test_should_apply_price_asc_sort(self, client, db_session, make_product):
        _seed(
            db_session,
            [
                make_product(name="apple A", current_price=3000),
                make_product(name="apple B", current_price=1000),
            ],
        )
        response = client.get(ENDPOINT, params={"q": "apple", "sort": "price_asc"})
        body = response.json()
        assert [i["currentPrice"] for i in body["items"]] == [1000, 3000]

    def test_should_apply_price_desc_sort(self, client, db_session, make_product):
        _seed(
            db_session,
            [
                make_product(name="apple A", current_price=3000),
                make_product(name="apple B", current_price=1000),
            ],
        )
        response = client.get(ENDPOINT, params={"q": "apple", "sort": "price_desc"})
        body = response.json()
        assert [i["currentPrice"] for i in body["items"]] == [3000, 1000]

    def test_should_default_sort_to_relevance_when_omitted(
        self, client, db_session, make_product
    ):
        # Given: several matching products
        _seed(
            db_session,
            [
                make_product(name="apple"),
                make_product(name="apple sauce"),
                make_product(name="green apple"),
            ],
        )

        # When: sort omitted vs. explicit sort=relevance
        default_response = client.get(ENDPOINT, params={"q": "apple"})
        explicit_response = client.get(
            ENDPOINT, params={"q": "apple", "sort": "relevance"}
        )

        # Then: both produce the same ordering (omitted == relevance)
        assert default_response.json()["items"] == explicit_response.json()["items"]


class TestEndpointTagSearch:
    def test_should_match_query_against_tags_end_to_end(
        self, client, db_session, make_product
    ):
        _seed(
            db_session,
            [
                make_product(name="商品A", tags=["organic", "fruit"]),
                make_product(name="商品B", tags=["dairy"]),
            ],
        )
        response = client.get(ENDPOINT, params={"q": "organic"})
        body = response.json()
        assert body["totalCount"] == 1
        assert body["items"][0]["name"] == "商品A"


class TestEndpointTrigram:
    def test_should_match_typo_query_end_to_end(
        self, client, db_session, make_product
    ):
        _seed(db_session, [make_product(name="strawberry")])
        response = client.get(ENDPOINT, params={"q": "strawbery"})
        body = response.json()
        assert body["totalCount"] >= 1
        assert "strawberry" in [i["name"] for i in body["items"]]


class TestEndpointAuthentication:
    def test_should_not_require_authentication(
        self, client, db_session, make_product
    ):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: calling without any auth header
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: 200 (endpoint is public per planner decision)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Validation (422) tests
# ---------------------------------------------------------------------------


class TestEndpointValidationErrors:
    """All validation failures must surface as 422.

    The contract returns FastAPI's standard 422 so callers can detect bad
    input rather than mistaking it for an empty result set.
    """

    def test_should_return_422_when_q_missing(self, client):
        response = client.get(ENDPOINT)
        assert response.status_code == 422

    def test_should_return_422_when_q_is_empty_string(self, client):
        response = client.get(ENDPOINT, params={"q": ""})
        assert response.status_code == 422

    def test_should_return_422_when_q_exceeds_max_length(self, client):
        response = client.get(ENDPOINT, params={"q": "a" * 101})
        assert response.status_code == 422

    def test_should_return_422_when_priceMin_greater_than_priceMax(self, client):
        response = client.get(
            ENDPOINT,
            params={"q": "apple", "priceMin": 5000, "priceMax": 1000},
        )
        assert response.status_code == 422

    def test_should_return_422_when_priceMin_non_numeric(self, client):
        response = client.get(
            ENDPOINT, params={"q": "apple", "priceMin": "abc"}
        )
        assert response.status_code == 422

    def test_should_return_422_when_priceMax_non_numeric(self, client):
        response = client.get(
            ENDPOINT, params={"q": "apple", "priceMax": "abc"}
        )
        assert response.status_code == 422

    def test_should_return_422_when_priceMin_negative(self, client):
        response = client.get(ENDPOINT, params={"q": "apple", "priceMin": -1})
        assert response.status_code == 422

    def test_should_return_422_when_priceMax_negative(self, client):
        response = client.get(ENDPOINT, params={"q": "apple", "priceMax": -1})
        assert response.status_code == 422

    def test_should_return_422_when_sort_value_not_in_allowed_set(self, client):
        response = client.get(
            ENDPOINT, params={"q": "apple", "sort": "popularity"}
        )
        assert response.status_code == 422

    def test_should_return_422_when_page_zero(self, client):
        response = client.get(ENDPOINT, params={"q": "apple", "page": 0})
        assert response.status_code == 422

    def test_should_return_422_when_page_negative(self, client):
        response = client.get(ENDPOINT, params={"q": "apple", "page": -1})
        assert response.status_code == 422

    def test_should_return_422_when_page_non_numeric(self, client):
        response = client.get(ENDPOINT, params={"q": "apple", "page": "abc"})
        assert response.status_code == 422


class TestEndpointQueryStringContract:
    """`q` and the other params must come from the query string.

    These tests guard against an implementation that accidentally reads
    the request body or treats response-envelope keys as input.
    """

    def test_should_return_422_when_q_only_provided_in_body(self, client):
        # When: q is sent as a JSON body but missing from the query string
        response = client.request("GET", ENDPOINT, json={"q": "apple"})

        # Then: body is ignored; q is missing from query string -> 422
        assert response.status_code == 422

    def test_should_ignore_response_envelope_shaped_body(self, client):
        # Given: a body that mimics the response envelope (a way the impl
        # might accidentally re-use the response shape for input parsing)
        envelope_shaped_body = {
            "items": [{"q": "apple"}],
            "page": 1,
            "totalCount": 0,
            "totalPages": 0,
        }

        # When: posting it as the request body of a GET
        response = client.request("GET", ENDPOINT, json=envelope_shaped_body)

        # Then: the envelope is not interpreted as input; q is missing -> 422
        assert response.status_code == 422

    def test_should_ignore_filter_values_provided_in_body(self, client):
        # Given: invalid filter values in the request body, valid q on the
        # query string. If the impl read priceMin/priceMax from the body,
        # the non-numeric values would trigger a 422.
        response = client.request(
            "GET",
            ENDPOINT,
            params={"q": "apple"},
            json={"priceMin": "abc", "priceMax": "abc"},
        )

        # Then: the body is ignored and the request succeeds because the
        # only required input (q) comes from the query string.
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Helpers for T-08 personalization tests
# ---------------------------------------------------------------------------


def _signup(client, *, email: str, password: str):
    return client.post(SIGNUP_ENDPOINT, json={"email": email, "password": password})


def _login(client, *, email: str, password: str):
    return client.post(LOGIN_ENDPOINT, json={"email": email, "password": password})


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_token(client):
    """認証済みユーザーを作成し JWT を返す。パーソナライズテスト用。

    別テストクラスで同名フィクスチャ (test_profile.py の auth_token) が
    あるが、pytest のモジュールスコープにより互いに干渉しない。
    """
    email = "search.user@example.com"
    password = "SearchPass1!"
    signup = _signup(client, email=email, password=password)
    assert signup.status_code == 201
    login = _login(client, email=email, password=password)
    assert login.status_code == 200
    return {
        "token": login.json()["accessToken"],
        "user_id": uuid.UUID(signup.json()["id"]),
    }


@pytest.fixture
def seeded_card(db_session, make_card):
    """楽天カード（SPU 2%）を永続化して返す。

    Why special_rewards={"rakuten": 2.0}:
        price=1000 円のときポイント計算が
        ストア 1% (10pt) + SPU 2% (20pt) = 30pt, 実質価格 970 円
        という端数なしのきれいな値になり、テストで断言しやすい。
        test_profile.py の seeded_card ({"rakuten": 1.0}) とは別の
        モジュールスコープのフィクスチャなので干渉しない。
    """
    card = make_card(
        name="楽天カード",
        base_reward_rate=1.0,
        annual_fee=0,
        special_rewards={"rakuten": 2.0},
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    return card


# ---------------------------------------------------------------------------
# T-08: meta フィールドの形（未認証でも meta は常に返る）
# ---------------------------------------------------------------------------


class TestEndpointMetaShape:
    """meta フィールドの構造を固定する。

    meta は認証有無に関わらず常にレスポンスに含まれる。
    キー集合の検証を EXPECTED_*_KEYS 定数に集約し、フィールドの追加・
    削除を単一箇所で検出できるようにしている。
    """

    def test_envelope_should_include_meta_field(
        self, client, db_session, make_product
    ):
        # Given: a matching product (unauthenticated context)
        _seed(db_session, [make_product(name="apple")])

        # When: search without auth
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: meta is present at the envelope level
        assert response.status_code == 200
        assert "meta" in response.json()

    def test_envelope_should_have_exactly_expected_top_level_keys(
        self, client, db_session, make_product
    ):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: search without auth
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: envelope keys are exactly the expected set (meta included)
        assert set(response.json().keys()) == EXPECTED_ENVELOPE_KEYS

    def test_meta_should_have_exactly_personalization_key(
        self, client, db_session, make_product
    ):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: search without auth
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: meta contains exactly {"personalization"}
        meta = response.json()["meta"]
        assert set(meta.keys()) == EXPECTED_META_KEYS

    def test_personalization_should_have_required_keys(
        self, client, db_session, make_product
    ):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: search without auth
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: personalization contains exactly {applied, rakutenRank, hasCard}
        personalization = response.json()["meta"]["personalization"]
        assert set(personalization.keys()) == EXPECTED_PERSONALIZATION_KEYS

    def test_zero_results_should_still_return_meta(self, client):
        # Given: no products in DB
        # When: search that matches nothing
        response = client.get(ENDPOINT, params={"q": "totally-nonexistent-xyz"})

        # Then: 200 with empty items, meta is still present
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert "meta" in body
        assert "personalization" in body["meta"]


# ---------------------------------------------------------------------------
# T-08: listings フィールドの形
# ---------------------------------------------------------------------------


class TestEndpointListingsShape:
    """listings フィールドの構造を固定する。

    各 item には listings リストが含まれ、各 listing は EcSiteProduct 1 件に
    対応する。サイト固有メタデータ (siteType / siteProductId / url) と
    ポイント計算フィールド (points / effectivePrice / breakdown) を持つ。
    """

    def test_items_should_include_listings_field(
        self, client, db_session, make_product
    ):
        # Given: a product without any site product
        _seed(db_session, [make_product(name="apple")])

        # When: search
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: listings field is present (empty list, not null)
        items = response.json()["items"]
        assert len(items) == 1
        assert "listings" in items[0]

    def test_item_without_site_products_should_have_empty_listings(
        self, client, db_session, make_product
    ):
        # Given: a product with no EcSiteProduct rows
        _seed(db_session, [make_product(name="apple", current_price=1000)])

        # When: search
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: listings is [] (not null; list is always present, just empty)
        item = response.json()["items"][0]
        assert item["listings"] == []

    def test_listing_should_have_required_keys(
        self, client, db_session, make_product, make_site_product
    ):
        # Given: a product with one site product
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(
            make_site_product(
                product,
                "rakuten",
                site_product_id="RAKU001",
                url="https://item.rakuten.co.jp/test/RAKU001/",
            )
        )
        db_session.commit()

        # When: unauthenticated search
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: listing has exactly the expected camelCase keys
        listings = response.json()["items"][0]["listings"]
        assert len(listings) == 1
        assert set(listings[0].keys()) == EXPECTED_LISTING_KEYS

    def test_listing_should_expose_correct_site_metadata(
        self, client, db_session, make_product, make_site_product
    ):
        # Given: a rakuten site product with known identifiers
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(
            make_site_product(
                product,
                "rakuten",
                site_product_id="RAKU001",
                url="https://item.rakuten.co.jp/test/RAKU001/",
            )
        )
        db_session.commit()

        # When: search
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: siteType / siteProductId / url match the seeded values
        listing = response.json()["items"][0]["listings"][0]
        assert listing["siteType"] == "rakuten"
        assert listing["siteProductId"] == "RAKU001"
        assert listing["url"] == "https://item.rakuten.co.jp/test/RAKU001/"

    def test_product_with_multiple_site_products_should_have_multiple_listings(
        self, client, db_session, make_product, make_site_product
    ):
        # Given: one product linked to both Amazon and Rakuten
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(
            make_site_product(
                product,
                "amazon",
                site_product_id="ASIN001",
                url="https://amazon.co.jp/dp/ASIN001",
            )
        )
        db_session.add(
            make_site_product(
                product,
                "rakuten",
                site_product_id="RAKU001",
                url="https://item.rakuten.co.jp/test/RAKU001/",
            )
        )
        db_session.commit()

        # When: search
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: 2 listings, one per site
        listings = response.json()["items"][0]["listings"]
        assert len(listings) == 2
        site_types = {listing["siteType"] for listing in listings}
        assert site_types == {"amazon", "rakuten"}


# ---------------------------------------------------------------------------
# T-08: パーソナライズ動作（未認証 / 認証済み × プロフィール有無 × カード有無）
# ---------------------------------------------------------------------------


class TestEndpointPersonalizationBehavior:
    """検索パーソナライズの動作仕様。

    テスト戦略 (order.md より):
        - 未認証: applied=false, points/effectivePrice/breakdown=null
        - 認証済み・プロフィール未設定: applied=false, points=null
        - 認証済み・プロフィール設定済み・カード設定あり: applied=true, points 計算済み
        - 認証済み・プロフィール設定済み・カード未設定: applied=true, カードなし計算
        - 検索結果 0 件: items=[], meta.personalization は返る
        - 無効トークン: 401 を返さず未認証として扱う (applied=false)
    """

    def test_unauthenticated_should_have_applied_false(
        self, client, db_session, make_product
    ):
        # Given: a product (no auth)
        _seed(db_session, [make_product(name="apple")])

        # When: search without Authorization header
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: personalization is not applied
        assert response.status_code == 200
        personalization = response.json()["meta"]["personalization"]
        assert personalization["applied"] is False
        assert personalization["rakutenRank"] is None
        assert personalization["hasCard"] is False

    def test_unauthenticated_listings_should_have_null_pricing_fields(
        self, client, db_session, make_product, make_site_product
    ):
        # Given: a product with a site product, no auth
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.commit()

        # When: search without auth
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: pricing fields are null (no user to compute against)
        listing = response.json()["items"][0]["listings"][0]
        assert listing["points"] is None
        assert listing["effectivePrice"] is None
        assert listing["breakdown"] is None

    def test_invalid_token_should_not_return_401(
        self, client, db_session, make_product
    ):
        # Given: a product and an invalid JWT
        _seed(db_session, [make_product(name="apple")])

        # When: search with a malformed Bearer token
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers={"Authorization": "Bearer invalid-jwt-token"},
        )

        # Then: 200 (not 401); get_current_user_optional silently ignores bad tokens
        assert response.status_code == 200

    def test_invalid_token_should_treat_as_unauthenticated(
        self, client, db_session, make_product
    ):
        # Given: a product and an invalid JWT
        _seed(db_session, [make_product(name="apple")])

        # When: search with a malformed Bearer token
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers={"Authorization": "Bearer invalid-jwt-token"},
        )

        # Then: applied=false (treated as anonymous, not error)
        personalization = response.json()["meta"]["personalization"]
        assert personalization["applied"] is False

    def test_authenticated_without_profile_should_have_applied_false(
        self, client, db_session, make_product, make_site_product, auth_token
    ):
        # Given: authenticated user with no saved UserProfile
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.commit()

        # When: search with valid token but no profile
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: personalization not applied (no profile to read from)
        assert response.status_code == 200
        personalization = response.json()["meta"]["personalization"]
        assert personalization["applied"] is False

    def test_authenticated_without_profile_listings_should_have_null_points(
        self, client, db_session, make_product, make_site_product, auth_token
    ):
        # Given: authenticated user with no profile + site product
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.commit()

        # When: search with auth (no profile)
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: points null (no profile, no computation)
        listing = response.json()["items"][0]["listings"][0]
        assert listing["points"] is None
        assert listing["effectivePrice"] is None

    def test_authenticated_with_profile_and_card_should_have_applied_true(
        self, client, db_session, make_product, make_site_product, auth_token, seeded_card
    ):
        # Given: product + rakuten site product + profile with card
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                is_rakuten_mobile=False,
                is_paypay_linked=False,
                default_card_id=seeded_card.id,
            )
        )
        db_session.commit()

        # When: search with auth
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: personalization applied, meta reflects profile state
        assert response.status_code == 200
        personalization = response.json()["meta"]["personalization"]
        assert personalization["applied"] is True
        assert personalization["rakutenRank"] == "regular"
        assert personalization["hasCard"] is True

    def test_authenticated_with_profile_and_card_listings_should_have_points(
        self, client, db_session, make_product, make_site_product, auth_token, seeded_card
    ):
        """楽天カード (SPU 2%) × 楽天サイト × 1000 円の計算値を end-to-end で検証する。

        期待値の根拠 (engine.calculate_points_rakuten より):
            ストア 1% = floor(1000 * 0.01) = 10 pt
            SPU 2%   = floor(1000 * 0.02) = 20 pt
            total    = 30 pt
            effective = max(0, 1000 + 0 - 30) = 970 円  (送料 DB 未記録 → 0)
        """
        # Given: price=1000 product + rakuten site + profile with seeded_card (SPU 2%)
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                is_rakuten_mobile=False,
                is_paypay_linked=False,
                default_card_id=seeded_card.id,
            )
        )
        db_session.commit()

        # When: search with auth
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: points and effectivePrice match the deterministic calculation
        listing = response.json()["items"][0]["listings"][0]
        assert listing["points"] == 30
        assert listing["effectivePrice"] == 970
        assert listing["breakdown"] is not None
        assert isinstance(listing["breakdown"], list)
        assert len(listing["breakdown"]) > 0

    def test_breakdown_entries_should_have_required_keys(
        self, client, db_session, make_product, make_site_product, auth_token, seeded_card
    ):
        # Given: profile + card + site product (same setup as above)
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                is_rakuten_mobile=False,
                is_paypay_linked=False,
                default_card_id=seeded_card.id,
            )
        )
        db_session.commit()

        # When: search with auth
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: each breakdown entry has exactly {label, rate, points, note}
        breakdown = response.json()["items"][0]["listings"][0]["breakdown"]
        assert len(breakdown) > 0
        for entry in breakdown:
            assert set(entry.keys()) == EXPECTED_BREAKDOWN_ENTRY_KEYS

    def test_authenticated_with_profile_no_card_should_have_applied_true(
        self, client, db_session, make_product, make_site_product, auth_token
    ):
        # Given: profile with default_card_id=None
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.GOLD,
                is_amazon_prime=False,
                yahoo_premium=False,
                is_rakuten_mobile=False,
                is_paypay_linked=False,
                default_card_id=None,
            )
        )
        db_session.commit()

        # When: search with auth
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: applied is true (profile exists), hasCard is false
        personalization = response.json()["meta"]["personalization"]
        assert personalization["applied"] is True
        assert personalization["hasCard"] is False
        assert personalization["rakutenRank"] == "gold"

    def test_authenticated_with_profile_no_card_listings_should_have_points(
        self, client, db_session, make_product, make_site_product, auth_token
    ):
        """カードなし × 楽天サイト × 1000 円の計算値を end-to-end で検証する。

        期待値の根拠 (engine.calculate_points_rakuten より):
            ストア 1%     = floor(1000 * 0.01) = 10 pt
            カード基本 1% = floor(1000 * 1.0/100) = 10 pt  (card_base_rate=1.0 default)
            total         = 20 pt
            effective     = max(0, 1000 + 0 - 20) = 980 円
        """
        # Given: profile with no default card, rakuten site product
        product = make_product(name="apple", current_price=1000)
        _seed(db_session, [product])
        db_session.add(make_site_product(product, "rakuten"))
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                is_rakuten_mobile=False,
                is_paypay_linked=False,
                default_card_id=None,
            )
        )
        db_session.commit()

        # When: search with auth
        response = client.get(
            ENDPOINT,
            params={"q": "apple"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: points calculated with card_base_rate=1.0 (no special rewards)
        listing = response.json()["items"][0]["listings"][0]
        assert listing["points"] == 20
        assert listing["effectivePrice"] == 980

    def test_zero_results_authenticated_should_return_applied_true(
        self, client, db_session, auth_token
    ):
        # Given: authenticated user with a profile (no matching product)
        db_session.add(
            UserProfile(
                user_id=auth_token["user_id"],
                rakuten_rank=RakutenRank.REGULAR,
                is_amazon_prime=False,
                yahoo_premium=False,
                is_rakuten_mobile=False,
                is_paypay_linked=False,
                default_card_id=None,
            )
        )
        db_session.commit()

        # When: search that matches nothing
        response = client.get(
            ENDPOINT,
            params={"q": "totally-nonexistent-product-xyz"},
            headers=_auth_header(auth_token["token"]),
        )

        # Then: 200, empty items, but meta.personalization reflects the user
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        personalization = body["meta"]["personalization"]
        assert personalization["applied"] is True
