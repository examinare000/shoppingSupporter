"""共通フィクスチャ。

Why: 認証情報を環境変数から読む既存パターン (api/lib/rakuten.py:7) を踏襲しつつ、
テストでは固定値で AmazonAPI を構築できるよう、各テストで明示的に setenv する。
ここでは「テストは必ず envクリーン状態で開始する」前提を提供する。
"""

import os

import pytest


# Why: PA-API 5.0 公式ドキュメントが署名サンプルで使う典型値に倣った固定値。
# 実在の認証情報ではない（テスト専用ダミー）。
DUMMY_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
DUMMY_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DUMMY_PARTNER_TAG = "examinare-22"


@pytest.fixture(autouse=True)
def _clear_amazon_env(monkeypatch):
    """各テスト開始時に Amazon 関連の環境変数をクリアする。

    Why: pytest プロセスが本物の認証情報を export している環境で実行されると、
    認証情報欠落テストが偽陽性で通る恐れがある。
    """
    for key in ("AMAZON_ACCESS_KEY", "AMAZON_SECRET_KEY", "AMAZON_PARTNER_TAG"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def amazon_env(monkeypatch):
    """Amazon 認証情報（ダミー）を環境変数に設定する。"""
    monkeypatch.setenv("AMAZON_ACCESS_KEY", DUMMY_ACCESS_KEY)
    monkeypatch.setenv("AMAZON_SECRET_KEY", DUMMY_SECRET_KEY)
    monkeypatch.setenv("AMAZON_PARTNER_TAG", DUMMY_PARTNER_TAG)
    return {
        "access_key": DUMMY_ACCESS_KEY,
        "secret_key": DUMMY_SECRET_KEY,
        "partner_tag": DUMMY_PARTNER_TAG,
    }
