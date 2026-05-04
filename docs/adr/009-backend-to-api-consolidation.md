# ADR-009: `backend/` を `api/` に統合し Vercel + Neon 構成を正本化する

## ステータス
採用済み

## 背景
develop ブランチでは ADR-002（Vercel 移行）と ADR-005（モック→実バックエンド移行）に基づき、Python バックエンドを Vercel Functions として `api/` 配下に配置する構成へ既に刷新済みである（`api/main.py`、`api/common/`、`api/cron/`、`api/lib/`）。

一方、main ブランチでは並行して `backend/` ディレクトリでコンテナ前提の FastAPI 実装が継続され、`GET /api/products/search`（FTS + pg_trgm + Alembic マイグレーション + テスト）を実装した。

この main を develop にマージしたところ、以下の二重構造が発生した。

- `api/` … Vercel Functions（develop 主流）
- `backend/` … コンテナ前提（main から取り込んだ検索機能の置き場）

両者は同じ FastAPI アプリの一部でありながら別ディレクトリに分散しており、`models.py` が二重に存在し、import パスも `api.common.models` と `models`（CWD 依存）で食い違う。このまま放置するとデプロイ対象（Vercel が読むのは `api/`）に検索機能が乗らない、または不整合のまま二重保守が始まる。

## 検討した選択肢

### 1. `backend/` を正にして `api/` を捨てる
- メリット: 検索機能の現コードに手を入れずに済む。
- デメリット: ADR-002（Vercel 移行）と ADR-005、ADR-008（Neon）の一連の決定を覆す。Vercel Functions の利点（ゼロ運用・スケールゼロ）を失う。コンテナ運用の固定費が発生する。

### 2. `api/` と `backend/` を並行運用する
- メリット: 当面の改修コストが低い。
- デメリット: モデル定義が二重化し schema drift のリスクが恒常化する。Vercel に乗らない `backend/` 側のコードがデッドコードと化す。CI／テスト戦略の分岐が必要になり保守コストが上がる。

### 3. `backend/` の中身を `api/` 配下に統合し `backend/` を削除する（採用）
- メリット: 既決定（ADR-002 / 005 / 008）と整合する。デプロイ単位は Vercel Functions ひとつに集約される。`models.py` が一本化される。
- デメリット: import パスの一括書き換えと、Alembic／テストの再配置が必要。

## 決定
**選択肢 3 を採用し、Vercel + Neon 構成を本プロジェクトの正本とする。**

具体的な配置は以下のとおり。

| 旧（`backend/`） | 新（リポジトリ） |
|---|---|
| `backend/main.py` | 削除（`api/main.py` に統合） |
| `backend/models.py` | 削除（`api/common/models.py` に一本化） |
| `backend/database.py` | 削除（`api/common/database.py` に一本化） |
| `backend/Dockerfile` | 削除（Vercel Functions が実行環境のため不要） |
| `backend/routers/` | `api/routers/` |
| `backend/repositories/` | `api/repositories/` |
| `backend/schemas.py` | `api/schemas.py` |
| `backend/alembic.ini` | `alembic.ini`（リポジトリルート） |
| `backend/alembic/` | `alembic/`（リポジトリルート） |
| `backend/tests/` | `tests/integration/` に統合 |
| `backend/pytest.ini` | 削除（ルート `pytest.ini` に集約） |

## 理由

- **ADR との整合**: ADR-002（Vercel）、ADR-005（モック→Vercel Functions 経由の実 API）、ADR-007（FastAPI + JWT）、ADR-008（Neon 直接契約 + `-pooler` 接続）の積み上げを尊重する。
- **インフラのシンプルさと低コスト**: Vercel + Neon は両者とも従量課金・サーバーレスでアイドル時はほぼゼロコスト。コンテナホスティングの固定費を発生させる必要がない。
- **デプロイ単位の一本化**: `api/main.py` を Vercel rewrite (`/api/(.*) → /api/main.py`) で受ける現構成に検索 router を `include_router` するだけで済む。新たな URL ルート設計は不要。
- **Alembic の置き場**: マイグレーションは Vercel Functions の実行プロセスとは独立に動かす（CI もしくは開発者ローカルから Neon に対して実行）。リポジトリルートに置くことで `python -m alembic` を直感的に実行でき、`api/` パッケージとの参照（`from api.common.models import Base`）も明示的になる。

## 結果

- フロントエンドは ADR-005 の方針どおり `fetch('/api/products/search?...')` で Vercel Functions（FastAPI）を直接叩ける。
- マイグレーションは「Neon 上のターゲット DB に対して `alembic upgrade head` を CI/手動で実行する」という運用で確定する。Dockerfile による起動時自動 upgrade は廃止。
- ランタイム依存（`requirements.txt`）と開発依存（`requirements-dev.txt`）を明確に分離し、Vercel Functions の cold start 時インストールサイズを最小化する。
- `backend/` 配下に紐づいていた `.takt/runs/*` の参照は履歴として残るが、現リポジトリ上の指す先は無効になる点に留意（履歴目的のため書き換え不要）。

## 影響を受ける既存 ADR

- **ADR-002**: 引き続き有効（本決定で具体化・補強）。
- **ADR-005**: 引き続き有効。検索エンドポイントのバックエンド配置場所が `backend/` ではなく `api/routers/products.py` であることを本 ADR が確定。
- **ADR-008**: 引き続き有効。Alembic の置き場（リポジトリルート）と運用（CI/手動 upgrade）を本 ADR が補足。
