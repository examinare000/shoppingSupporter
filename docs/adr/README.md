# アーキテクチャ決定記録 (ADR)

このディレクトリには、pricehack プロジェクトにおける主要な技術的意思決定とその背景を記録します。

## 履歴

- [ADR-001: 基本技術スタックの選定](001-tech-stack-selection.md)
- [ADR-002: Vercel への移行とサーバーレスアーキテクチャへの刷新](002-multi-container-architecture.md) (刷新)
- [ADR-003: 公式API連携への移行とPlaywrightの廃止](003-playwright-scraping.md) (刷新)
- [ADR-004: エディトリアルデザインの採用とモック先行のフロントエンド開発](004-editorial-design-and-mock-first-frontend.md)
- [ADR-005: モック駆動フロントから実バックエンドへの移行戦略](005-mock-to-backend-migration.md)
- [ADR-006: 高度な機能（還元率反映・履歴・予測）のロードマップ](006-advanced-features-roadmap.md)
- [ADR-007: ユーザー認証戦略の決定](007-authentication-strategy.md)
- [ADR-008: データベースサービスの選定](008-database-selection.md)
- [ADR-009: backend/ を api/ に統合し Vercel + Neon 構成を正本化](009-backend-to-api-consolidation.md)
- [ADR-010: Postgres 全文検索 (FTS) と Trigram 類似度による商品検索の実装](010-postgres-fts-and-trigram-search.md)
- [ADR-011: testcontainers と Alembic を活用したインテグレーションテスト戦略](011-integration-testing-strategy.md)
- [ADR-012: OpenAPI スキーマを活用したフロントエンド型同期戦略](012-openapi-type-sync-strategy.md)
