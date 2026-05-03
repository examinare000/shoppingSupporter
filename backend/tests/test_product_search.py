"""Tests for GET /api/products/search.

Covers the contract specified in
.takt/runs/20260503-152937-get-api-products-se/context/task/order.md
and the design from the plan step.

Layered as:
- Unit tests against the search_products(db, q, limit) helper
- Integration tests via FastAPI TestClient that exercise routing,
  validation handling, response shape, and error fallback
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from database import get_db
from main import app
from routers.products import search_products
from schemas import ProductOut


ENDPOINT = "/api/products/search"


def _seed(session, products):
    for product in products:
        session.add(product)
    session.commit()


# ---------------------------------------------------------------------------
# Unit tests: search_products(db, q, limit)
# ---------------------------------------------------------------------------


class TestSearchProductsName:
    def test_should_return_product_when_name_contains_q(self, db_session, make_product):
        # Given: a product whose name contains the query
        _seed(db_session, [make_product(name="赤いリンゴ")])

        # When: searching with the matching keyword
        result = search_products(db_session, "リンゴ", 10)

        # Then: that product is returned
        assert len(result) == 1
        assert result[0].name == "赤いリンゴ"

    def test_should_match_case_insensitively_for_ascii(self, db_session, make_product):
        # Given: a product with a mixed-case name
        _seed(db_session, [make_product(name="Apple Pie")])

        # When: searching with a lowercase keyword
        result = search_products(db_session, "apple", 10)

        # Then: the product is matched
        assert len(result) == 1
        assert result[0].name == "Apple Pie"

    def test_should_return_empty_when_no_product_matches(self, db_session, make_product):
        # Given: a single product that does not match
        _seed(db_session, [make_product(name="orange")])

        # When: searching for an unrelated keyword
        result = search_products(db_session, "banana", 10)

        # Then: an empty list is returned
        assert result == []


class TestSearchProductsDescription:
    def test_should_return_product_when_only_description_matches(self, db_session, make_product):
        # Given: a product whose description (not name) contains the query
        _seed(db_session, [make_product(name="無関係", description="このリンゴは美味しい")])

        # When: searching with the description keyword
        result = search_products(db_session, "リンゴ", 10)

        # Then: the product is returned
        assert len(result) == 1
        assert result[0].name == "無関係"

    def test_should_exclude_product_with_null_description_when_only_description_could_match(
        self, db_session, make_product
    ):
        # Given: a product without a description and a name that does not match
        _seed(db_session, [make_product(name="orange", description=None)])

        # When: searching for a keyword that would only have matched description
        result = search_products(db_session, "apple", 10)

        # Then: the product is excluded (NULL ILIKE behavior is intentional)
        assert result == []


class TestSearchProductsRelevanceOrder:
    def test_should_rank_by_relevance_tiers(self, db_session, make_product):
        # Given: products at each relevance tier
        _seed(
            db_session,
            [
                make_product(name="apple", description="exact name match"),
                make_product(name="apple pie", description="prefix match"),
                make_product(name="green apple", description="substring match"),
                make_product(name="orange", description="apple flavored"),
                make_product(name="banana", description="no match here"),
            ],
        )

        # When: searching by the keyword
        result = search_products(db_session, "apple", 10)

        # Then: ordered exact > prefix > substring > description, no banana
        names = [p.name for p in result]
        assert names == ["apple", "apple pie", "green apple", "orange"]

    def test_should_break_ties_by_name_ascending(self, db_session, make_product):
        # Given: two products at the same relevance tier
        _seed(
            db_session,
            [
                make_product(name="zebra apple"),
                make_product(name="alpha apple"),
            ],
        )

        # When: searching
        result = search_products(db_session, "apple", 10)

        # Then: alphabetical name order is the tie-break
        assert [p.name for p in result] == ["alpha apple", "zebra apple"]


class TestSearchProductsLimit:
    def test_should_respect_limit_argument(self, db_session, make_product):
        # Given: more matching products than the requested limit
        _seed(db_session, [make_product(name=f"apple {i}") for i in range(5)])

        # When: searching with a smaller limit
        result = search_products(db_session, "apple", 3)

        # Then: only `limit` results are returned
        assert len(result) == 3


class TestSearchProductsMatchKinds:
    def test_should_return_when_only_name_matches(self, db_session, make_product):
        # Given: a product where only the name matches
        _seed(
            db_session,
            [make_product(name="apple", description="completely unrelated")],
        )

        # When: searching by the keyword
        result = search_products(db_session, "apple", 10)

        # Then: the product is returned
        assert [p.name for p in result] == ["apple"]

    def test_should_return_when_only_description_matches(self, db_session, make_product):
        # Given: a product where only the description matches
        _seed(
            db_session,
            [make_product(name="orange", description="apple flavor")],
        )

        # When: searching by the keyword
        result = search_products(db_session, "apple", 10)

        # Then: the product is returned
        assert [p.name for p in result] == ["orange"]

    def test_should_return_when_both_name_and_description_match(self, db_session, make_product):
        # Given: a product where both fields match
        _seed(
            db_session,
            [make_product(name="apple snack", description="apple-based")],
        )

        # When: searching by the keyword
        result = search_products(db_session, "apple", 10)

        # Then: the product is returned exactly once
        assert [p.name for p in result] == ["apple snack"]


# ---------------------------------------------------------------------------
# Integration tests via TestClient
# ---------------------------------------------------------------------------


class TestEndpointHappyPath:
    def test_should_return_200_with_matching_products(self, client, db_session, make_product):
        # Given: a single matching product
        _seed(db_session, [make_product(name="apple")])

        # When: calling the endpoint with q
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: 200 with a JSON array body
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["name"] == "apple"

    def test_should_not_require_authentication(self, client, db_session, make_product):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: calling the endpoint without any auth headers
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: 200 is returned
        assert response.status_code == 200

    def test_should_return_response_with_product_schema_keys(
        self, client, db_session, make_product
    ):
        # Given: a fully populated matching product
        _seed(
            db_session,
            [
                make_product(
                    name="apple",
                    description="desc",
                    jan_code="1234567890123",
                    image_url="http://example.com/img.png",
                )
            ],
        )

        # When: calling the endpoint
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: each item exposes exactly the ProductOut schema keys
        body = response.json()
        assert len(body) == 1
        expected_keys = set(ProductOut.model_fields.keys())
        assert set(body[0].keys()) == expected_keys

    def test_should_return_bare_array_not_envelope(self, client, db_session, make_product):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: calling the endpoint
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: the body is a bare JSON array (response standard not used as envelope)
        body = response.json()
        assert isinstance(body, list), "response must be a bare list, not an envelope object"


class TestEndpointQueryParameterContract:
    def test_should_read_q_from_query_string_not_body(self, client, db_session, make_product):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: q is sent as a JSON body instead of a query string.
        # httpx>=0.20's client.get() does not accept `json=`; use request()
        # to keep the negative contract test (body must not be read) valid.
        response = client.request("GET", ENDPOINT, json={"q": "apple"})

        # Then: the body is ignored (q must come from the query string)
        assert response.status_code == 200
        assert response.json() == []

    def test_should_apply_limit_from_query_string(self, client, db_session, make_product):
        # Given: more matching products than the requested limit
        _seed(db_session, [make_product(name=f"apple {i}") for i in range(5)])

        # When: limit is provided on the query string
        response = client.get(ENDPOINT, params={"q": "apple", "limit": 2})

        # Then: only `limit` items are returned
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_should_default_limit_to_10_when_not_provided(self, client, db_session, make_product):
        # Given: more than 10 matching products
        _seed(db_session, [make_product(name=f"apple {i:02d}") for i in range(15)])

        # When: limit is omitted
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: exactly 10 items are returned (default limit)
        assert response.status_code == 200
        assert len(response.json()) == 10


class TestEndpointRelevanceOrdering:
    def test_should_order_endpoint_results_by_relevance(
        self, client, db_session, make_product
    ):
        # Given: products at each relevance tier
        _seed(
            db_session,
            [
                make_product(name="apple"),
                make_product(name="apple pie"),
                make_product(name="green apple"),
                make_product(name="orange", description="apple flavored"),
            ],
        )

        # When: searching via the endpoint
        response = client.get(ENDPOINT, params={"q": "apple"})

        # Then: ordering reflects the relevance tiers
        names = [p["name"] for p in response.json()]
        assert names == ["apple", "apple pie", "green apple", "orange"]


class TestEndpointEmptyResultCases:
    def test_should_return_empty_array_when_no_match(self, client, db_session, make_product):
        # Given: a product that does not match
        _seed(db_session, [make_product(name="orange")])

        # When: searching for an unrelated keyword
        response = client.get(ENDPOINT, params={"q": "xyz"})

        # Then: 200 with empty list
        assert response.status_code == 200
        assert response.json() == []

    def test_should_return_empty_array_when_q_is_missing(self, client):
        # Given: no q parameter
        # When: calling the endpoint without q
        response = client.get(ENDPOINT)

        # Then: 200 with empty list
        assert response.status_code == 200
        assert response.json() == []

    def test_should_return_empty_array_when_q_is_empty_string(
        self, client, db_session, make_product
    ):
        # Given: a product exists
        _seed(db_session, [make_product(name="apple")])

        # When: q is empty
        response = client.get(ENDPOINT, params={"q": ""})

        # Then: 200 with empty list
        assert response.status_code == 200
        assert response.json() == []

    def test_should_return_empty_array_when_q_is_whitespace_only(
        self, client, db_session, make_product
    ):
        # Given: a product exists
        _seed(db_session, [make_product(name="apple")])

        # When: q is whitespace
        response = client.get(ENDPOINT, params={"q": "   "})

        # Then: 200 with empty list
        assert response.status_code == 200
        assert response.json() == []

    def test_should_return_empty_array_when_q_exceeds_max_length(
        self, client, db_session, make_product
    ):
        # Given: a product exists
        _seed(db_session, [make_product(name="apple")])

        # When: q exceeds the 100-character cap
        response = client.get(ENDPOINT, params={"q": "a" * 101})

        # Then: 200 with empty list
        assert response.status_code == 200
        assert response.json() == []


class TestEndpointLimitBoundaries:
    def test_should_return_empty_array_when_limit_is_zero(
        self, client, db_session, make_product
    ):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: limit = 0
        response = client.get(ENDPOINT, params={"q": "apple", "limit": 0})

        # Then: 200 with empty list
        assert response.status_code == 200
        assert response.json() == []

    def test_should_return_empty_array_when_limit_is_negative(
        self, client, db_session, make_product
    ):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: limit < 0
        response = client.get(ENDPOINT, params={"q": "apple", "limit": -1})

        # Then: 200 with empty list
        assert response.status_code == 200
        assert response.json() == []

    def test_should_return_empty_array_when_limit_is_non_numeric(
        self, client, db_session, make_product
    ):
        # Given: a matching product
        _seed(db_session, [make_product(name="apple")])

        # When: limit is not parseable as int
        response = client.get(ENDPOINT, params={"q": "apple", "limit": "abc"})

        # Then: 200 with empty list (RequestValidationError converted to 200 + [])
        assert response.status_code == 200
        assert response.json() == []

    def test_should_clamp_limit_above_100_to_100(self, client, db_session, make_product):
        # Given: 150 matching products
        _seed(
            db_session, [make_product(name=f"apple {i:03d}") for i in range(150)]
        )

        # When: limit far exceeds the 100 cap
        response = client.get(ENDPOINT, params={"q": "apple", "limit": 9999})

        # Then: at most 100 results (cap is enforced)
        assert response.status_code == 200
        assert len(response.json()) == 100


class TestEndpointDatabaseError:
    def test_should_return_empty_array_when_db_execute_raises(self):
        # Given: an injected session whose execute always raises
        class BrokenSession:
            def execute(self, *args, **kwargs):
                raise RuntimeError("simulated DB failure")

            def close(self):
                pass

        def broken_get_db():
            yield BrokenSession()

        app.dependency_overrides[get_db] = broken_get_db
        try:
            # When: calling the endpoint
            with TestClient(app) as broken_client:
                response = broken_client.get(ENDPOINT, params={"q": "apple"})

            # Then: 200 with empty list (errors are swallowed by spec)
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestEndpointSpecialCharacterEscaping:
    def test_should_treat_percent_in_q_as_literal_not_wildcard(
        self, client, db_session, make_product
    ):
        # Given: one product with a literal "%" and one without
        _seed(
            db_session,
            [
                make_product(name="50% off"),
                make_product(name="50 percent off"),
            ],
        )

        # When: searching for a string that contains "%"
        response = client.get(ENDPOINT, params={"q": "50%"})

        # Then: only the literal "%" product matches; "%" must not act as a wildcard
        assert response.status_code == 200
        names = sorted(p["name"] for p in response.json())
        assert names == ["50% off"]

    def test_should_treat_underscore_in_q_as_literal_not_wildcard(
        self, client, db_session, make_product
    ):
        # Given: one product with a literal "_" and one with another character in that position
        _seed(
            db_session,
            [
                make_product(name="under_score"),
                make_product(name="underxscore"),
            ],
        )

        # When: searching with "_" in the query
        response = client.get(ENDPOINT, params={"q": "under_score"})

        # Then: only the literal "_" product matches
        assert response.status_code == 200
        names = sorted(p["name"] for p in response.json())
        assert names == ["under_score"]
