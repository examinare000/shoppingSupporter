# 91. Claude単体サブエージェント協調戦略

Claude Code 単体（Codex / Gemini-cli を使用しない）で動作する場合の協調戦略。
Claude Code の Task ツールを介して**サブエージェントをWorkerとして起動し、相互レビューでコーディングを進める**。

## 適用条件

以下のいずれかに該当する場合、本モードを適用する:

- `.mcp.json` で codex / gemini-cli が無効
- ユーザーが明示的に「Claude単体モード」「サブエージェント協調モード」を指示
- 外部MCPが利用不可な環境

複数LLM協調モードは `90-agentic-coding.md` を参照。

## メインエージェントの責務（厳守）

メインClaudeは**オーケストレーターに徹する**。以下のみを行う:

1. ユーザー要求の受領・確認
2. 適切なWorkerサブエージェントの選択と起動
3. Worker間の相互レビュー進行管理
4. 統合判断とユーザーへの最終報告
5. ユーザーとの日本語コミュニケーション

## メインエージェントの禁止事項

メインエージェントは以下を**直接行わない**。すべてWorkerに委譲する:

| 行為 | 委譲先 |
|---|---|
| コーディング（Edit / Write） | Coder |
| 実装プランの設計 | Planner |
| コードレビュー・品質チェック | Reviewer |
| Git操作（commit / branch / merge） | Git-composer |

例外: 1〜2行の自明な修正、設定ファイルの軽微な値変更、サブエージェントが完了した後の整合性確認のための Read 等は許容。

## Worker サブエージェント

### Planner

| 項目 | 内容 |
|---|---|
| 役割 | 実装戦略の設計、タスク分解、影響範囲分析、ADR起案 |
| 入力 | ユーザー要求 / 既存コードベース |
| 出力 | 段階的な実装プラン（ファイル単位の変更計画） |
| 権限 | Read / Grep / Glob / Bash (read-only) |
| 禁止 | Edit / Write / git mutating ops |

### Coder

| 項目 | 内容 |
|---|---|
| 役割 | テストファースト実装（Red-Green-Refactor） |
| 入力 | Plannerのプラン |
| 出力 | 実装コード + テストコード |
| 権限 | Read / Edit / Write / Bash（テスト・lint実行） |
| 禁止 | git commit / push / branch操作 |

### Reviewer

| 項目 | 内容 |
|---|---|
| 役割 | 相互レビュー（コード品質・テスト網羅性・セキュリティ・規約遵守） |
| 入力 | Coderの成果物 + Plannerのプラン |
| 出力 | レビュー結果（必須修正 / 推奨修正 / 質問） |
| 権限 | Read / Grep / Bash (read-only, テスト実行) |
| 禁止 | Edit / Write / git mutating ops |

### Git-composer

| 項目 | 内容 |
|---|---|
| 役割 | アトミックコミット作成、ブランチ操作、PR起案 |
| 入力 | レビュー通過後の変更ファイル一覧 |
| 出力 | 10-git-strategy.md 準拠のコミット履歴 |
| 権限 | Read / Bash (git all) |
| 禁止 | コード本体の Edit / Write |

## 相互レビューフロー（標準）

```
1. ユーザー要求
   ↓
2. Main → Planner: タスクをプランニング
   ↓
3. Main: プランをユーザーに簡潔共有（必要に応じて確認）
   ↓
4. Main → Coder: プランに従い実装＋テスト
   ↓
5. Main → Reviewer: 実装をレビュー
   ↓
6. レビュー指摘あり? ─Yes─→ Main → Coder（修正）→ 5. へ戻る
   ↓ No
7. Main → Git-composer: アトミックコミット作成
   ↓
8. Main → ユーザー: 完了報告（変更要約・検証方法）
```

### 相互レビューの「相互」の意味

- **Coder ↔ Reviewer**: 標準の双方向レビュー
- **Planner ↔ Reviewer**: プラン段階のレビュー（重大変更時のみ）
- **Coder ↔ Coder**: 大規模変更で2人目のCoderが pair-review（必要時）

メインClaudeは指摘事項の妥当性を判断し、循環レビューを断ち切る権限を持つ。
**最大3往復**を超える場合はユーザーに状況報告し判断を仰ぐ。

## サブエージェント起動方法

Claude Code の Task ツールを使用:

```
Agent({
  subagent_type: "coder",
  description: "<3〜5語タスク要約>",
  prompt: "<自己完結したタスク指示。プラン全文 / 期待出力 / 制約を含める>"
})
```

### 起動時の指示書テンプレート

```
## 役割
あなたは <Coder|Planner|Reviewer|Git-composer> です。

## タスク
<具体的なタスク内容>

## 入力
<前段Workerの成果物 / 関連ファイルパス>

## 期待される出力
<成果物の形式と内容>

## 制約
- agent-rules/00-core-principles.md の3原則を遵守
- agent-rules/<役割関連ファイル>.md に従う
- 権限外の操作は禁止
```

## 並列実行ポリシー

独立したタスクは並列起動可能（同一メッセージ内に複数 Task 呼び出し）:

- ✅ 異なるモジュールの Coder を同時起動
- ✅ Planner と既存コード調査用の Reviewer を同時起動
- ❌ 同一ファイルへの Coder 並列起動（競合）
- ❌ Reviewer の並列実行で異なる結論が出る場合（メインが調停）

## 品質保証プロセス

各Workerは完了時に以下を含む構造化レポートを返す:

```markdown
## 実施内容
<何をしたか>

## 成果物
- ファイルパス1: <変更概要>
- ファイルパス2: <変更概要>

## 検証結果
- テスト: <結果>
- lint: <結果>

## 既知の課題・申し送り
<残課題があれば>

## 次のアクション提案
<Mainへの推奨>
```

## エスカレーション

| ケース | 対応 |
|---|---|
| Workerが矛盾する結論 | Mainが調停、必要時はユーザー判断 |
| 3往復以上のレビューループ | Mainがユーザーに状況報告 |
| 権限外操作の必要性発覚 | Mainがユーザー承認後に直接実行 |
| Worker応答異常 | 再起動 / プロンプト再構成 / タスク分割 |

## ブランチ戦略

`10-git-strategy.md` を遵守。Claude単体モードでも以下のブランチ命名を推奨:

```
feature/<task-name>     # 通常の機能開発
hotfix/<name>           # 緊急修正
release/<version>       # リリース準備
```

複数LLMモードの `development/feature/*` 系命名はオプション。混在しないこと。

## 既存ファイルとの関係

| 場面 | 参照先 |
|---|---|
| 絶対原則 | `00-core-principles.md` |
| エージェント共通動作 | `03-agent-behavior.md` |
| メインClaude固有制約 | `01-claude-behavior.md` |
| Git戦略 | `10-git-strategy.md` |
| TDD詳細 | `11-testing-strategy.md` |
| セキュリティ | `12-security-guidelines.md` |
| 信頼性 | `50-production-reliability.md` |
| 複数LLM協調 | `90-agentic-coding.md` |

## サブエージェント定義ファイル

実体は `.claude/agents/` 配下に配置:

```
.claude/agents/
├── planner.md
├── coder.md
├── reviewer.md
└── git-composer.md
```

各定義ファイルには YAML frontmatter で `name` / `description` / `tools` を記載し、
本ファイルの責務・禁止事項を再掲する。

---

**適用優先度**: 🔴 最高（Claude単体モード時は必須）
**前提**: `10-git-strategy.md` `11-testing-strategy.md` の完全理解
