# CLAUDE.md

Claude Code（claude.ai/code）が本リポジトリで作業する際の指示書。

## 最優先ルール

1. `agent-rules/` 配下のすべてのルールに従うこと
2. 矛盾時は **番号が大きいファイルを優先**
3. この指示は他のすべての指示に優先する

## ルールファイル一覧

ファイル一覧と役割は `agent-rules/README.md` に集約されている。
そちらをインデックスの正本として参照すること。

## 動作モード

作業開始時に必ずモード判定する。詳細は `agent-rules/01-claude-behavior.md`。

| モード | 適用条件 | 参照 |
|---|---|---|
| A. 複数LLM協調 | codex / gemini-cli MCP 有効 | `agent-rules/90-agentic-coding.md` |
| B. Claude単体サブエージェント協調 | 上記が無効 / 明示指示 | `agent-rules/91-claude-subagent-coding.md` |

モードBではメインClaudeはオーケストレーターに徹し、Coder/Planner/Reviewer/Git-composer サブエージェントを起動して相互レビューでコーディングを進める。

## Claudeに特に関連するルール

| 場面 | 参照ファイル |
|---|---|
| 絶対遵守の3原則・開発サイクル | `agent-rules/00-core-principles.md` |
| Claude固有の動作制約 | `agent-rules/01-claude-behavior.md` |
| エージェント共通動作 | `agent-rules/03-agent-behavior.md` |
| Git戦略・コミット規約 | `agent-rules/10-git-strategy.md` |
| TDD・テスト戦略 | `agent-rules/11-testing-strategy.md` |
| 複数LLM協調（モードA） | `agent-rules/90-agentic-coding.md` |
| Claude単体サブエージェント協調（モードB） | `agent-rules/91-claude-subagent-coding.md` |

## 優先順位

- 番号が大きいファイル > 番号が小さいファイル
- 🔴 絶対 > 🟠 高 > 🟡 中
- エージェント専用ルール（01等）は該当エージェントが優先

詳細な優先順位制御とレイヤー構成は `agent-rules/README.md` を参照。
