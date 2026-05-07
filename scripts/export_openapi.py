"""
FastAPI アプリから OpenAPI スキーマを JSON で標準出力に書き出す。
DB 接続・サーバー起動は不要。CI での型生成に使用する。

使い方:
  python scripts/export_openapi.py > openapi.json
"""
import json
import os
import sys

# SQLAlchemy の create_engine は URL を受け取るだけで接続しないため
# DATABASE_URL が実在しなくても import できる。未設定時はデフォルト値を使用。
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@localhost:5432/shoppingsupporter")
os.environ.setdefault("JWT_SECRET", "ci-only-secret-not-used-for-signing")

# リポジトリルートを sys.path に追加してパッケージとして認識させる
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from api.main import app  # noqa: E402

schema = app.openapi()
print(json.dumps(schema, ensure_ascii=False, indent=2))
