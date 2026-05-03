# 90. Agentic Coding役割分担（複数LLM協調モード）

Claude / Codex / Gemini-cli が協調して開発を行う際の役割分担。
Git戦略は `10-git-strategy.md` を遵守し、本ファイルではその拡張のみ定義する。

## モード選択

| モード | ファイル | 適用条件 |
|---|---|---|
| **A. 複数LLM協調**（本ファイル） | `90-agentic-coding.md` | codex / gemini-cli MCP 有効 |
| **B. Claude単体サブエージェント協調** | `91-claude-subagent-coding.md` | 上記が無効、または明示指示 |

メインClaudeは作業開始時に必ずモードを判定する（`01-claude-behavior.md` 参照）。

## エージェント役割

| エージェント | 役割 | 主担当 | Git操作 |
|---|---|---|---|
| **Claude** | コーディネーター | タスク分解・進捗管理・統合判断・ユーザー対応 | developへの統合判断のみ |
| **Codex MCP** | コーディング | 実装・テスト作成・品質保証 | `development/feature/<task>` で開発 |
| **Gemini-cli** | 調査・分析 | 既存コード分析・技術調査・ドキュメント化 | `development/research/<topic>` で記録 |

## 拡張ブランチ命名規則

```
main (プロダクション)
├── develop (統合開発)
└── development/ (Agentic coding専用)
    ├── feature/<task-name>      # Codex
    ├── research/<topic>         # Gemini
    └── integration/<name>       # Claude（必要時）
```

## ワークフロー

### 1. タスク受領・分解（Claude）

- ユーザー要求を技術タスクに分解
- 依存関係を整理し、適切なエージェントに割り当て
- TodoWrite で進捗管理

### 2. 開発・調査（Codex / Gemini）

- 各自のブランチで独立して作業
- Claudeが進捗をモニタリング
- 必要に応じてタスク再調整

### 3. 統合・品質管理（Claude）

統合判断基準:
- コード品質
- テスト通過
- 既存機能への影響
- セキュリティチェック

## コミュニケーション規約

| 経路 | 言語 | 内容 |
|---|---|---|
| Claude ↔ ユーザー | 日本語必須 | タスク分解の確認・技術選択の相談・統合可否報告 |
| Claude ↔ Codex/Gemini | 英語可 | 構造化された指示書（タスク定義・期待成果物・品質基準・ブランチ） |

## 完了時の必須アクション

### Codex（開発完了後）

```bash
npm test && npm run lint && npm run typecheck
git push origin development/feature/<task>
# Claudeへ実装内容を報告
```

### Gemini（調査完了後）

```bash
git add research-report.md
git commit -m "調査: <テーマ>の技術調査完了"
git push origin development/research/<topic>
# Claudeへ調査結果を報告
```

## エスカレーション規約

| ケース | 対応 |
|---|---|
| 技術判断要 | Codex/Gemini → Claude → ユーザー討議 → 全エージェント共有 |
| デッドロック | 状況報告 → 選択肢整理 → ユーザー最終判断 |
| 品質基準未達 | 自動差し戻し → 修正指示明確化 → 再実装/再調査 |
| エージェント応答不能 | 他エージェントで代替 / タスク分割 / ユーザー報告 |
| 統合コンフリクト | Claude手動解決。重要変更は必ずユーザー確認、最悪時はロールバック |

## 効率向上施策

- **並行作業の最大化**: 独立タスクは同時実行、ブランチ分離で競合回避
- **知識共有**: 調査結果の構造化ドキュメント化、開発パターンのテンプレート化、失敗事例のナレッジ化

---

**適用優先度**: 🔴 最高（Agentic coding実施時は必須）
**前提**: `10-git-strategy.md` の完全理解と遵守
