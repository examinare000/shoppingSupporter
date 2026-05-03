# 12. セキュリティガイドライン

すべてのプロダクションコードに適用する。

## 認証情報・シークレット

- **ログ出力禁止**: トークン・パスワード・APIキーは絶対にログに出さない
- **ハードコーディング禁止**: 環境変数または安全なストレージ経由
- **マスク必須**: エラーハンドラで機密情報をサニタイズ
- `.env` は必ず `.gitignore` に追加。`.env.example` で雛形を共有

```python
# ❌ NG
API_KEY = 'abc123secret'
logger.info(f"login: {email}, password: {password}")

# ✅ OK
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError('API_KEYが設定されていません')
logger.info(f"login: {email}")  # パスワードは出さない
```

## 入力値検証

すべての外部入力（API・ファイル・ユーザー入力・環境変数）を検証する。

- **メール / URL / 数値**: 形式バリデーション
- **HTML出力**: HTMLエスケープでXSS防止
- **ファイルパス**: `os.path.normpath` 後に `..` / 絶対パスを拒否（ディレクトリトラバーサル対策）
- **長さ制限**: 想定サイズの上限を設定

## SQLインジェクション対策

```python
# ❌ NG: 文字列結合
cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")

# ✅ OK: パラメータ化クエリ
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))

# ✅ OK: ORM
User.objects.filter(email=email).first()
```

## 認証・認可

- **JWT等のトークン**: 期限切れ・改ざんを必ず検証。失敗時は警告ログ
- **パスワード**: bcrypt等で必ずハッシュ化（ソルト付き）。平文保存禁止
- **複雑性チェック**: 最小8文字以上、文字種要件など

```python
# bcryptでハッシュ化
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
# 検証
bcrypt.checkpw(password.encode(), hashed)
```

## エラーハンドリング・ログ

- **内部詳細を露出しない**: ユーザーには汎用メッセージ、詳細は内部ログのみ
- **機密情報の自動マスク**: `password` `token` `secret` `key` `authorization` 等を含むキーは `[REDACTED]` に置換
- **認証試行・疑わしい活動**は専用セキュリティログに記録

## リソース保護

- **レート制限**: IPまたはユーザー単位でリクエスト頻度を制御
- **タイムアウト**: 全外部呼び出しにタイムアウトを設定
- **ファイルアップロード**: 拡張子・MIMEタイプ・サイズ・ファイル名サニタイズを検証

## チェックリスト

### 開発時
- [ ] 全外部入力を検証・サニタイズ
- [ ] 認証情報のハードコーディングなし
- [ ] パスワードは適切にハッシュ化
- [ ] SQLインジェクション・XSS対策実装
- [ ] ファイルアップロードの検証

### デプロイ前
- [ ] 環境変数が適切に設定
- [ ] HTTPS有効・セキュリティヘッダー設定
- [ ] レート制限実装
- [ ] ログにシークレットなし
- [ ] 依存関係の脆弱性チェック完了

### 監視・アラート
- [ ] 認証失敗の監視
- [ ] 異常アクセスパターンのアラート
- [ ] セキュリティログの保存・分析体制
- [ ] インシデント対応手順の整備

---

**適用優先度**: 🔴 最高（すべてのプロダクションコードに適用必須）
