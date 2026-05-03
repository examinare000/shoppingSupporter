# 11. テスト戦略

TDD実践とテスト品質の正本。基本原則は `00-core-principles.md` 参照。

## テスト階層

```
E2E      ← ユーザーシナリオ
統合     ← システム全体の動作確認
コンポ   ← モジュール間連携
ユニット ← 個別関数・メソッド
```

## TDD実践（t-wada方式）

### Red-Green-Refactor

```python
# 1. Red: 失敗するテストを先に書く
def test_税金計算_正常系():
    """金額に10%の税金が計算されること"""
    assert calculate_tax(1000) == 100

def test_税金計算_異常系():
    """負の金額では例外が発生すること"""
    with pytest.raises(ValueError, match="金額は正の数である必要があります"):
        calculate_tax(-100)

# 2. Green: 最小限の実装でテストを通す
def calculate_tax(amount):
    if amount < 0:
        raise ValueError("金額は正の数である必要があります")
    return amount * 0.1

# 3. Refactor: 振る舞いを保ったままコードを改善
```

### 実装ファースト禁止

テストを書く前に実装を進めない。仕様を先に明確化することで品質と設計を担保する。

## 必須テストパターン

### A. エラーハンドリング

undefined / None / 空文字 等の境界値で例外を出さず、適切にエラー応答するか検証。

```python
def test_undefinedメトリクスでも正常動作する():
    result = evaluator.calculate({'code_metrics': None})
    assert result['success'] is True
    assert result['overall_score'] >= 0
```

### B. 境界値

最小値・最大値・境界超過・空文字を網羅。

```python
def test_ユーザー名バリデーション_境界値():
    assert UserValidator.validate_name("田") is True       # 最小
    assert UserValidator.validate_name("田" * 50) is True   # 最大
    with pytest.raises(ValidationError):
        UserValidator.validate_name("田" * 51)             # 超過
    with pytest.raises(ValidationError):
        UserValidator.validate_name("")                    # 空
```

### C. 統合ワークフロー

ユーザーライフサイクル（作成 → 取得 → 更新 → 削除 → 確認）を一気通貫で検証。

### D. インターフェース契約

API レスポンスの必須フィールドと型を検証。後方互換性の早期検出に使う。

```python
def test_API契約_期待される構造でデータを返す():
    result = api.get_quality_report(project_id=1)
    for field in ['assessment', 'timestamp', 'success']:
        assert field in result
    assert isinstance(result['assessment']['overall_score'], (int, float))
    assert 0 <= result['assessment']['overall_score'] <= 100
```

## テスト実行戦略

### 実行順序

1. ユニットテスト → 基本機能
2. 統合テスト → モジュール間連携
3. システムテスト → 起動・動作
4. E2Eテスト → ユーザーシナリオ

### コマンド例

```bash
# Python
pytest tests/unit/ tests/integration/ tests/system/ tests/e2e/

# Node.js
npm run test:unit && npm run test:integration && npm run test:e2e

# Go
go test ./... -short
```

## 品質指標

| 指標 | 目標 |
|---|---|
| ユニットカバレッジ | 80%以上 |
| 統合テスト主要フロー | 100% |
| E2E主要シナリオ | 100% |
| テスト成功率 | 95%以上 |
| ユニット実行時間 | 10秒以内 |
| 統合テスト時間 | 5分以内 |
| E2E時間 | 30分以内 |

カバレッジは副産物。振る舞いに集中すること。

## モック戦略

外部依存（DB / API / ファイル / 時刻）はモック化し、ビジネスロジックを分離してテスト可能に保つ。

```python
@pytest.fixture
def mock_database():
    with patch('app.database.connection') as mock_db:
        mock_db.execute.return_value = [{"id": 1, "name": "テストユーザー"}]
        yield mock_db
```

注意: モックを多用しすぎると本番との乖離が発生する。**統合層は実DB/実APIで検証**するのが原則。

## テストデータ管理

- **フィクスチャ**で再利用可能なテストデータを定義
- セッションスコープで**テスト用DB**を構築・破棄
- テスト後のクリーンアップを忘れない

## パフォーマンステスト

主要操作には実行時間アサーションを入れる。

```python
def test_ユーザー作成_パフォーマンス():
    start = time.time()
    UserService.create_user({"name": "test", "email": "t@example.com"})
    assert time.time() - start < 1.0
```

---

**適用優先度**: 🔴 最高（すべてのコードに適用必須）
