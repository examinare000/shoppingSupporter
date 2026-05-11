"""Unit tests for SuggestionResponse schema (T-20).

検証対象:
- SuggestionResponse の action フィールドが Literal["buy_now", "wait"] であること
- 不正な action 値は Pydantic ValidationError で拒否されること
- action='wait' のとき Optional フィールドすべてに値が設定されること（cross-field 不変条件）

Why ここでテストするか:
    action: str に戻す変更（型ガード削除）や不正値の混入を
    ビルド・テスト時点で検出するための契約テスト。
    Pydantic の静的バリデーションを利用し DB 不要でインメモリ検証できる。
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from api.schemas import SuggestionResponse

# buy_now の有効なベースデータ（Optional フィールドはすべて None）
_BUY_NOW_BASE = {
    "product_id": uuid.uuid4(),
    "action": "buy_now",
    "rationale": "今が買い時です。",
    "current_best_effective_price": None,
    "expected_sale_effective_price": None,
    "estimated_saving": None,
    "next_sale_date": None,
    "next_sale_campaign": None,
}

# wait の有効なベースデータ（Optional フィールドすべてに値あり）
_WAIT_BASE = {
    "product_id": uuid.uuid4(),
    "action": "wait",
    "rationale": "近日中にセールが予定されています。",
    "current_best_effective_price": 10000,
    "expected_sale_effective_price": 9000,
    "estimated_saving": 1000,
    "next_sale_date": date(2026, 5, 15),
    "next_sale_campaign": "お買い物マラソン",
}


def _buy_now_response(**overrides) -> dict:
    return {**_BUY_NOW_BASE, **overrides}


def _wait_response(**overrides) -> dict:
    return {**_WAIT_BASE, **overrides}


class TestSuggestionResponseActionLiteralContract:
    """action フィールドの Literal 型契約を検証する。

    Why この型契約テストが必要か:
        action: str に差し戻されると不正値がサイレントに通過し、
        フロントエンドに未定義の action が返る。
        ビルドやユニットテストの段階でリグレッションを検出するために保持する。
    """

    def test_buy_now_is_valid_action(self):
        """action="buy_now" は SuggestionResponse を生成できる。"""
        resp = SuggestionResponse(**_buy_now_response())
        assert resp.action == "buy_now"

    def test_wait_is_valid_action(self):
        """action="wait" かつ Optional フィールドすべてに値があれば生成できる。"""
        resp = SuggestionResponse(**_wait_response())
        assert resp.action == "wait"

    def test_invalid_action_raises_validation_error(self):
        """action="invalid" は ValidationError を発生させる（Literal 契約）。"""
        with pytest.raises(ValidationError):
            SuggestionResponse(**_buy_now_response(action="invalid"))

    def test_empty_string_action_raises_validation_error(self):
        """空文字列は ValidationError を発生させる。"""
        with pytest.raises(ValidationError):
            SuggestionResponse(**_buy_now_response(action=""))

    def test_uppercase_action_raises_validation_error(self):
        """大文字混じりの "BUY_NOW" は ValidationError を発生させる。

        Why: Literal は大文字小文字を区別する。フロントエンドは
        小文字を期待するため、大文字変換が入らないことを検証する。
        """
        with pytest.raises(ValidationError):
            SuggestionResponse(**_buy_now_response(action="BUY_NOW"))


class TestSuggestionResponseCrossFieldValidation:
    """action='wait' 時の cross-field 不変条件を検証する。

    Why この契約テストが必要か:
        docstring の不変条件「wait のとき Optional フィールドすべてに値が設定される」を
        @model_validator で強制している。バリデーターを削除・弱体化する変更を
        テスト段階で検出するために保持する。
    """

    def test_wait_with_all_optional_fields_is_valid(self):
        """action='wait' かつ Optional フィールドすべてに値があれば ValidationError なし。"""
        resp = SuggestionResponse(**_wait_response())
        assert resp.action == "wait"
        assert resp.estimated_saving == 1000

    def test_wait_with_missing_estimated_saving_raises_validation_error(self):
        """action='wait' で estimated_saving が None なら ValidationError。"""
        with pytest.raises(ValidationError, match="estimated_saving"):
            SuggestionResponse(**_wait_response(estimated_saving=None))

    def test_wait_with_missing_expected_sale_effective_price_raises_validation_error(self):
        """action='wait' で expected_sale_effective_price が None なら ValidationError。"""
        with pytest.raises(ValidationError, match="expected_sale_effective_price"):
            SuggestionResponse(**_wait_response(expected_sale_effective_price=None))

    def test_wait_with_missing_next_sale_date_raises_validation_error(self):
        """action='wait' で next_sale_date が None なら ValidationError。"""
        with pytest.raises(ValidationError, match="next_sale_date"):
            SuggestionResponse(**_wait_response(next_sale_date=None))

    def test_wait_with_missing_next_sale_campaign_raises_validation_error(self):
        """action='wait' で next_sale_campaign が None なら ValidationError。"""
        with pytest.raises(ValidationError, match="next_sale_campaign"):
            SuggestionResponse(**_wait_response(next_sale_campaign=None))

    def test_wait_with_all_optional_fields_none_raises_validation_error(self):
        """action='wait' で Optional フィールドがすべて None なら ValidationError。"""
        with pytest.raises(ValidationError):
            SuggestionResponse(**_wait_response(
                expected_sale_effective_price=None,
                estimated_saving=None,
                next_sale_date=None,
                next_sale_campaign=None,
            ))

    def test_buy_now_with_all_optional_fields_none_is_valid(self):
        """action='buy_now' では Optional フィールドが None でも ValidationError なし。"""
        resp = SuggestionResponse(**_buy_now_response())
        assert resp.action == "buy_now"
        assert resp.estimated_saving is None
