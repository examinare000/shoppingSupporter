# 50. プロダクション信頼性

防御的設計とインターフェース契約により、本番環境での予期せぬ障害を防ぐ。
TDD・テストパターンの詳細は `11-testing-strategy.md` を参照。

## 信頼性3原則

### 1. Test-First Error Discovery

> エラーは本番で発見するのではなく、テスト環境で事前に発見・修正する

統合テスト・エッジケーステストを必須化する。

### 2. Defensive Programming by Default

外部入力（API・設定・環境変数）はすべて疑う。デフォルト値で継続動作可能にする。

```javascript
// ❌ 危険: 直接プロパティアクセス
const score = metrics.security.securityScore;

// ✅ Optional Chaining + デフォルト値
const score = metrics.security?.securityScore ?? DEFAULT_SECURITY_SCORE;
```

### 3. Interface Contract Verification

API契約を明示化し、契約違反を実行時ではなく開発時に検出する。

```javascript
function processQuality(report) {
  if (!report?.assessment?.overallScore) {
    throw new Error('Invalid quality report structure');
  }
  return report.assessment.overallScore.toFixed(1);
}
```

## 系統的デバッグアプローチ

```
1. エラーの再現   → テストケースで確実に再現
2. 原因の特定     → ログ・デバッガで根本原因調査
3. 修正の実装     → 最小限の変更で問題解決
4. テストで検証   → 修正が問題を解決することを確認
5. 回帰テスト     → 他機能に影響がないことを確認
```

## 修正品質基準

- **単一責任**: 1修正 = 1問題
- **最小影響**: 既存コードへの影響最小化
- **テスト可能**: 修正内容をテストで検証可能
- **文書化**: 修正理由と変更内容を記録

## 堅牢なエラーハンドリング戦略

```python
class QualityEvaluator:
    def evaluate_quality(self, codebase=None):
        try:
            codebase = codebase or {}
            metrics = self._collect_metrics(codebase)
            assessment = self._calculate_assessment(metrics)
            return self._success_response(assessment)
        except ValidationError as e:
            self.logger.error(f'バリデーションエラー: {e}')
            return self._error_response(f'入力データの検証に失敗: {e}')
        except Exception as e:
            self.logger.error(f'品質評価エラー: {e}', exc_info=True)
            return self._error_response('処理中にエラーが発生しました')
```

ポイント:
- 例外型ごとに区別（既知のドメイン例外 vs 予期せぬ例外）
- ユーザー向けメッセージは汎用的に
- 内部ログには `exc_info=True` でスタックトレース

## リソース管理

- **タイムアウト**: 全外部呼び出しに必須
- **同時実行制限**: セマフォ等で並列度を制御
- **リソース解放**: `finally` または `with` 文で確実に

```python
async with rm.managed_resource("quality_analysis"):
    result = await analyze_quality(data)
```

## チェックリスト

### 起動前
- [ ] 全ユニット・統合・E2Eテストがパス
- [ ] エラーハンドリング・パフォーマンステストがパス
- [ ] セキュリティテストがパス

### コードレビュー
- [ ] 防御的プログラミングが実装されている
- [ ] エラーハンドリングが適切
- [ ] インターフェース契約が明確
- [ ] テストカバレッジ80%以上
- [ ] ログ・監視が適切

### デプロイ前
- [ ] 本番相当環境でのテスト完了
- [ ] ロールバック手順確認済み
- [ ] 監視・アラート設定済み
- [ ] 依存関係の脆弱性チェック完了

## 品質メトリクス監視

- テスト成功率: 95%以上
- 本番エラー発生率: 月1件未満
- MTTR（平均復旧時間）: 30分以内
- テストカバレッジ: 80%以上

## インシデント対応フロー

```
1. 検知       (自動監視 / ユーザー報告)
2. 初期対応   (影響範囲特定 / 応急処置)
3. 根本原因   (ログ調査 / 再現テスト)
4. 恒久対策   (修正実装 / テスト)
5. 予防策     (再発防止の仕組み実装)
6. 文書化     (インシデント報告書)
7. 改善       (プロセス・監視の見直し)
```

---

**適用優先度**: 🔴 最高（プロダクションコードに必須）
