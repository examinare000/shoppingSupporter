# 10. Git戦略

本リポジトリにおけるブランチ・コミット運用の**正本（Single Source of Truth）**。
Git-Flow を参考にしたブランチ戦略を採用する。

## 必須ルール

- 1ブランチ = 1イニシアチブ。小さく短命に保つ
- 保護ブランチ（`main` / `develop`）への直接コミット禁止
- 共有ブランチへの force-push 禁止
- `git add .` 原則禁止（意図しないファイル混入防止）
- WIP連投・無関係な変更の混在禁止

## ブランチ構成

| ブランチ | 用途 | 分岐元 | マージ先 | 直接コミット |
|---|---|---|---|---|
| `main` | プロダクション。タグ付きリリースのみ | - | - | 禁止 |
| `develop` | 統合開発ブランチ | - | - | 禁止 |
| `feature/<task-name>` | 新機能開発 | develop | develop | 可 |
| `release/<version>` | リリース準備 | develop | main + develop | 可 |
| `hotfix/<name>` | 緊急修正 | main | main + develop | 可 |

Agentic coding の拡張ブランチ（`development/feature/*` 等）は `90-agentic-coding.md` を参照。

### 命名例

```
feature/user-auth-session-timeout
release/v0.5.0
hotfix/critical-sync-bug
```

## アトミックコミットの原則

1. **1コミット = 1論理変更**
2. **複数ファイルは原則別コミット**。例外は相互依存がある場合のみ
   - 相互依存の定義: 一方の変更がコミットされないと他方が正常動作しない
   - 例: CSS変数定義（`globals.css`）とそれを参照する `tailwind.config.ts`
3. **独立した取り消し可能性**: 各コミットは他機能を壊さず revert 可能

### 依存関係の判断基準

| 状況 | 依存 | コミット方法 |
|---|---|---|
| 設定ファイルAを参照する設定ファイルB | あり | 1コミット |
| 同じ機能の異なるファイル（個別動作可能） | なし | 別コミット |
| インポート関係があるがビルド可能 | なし | 別コミット |
| 一方がないとコンパイル/実行エラー | あり | 1コミット |

## コミットメッセージ規約

**形式**: `<種別>: <説明>`（日本語、1〜2文、WHY優先）
**Co-Author表記は不要**

| 種別 | 用途 |
|---|---|
| 機能 | 新機能の追加 |
| 修正 | バグの修正 |
| 改善 | 既存機能の改善 |
| 削除 | コード・ファイルの削除 |
| 移動 | ファイル・コードの移動 |
| 名前変更 | 変数・関数・ファイル名の変更 |
| テスト | テストの追加・修正 |
| 文書 | ドキュメントのみの変更 |
| 設定 | 設定ファイルの変更 |
| 構成 | ディレクトリ構造の変更 |
| 統合 | ブランチのマージ |

```bash
# ✅ 良い例（WHYを含む）
git commit -m "改善: ボタン色をCSS変数に移行（保守性向上）"
git commit -m "統合: feature/user-authをdevelopにマージ"

# ❌ 悪い例
git commit -m "update"
git commit -m "WIP"
```

## マージ戦略

マージコミットを許容する。rebase は必須ではない。

```bash
git merge feature/<task-name>           # 標準マージ
git merge --no-ff feature/<task-name>   # 明示的にマージコミット作成
```

コンフリクト解決後は `統合: <理由>` のメッセージでコミット。

## 典型フロー

### 機能開発（feature）

```bash
git checkout develop && git pull origin develop
git checkout -b feature/<task-name>

# アトミックコミットで開発
git add specific_file.py
git commit -m "機能: <WHY>"

# 完了後
git checkout develop && git pull origin develop
git merge feature/<task-name>
git push origin develop
git branch -d feature/<task-name>
```

### リリース（release）

```bash
git checkout -b release/vX.Y.Z develop
# バージョン/CHANGELOG更新・最終テスト

git checkout main && git merge release/vX.Y.Z
git tag -a vX.Y.Z -m "リリース vX.Y.Z"
git push origin main --tags

git checkout develop && git merge release/vX.Y.Z
git push origin develop
git branch -d release/vX.Y.Z
```

### 緊急修正（hotfix）

```bash
git checkout -b hotfix/<name> main
# 修正後
git checkout main && git merge hotfix/<name>
git tag -a vX.Y.Z -m "Hotfix vX.Y.Z"
git push origin main --tags

git checkout develop && git merge hotfix/<name>
git push origin develop
git branch -d hotfix/<name>
```

## 事前チェック（push / PR 前）

```bash
npm test         # または pytest, go test など
npm run lint
npm run typecheck
```

## 誤操作時のリカバリー

### main / develop に誤コミット

```bash
git reset --soft HEAD~1
git stash
git checkout <correct-branch>
git stash pop
git commit -m "移動: 誤って<branch>にコミットした変更を移動"
```

### 間違ったブランチで作業

```bash
git stash
git checkout <correct-branch>
git stash pop
```

## バージョニング

- Semantic Versioning（MAJOR.MINOR.PATCH）
- `main` 取り込み時は annotated tag を付与

## 開発開始時の必須チェック

```bash
git branch                       # 現在ブランチ確認
git status                       # 状態確認
git checkout develop && git pull # 統合ブランチ最新化
```

---

**適用優先度**: 🔴 最高（すべてのGit操作に適用必須）
