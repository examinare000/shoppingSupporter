"""共通の日時ユーティリティ。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# 日本標準時 (JST = UTC+9)
_JST = timezone(timedelta(hours=9))


def current_business_month() -> str:
    """日本標準時（JST）での当月を YYYY-MM 形式で返す。

    Why UTC ではなく JST か:
        月境界が UTC と JST で最大9時間ずれる。日本のユーザー向けサービスでは
        JST を基準にすることで「今月」の定義をユーザーの感覚と一致させる。
    """
    return datetime.now(_JST).strftime("%Y-%m")
