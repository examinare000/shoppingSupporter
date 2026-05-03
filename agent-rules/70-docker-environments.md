# 70. Docker環境管理

## 規約

- **ファイル名**: `compose.yml`（`docker-compose.yml` ではない）
- **形式**: Compose V2（`version:` フィールド記載しない）
- **コマンド**: `docker compose`（`docker-compose` ではない）

## compose.yml の基本構成

```yaml
services:
  app:
    image: python:3.11-alpine  # 言語に応じて変更
    ports:
      - "8000:8000"
    environment:
      ENV: development
    env_file:
      - .env
    volumes:
      - .:/app
      - app_cache:/app/.cache
    working_dir: /app
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
  app_cache:
```

## 言語別ベースイメージ

| 言語 | 推奨イメージ | キャッシュボリューム |
|---|---|---|
| Python | `python:3.11-alpine` | `pip_cache:/root/.cache/pip` |
| Node.js | `node:18-alpine` | `node_modules:/app/node_modules` |
| Go | `golang:1.21-alpine` | `go_cache:/go/pkg/mod` |

## 開発フロー

```bash
# 初期セットアップ
cp .env.example .env
docker compose up -d
docker compose logs -f app

# コンテナ内作業
docker compose exec app bash
docker compose run --rm app <command>

# 環境リセット
docker compose down -v
docker compose up --build -d
```

## ツールのDocker化

ツール作成時は必ずDockerコンテナで実行可能にする。`profiles` で分離する。

```yaml
services:
  test:
    extends: dev-tools
    command: pytest tests/ -v
    profiles: [test]

  lint:
    extends: dev-tools
    command: flake8 src/
    profiles: [lint]
```

```bash
docker compose --profile test run --rm test
docker compose --profile lint run --rm lint
```

## Dockerfile標準

### 必須要件

- 非rootユーザーで実行
- マルチステージビルドで本番イメージを最小化
- 依存関係インストールとアプリコピーを分離（キャッシュ活用）
- `EXPOSE` でポートを明示

### マルチステージ例（Node.js）

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS production
RUN apk add --no-cache dumb-init
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001 -G nodejs
WORKDIR /app
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/package*.json ./
RUN npm ci --only=production && npm cache clean --force
USER nodejs
EXPOSE 3000
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/index.js"]
```

## 環境変数

- `.env.example` を必ず提供。実値は `.env`（gitignore対象）
- 開発環境固有の値は `compose.yml` の `environment` で上書き

## 開発効率の設定

- **ホットリロード**: `volumes` でソースをマウント、`node_modules` 等は除外
- **デバッガポート**: 例 `"9229:9229"`、`NODE_OPTIONS: "--inspect=0.0.0.0:9229"`
- **ヘルスチェック**: `healthcheck` で起動完了を確実に検知
- **リソース制限**: `deploy.resources.limits` で CPU/メモリ上限

## トラブルシューティング

| 問題 | 対処 |
|---|---|
| ポート競合 | `lsof -i :<port>` で確認、`compose.yml` で別ポートに |
| ボリューム権限 | `chown -R $(id -u):$(id -g) /app` または Dockerfile で USER 設定 |
| キャッシュ不整合 | `docker compose build --no-cache` または `docker system prune -a` |

---

**適用優先度**: 🟠 高（Docker使用プロジェクトでは必須）
