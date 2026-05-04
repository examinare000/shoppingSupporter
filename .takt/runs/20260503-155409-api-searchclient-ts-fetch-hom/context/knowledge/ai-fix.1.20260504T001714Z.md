# フロントエンド専門知識

## フロントエンドの層構造

依存方向は一方向。逆方向の依存は禁止。

```
app/routes/ → features/ → shared/
```

| 層 | 責務 | ルール |
|---|------|--------|
| `app/routes/` | ルート定義のみ | UIロジックを持たない。feature の View を呼ぶだけ |
| `features/` | 機能単位の自己完結モジュール | 他の feature を直接参照しない |
| `shared/` | 全 feature 横断の共有コード | feature に依存しない |

ルートファイルは薄いラッパーに徹する。

```tsx
// CORRECT - ルートは薄い
// app/routes/schedule-management.tsx
export default function ScheduleManagementRoute() {
  return <ScheduleManagementView />
}

// WRONG - ルートにロジックを書く
export default function ScheduleManagementRoute() {
  const [filter, setFilter] = useState('all')
  const { data } = useListSchedules({ filter })
  return <ScheduleTable data={data} onFilterChange={setFilter} />
}
```

View コンポーネント（`features/*/components/*-view.tsx`）がデータ取得・状態管理を担当する。

```
ルート（route） → View（データ取得・状態管理） → 子コンポーネント（表示）
```

### 画面追加時のルーティング配線

新しい画面を追加したら、画面コンポーネントを作るだけで終わらせず、到達経路まで配線する。Router、メニュー、導線のどこから到達するかを計画時点で固定する。

| 基準 | 判定 |
|------|------|
| 新規ページを作成したのに Router に route がない | REJECT |
| basename 配下の URL と route path の対応を確認していない | REJECT |
| 画面実装と同時に Router / 導線 / 一時導線の要否を判断している | OK |
| 開発用の一時導線を使う場合、その理由と後で除去する前提を記録している | OK |
| route を更新したが、メニュー・ボタン・リンク・外部呼び出しなど実際の入口を未確認 | 警告 |

```tsx
// OK - 画面実装と route 配線を同時に追加
<Route path="/contreg" element={<ContainerRegisterPage />} />

// REJECT - 画面実装はあるが到達経路がない
// src/pages/ContainerRegisterPage.tsx は存在する
// Router には route がない
```

到達経路は Router だけではない。メニュー、一覧からの遷移ボタン、ダイアログ内の確定導線、外部画面からのリンクなど、利用者が実際にたどる入口を基準に確認する。

### 外部UIライブラリとの統合

DataGrid、日付ピッカー、チャート、仮想リストのような外部 UI ライブラリは、型が通っても実行時に落ちることがある。特にメジャーバージョン差分では、props 名や state model の互換性を shallow なモックだけでは検出できない。

| 基準 | 判定 |
|------|------|
| 主要 UI ライブラリの props を、既存プロジェクトのバージョン確認なしに推測で渡す | REJECT |
| テストでライブラリ本体を完全にモックし、実マウント時の破綻を見逃す | 警告 |
| 代表的な props で実コンポーネントを描画し、画面レベルでクラッシュしないことを確認する | OK |
| 既存画面の利用パターンやプロジェクト依存バージョンを参照して props 形を決める | OK |

## コンポーネント設計

1ファイルにベタ書きしない。必ずコンポーネント分割する。

分離が必須なケース:
- 独自のstateを持つ → 必ず分離
- 50行超のJSX → 分離
- 再利用可能 → 分離
- 責務が複数 → 分離
- ページ内の独立したセクション → 分離

| 基準 | 判定 |
|------|------|
| 1コンポーネント200行超 | 分割を検討 |
| 1コンポーネント300行超 | Warning。分割を提案 |
| 表示とロジックが混在 | 分離を検討 |
| Props drilling（3階層以上） | 状態管理の導入を検討 |
| 複数の責務を持つコンポーネント | REJECT |

コンポーネント行数はレビュー観点であり、unit test や snapshot test の失敗条件にしない。

良いコンポーネント:
- 単一責務: 1つのことをうまくやる
- 自己完結: 必要な依存が明確
- テスト可能: 副作用が分離されている

コンポーネント分類:

| 種類 | 責務 | 例 |
|------|------|-----|
| Container | データ取得・状態管理 | `UserListContainer` |
| Presentational | 表示のみ | `UserCard` |
| Layout | 配置・構造 | `PageLayout`, `Grid` |
| Utility | 共通機能 | `ErrorBoundary`, `Portal` |

### UIプリミティブの設計原則

shared/components/ui/ に配置するHTML要素ラッパーの設計ルール:

- `forwardRef` で ref を転送する（外部からの制御を可能にする）
- `className` を受け取り、外からスタイル拡張可能にする
- ネイティブ props をスプレッドで透過する（`...props`）
- variants は別ファイルに分離する（`button.variants.ts`）

```tsx
// CORRECT - プリミティブの設計
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant, size, className, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      >
        {children}
      </button>
    )
  }
)

// WRONG - refもclassNameも透過しない閉じたコンポーネント
export const Button = ({ label, onClick }: { label: string; onClick: () => void }) => {
  return <button className="fixed-style" onClick={onClick}>{label}</button>
}
```

ディレクトリ構成:
```
features/{feature-name}/
├── components/
│   ├── {feature}-view.tsx      # メインビュー（子を組み合わせる）
│   ├── {sub-component}.tsx     # サブコンポーネント
│   └── index.ts
├── hooks/
├── types.ts
└── index.ts
```

## 状態管理

子コンポーネントは自身で状態を変更しない。イベントを親にバブリングし、親が状態を操作する。

```tsx
// 子が自分で状態を変更（NG）
const ChildBad = ({ initialValue }: { initialValue: string }) => {
  const [value, setValue] = useState(initialValue)
  return <input value={value} onChange={e => setValue(e.target.value)} />
}

// 親が状態を管理、子はコールバックで通知（OK）
const ChildGood = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => {
  return <input value={value} onChange={e => onChange(e.target.value)} />
}

const Parent = () => {
  const [value, setValue] = useState('')
  return <ChildGood value={value} onChange={setValue} />
}
```

例外（子がローカルstate持ってOK）:
- UI専用の一時状態（ホバー、フォーカス、アニメーション）
- 親に伝える必要がない完全にローカルな状態

| 基準 | 判定 |
|------|------|
| 不要なグローバル状態 | ローカル化を検討 |
| 同じ状態が複数箇所で管理 | 正規化が必要 |
| 子から親への状態変更（逆方向データフロー） | REJECT |
| APIレスポンスをそのまま状態に | 正規化を検討 |
| useEffectの依存配列が不適切 | REJECT |
| 初期取得が不安定な Context/Provider 関数参照に結び付いている | REJECT |

状態配置の判断基準:

| 状態の性質 | 推奨配置 |
|-----------|---------|
| UIの一時的な状態（モーダル開閉等） | ローカル（useState） |
| フォームの入力値 | ローカル or フォームライブラリ |
| 複数コンポーネントで共有 | Context or 状態管理ライブラリ |
| サーバーデータのキャッシュ | TanStack Query等のデータフェッチライブラリ |

## APIクライアント生成

プロジェクトがAPIクライアント生成ツール（Orval、openapi-typescript等）を採用している場合、新規APIエンドポイントとの接続には必ず生成されたクライアントを使用する。

| パターン | 判定 |
|---------|------|
| 生成ツールが存在するのに axiosInstance/fetch を直接使用 | REJECT |
| 生成ツールの設定を確認せずにAPIフックを手書き | REJECT |
| 生成ツールが存在しないプロジェクトで直接呼び出し | OK |

確認手順:
1. プロジェクトにAPI生成設定があるか確認（orval.config.ts, openapi-generator 等）
2. 既存の生成済みクライアントの使用パターンを確認
3. 新規エンドポイントは生成パイプラインに追加し、生成されたフックを使う

## 初期表示ロードと再取得境界

初期表示ロードはリアクティブな再取得と分けて扱う。URL、フィルタ、ページング、明示的な更新操作がない限り、初回ロードは mount-only に保ち、不安定なコールバック参照に結び付けない。

| 基準 | 判定 |
|------|------|
| Provider/Context の関数参照変化で初期取得が再実行される | REJECT |
| 再取得条件が URL・フィルタ・ページング・更新操作として明示されている | OK |
| メッセージ表示、loading 切替、dialog 開閉で再取得される | REJECT |
| 初期取得は mount-only、以後の再取得は明示トリガーで行う | OK |

## データ取得

API呼び出しはルート（View）コンポーネントで行い、子コンポーネントにはpropsで渡す。

```tsx
// CORRECT - ルートでデータ取得、子に渡す
const OrderDetailView = () => {
  const { data: order, isLoading, error } = useGetOrder(orderId)
  const { data: items } = useListOrderItems(orderId)

  if (isLoading) return <Skeleton />
  if (error) return <ErrorDisplay error={error} />

  return (
    <OrderSummary
      order={order}
      items={items}
      onItemSelect={handleItemSelect}
    />
  )
}

// WRONG - 子コンポーネントが自分でデータ取得
const OrderSummary = ({ orderId }) => {
  const { data: order } = useGetOrder(orderId)
  // ...
}
```

UIの状態変更でパラメータが変わる場合（週切り替え、フィルタ等）:

状態もViewレベルで管理し、コンポーネントにはコールバックを渡す。

```tsx
// CORRECT - 状態もViewで管理
const ScheduleView = () => {
  const [currentWeek, setCurrentWeek] = useState(startOfWeek(new Date()))
  const { data } = useListSchedules({
    from: format(currentWeek, 'yyyy-MM-dd'),
    to: format(endOfWeek(currentWeek), 'yyyy-MM-dd'),
  })

  return (
    <WeeklyCalendar
      schedules={data?.items ?? []}
      currentWeek={currentWeek}
      onWeekChange={setCurrentWeek}
    />
  )
}

// WRONG - コンポーネント内で状態管理+データ取得
const WeeklyCalendar = ({ facilityId }) => {
  const [currentWeek, setCurrentWeek] = useState(...)
  const { data } = useListSchedules({ facilityId, from, to })
  // ...
}
```

例外（コンポーネント内フェッチが許容されるケース）:

| ケース | 理由 |
|--------|------|
| 独立ウィジェット | どのページにも置ける自己完結型コンポーネント |
| 無限スクロール | スクロール位置というUI内部状態に依存 |
| 検索オートコンプリート | 入力値に依存したリアルタイム検索 |
| リアルタイム更新 | WebSocket/Pollingでの自動更新 |
| モーダル内の詳細取得 | 開いたときだけ追加データを取得 |

### 独立ウィジェットパターン

どのページにも「置くだけ」で動く自己完結型コンポーネント（通知バッジ、ログインユーザー表示等）。

ウィジェットと判定する条件（すべて満たすこと）:
- 親のデータと完全に無関係
- 親の状態に影響を与えない
- どのページに置いても同じ動作をする

1つでも満たさない場合は View でデータ取得し、props で渡す。

```tsx
// WRONG - orderId という親のコンテキストに依存。ウィジェットではない
const OrderStatusWidget = ({ orderId }: { orderId: string }) => {
  const { data } = useGetOrder(orderId)
  return <StatusBadge status={data?.status} />
}

// CORRECT - 親のデータフローに参加するならpropsで受け取る
const OrderStatusWidget = ({ status }: { status: OrderStatus }) => {
  return <StatusBadge status={status} />
}
```

| 基準 | 判定 |
|------|------|
| コンポーネント内で直接fetch | Container層に分離 |
| エラーハンドリングなし | REJECT |
| ローディング状態の未処理 | REJECT |
| N+1クエリ的なフェッチ | REJECT |

### 画面専用APIの利用

画面が必要とするデータは、その画面専用のAPIエンドポイントから取得する。既存の汎用APIを流用して画面を組み立てない。APIが存在しない場合は、フロントで回避するのではなく、バックエンドに専用エンドポイントの追加を先に行う。

| 基準 | 判定 |
|------|------|
| 一覧APIのレスポンスを詳細画面でも使い回す | REJECT |
| 一覧の表示単位とAPIの取得単位がずれている | REJECT |
| 判定だけのために全件取得する（集計APIを使うべき） | REJECT |
| 画面ごとに専用の取得口を持ち、必要なデータだけ返す | OK |

```tsx
// REJECT - 一覧APIを詳細画面で流用
const DetailScreen = ({ itemId }) => {
  const { data: list } = useListItems({ date })
  const item = list?.items.find(i => i.id === itemId)
  return <Detail item={item} />
}

// OK - 詳細画面は詳細APIを使う
const DetailScreen = ({ itemId }) => {
  const { data: item } = useGetItem(itemId)
  return <Detail item={item} />
}
```

### 通信スコープの限定

通信はタブ・画面単位で閉じる。他タブのために先読みしない。定期ポーリングは表示中の画面だけで行う。

| 基準 | 判定 |
|------|------|
| タブ切替で表示中の画面だけが通信する | OK |
| 全タブ共通の親でまとめて通信し、子タブに配る | REJECT |
| 非表示タブでもポーリングが動き続ける | REJECT |

## 共有コンポーネントと抽象化

### カテゴリ分類

shared コンポーネントは責務別にサブディレクトリで分類する。

```
shared/components/
├── ui/              # HTMLプリミティブのラッパー（Button, Card, Badge, Dialog）
├── form/            # フォーム入力要素（TextInput, Select, Checkbox）
├── layout/          # ページ構造・ルート保護（Layout, ProtectedRoute）
├── navigation/      # ナビゲーション（Tabs, BackLink, SidebarItem）
├── data-display/    # データ表示（Table, DetailField, Calendar）
├── feedback/        # 状態フィードバック（LoadingState, ErrorState）
├── domain/          # ドメイン固有だが横断的（StatusBadge, CategoryBadge）
└── index.ts         # barrel export
```

| カテゴリ | 配置基準 |
|---------|---------|
| ui/ | HTML要素を薄くラップ。ドメイン知識を持たない |
| form/ | ラベル・エラー・必須マークを統合したフォーム部品 |
| layout/ | ページ全体の骨格。認証・ロール制御を含む |
| domain/ | 特定ドメインに依存するが、複数 feature で共有 |

ui/ と domain/ の判断基準: ドメイン用語がコンポーネント名やpropsに含まれるなら domain/。

### 共有化の基準

同じパターンのUIは共有コンポーネント化する。インラインスタイルのコピペは禁止。

```tsx
// WRONG - インラインスタイルのコピペ
<button className="p-2 text-[var(--text-secondary)] hover:...">
  <X className="w-5 h-5" />
</button>

// CORRECT - 共有コンポーネント使用
<IconButton onClick={onClose} aria-label="閉じる">
  <X className="w-5 h-5" />
</IconButton>
```

共有コンポーネント化すべきパターン:
- アイコンボタン（閉じる、編集、削除等）
- ローディング/エラー表示
- ステータスバッジ
- タブ切り替え
- ラベル+値の表示（詳細画面）
- 検索入力
- カラー凡例

過度な汎用化を避ける:

```tsx
// WRONG - IconButtonに無理やりステッパー用バリアントを追加
export const iconButtonVariants = cva('...', {
  variants: {
    variant: {
      default: '...',
      outlined: '...',  // ステッパー専用、他で使わない
    },
    size: {
      medium: 'p-2',
      stepper: 'w-8 h-8',  // outlinedとセットでしか使わない
    },
  },
})

// CORRECT - 用途別に専用コンポーネント
export function StepperButton(props) {
  return (
    <button className="w-8 h-8 rounded-full border ..." {...props}>
      <Plus className="w-4 h-4" />
    </button>
  )
}
```

別コンポーネントにすべきサイン:
- 「このvariantはこのsizeとセット」のような暗黙の制約がある
- 追加したvariantが元のコンポーネントの用途と明らかに違う
- 使う側のprops指定が複雑になる

### テーマ差分とデザイントークン

同じ機能コンポーネントを再利用しつつ見た目だけ変える場合は、デザイントークン + テーマスコープで管理する。

原則:
- 色・余白・角丸・影・タイポをトークン（CSS Variables）として定義する
- 画面/ロール別の差分はテーマスコープ（例: `.consumer-theme`, `.admin-theme`）で上書きする
- コンポーネント内に16進カラー値（`#xxxxxx`）を直書きしない
- ロジック差分（API・状態管理）と見た目差分（トークン）を混在させない

```css
/* tokens.css */
:root {
  --color-bg-page: #f3f4f6;
  --color-surface: #ffffff;
  --color-text-primary: #1f2937;
  --color-border: #d1d5db;
  --color-accent: #2563eb;
}

.consumer-theme {
  --color-bg-page: #f7f8fa;
  --color-accent: #4daca1;
}
```

```tsx
// same component, different look by scope
<div className="consumer-theme">
  <Button variant="primary">Submit</Button>
</div>
```

運用ルール:
- 共通UI（Button/Card/Input/Tabs）はトークン参照のみで実装する
- feature側はテーマ共通クラス（例: `surface`, `title`, `chip`）を利用し、装飾ロジックを重複させない
- 追加テーマ実装時は「トークン追加 → スコープ上書き → 既存コンポーネント流用」の順で進める

レビュー観点:
- 直書き色・直書き余白のコピペがないか
- 同一UIパターンがテーマごとに別コンポーネント化されていないか
- 見た目変更のためにデータ取得/状態管理が改変されていないか

NG例:
- 見た目差分のために `ButtonConsumer`, `ButtonAdmin` を乱立
- featureコンポーネントごとに色を直書き
- テーマ切り替えのたびにAPIレスポンス整形ロジックを変更

## 抽象化レベルの評価

### 条件分岐の肥大化検出

| パターン | 判定 |
|---------|------|
| 同じ条件分岐が3箇所以上 | 共通コンポーネントに抽出 → REJECT |
| propsによる分岐が5種類以上 | コンポーネント分割を検討 |
| render内の三項演算子のネスト | 早期リターンまたはコンポーネント分離 → REJECT |
| 型による分岐レンダリング | ポリモーフィックコンポーネントを検討 |

### 抽象度の不一致検出

| パターン | 問題 | 修正案 |
|---------|------|--------|
| データ取得ロジックがJSXに混在 | 読みにくい | カスタムフックに抽出 |
| ビジネスロジックがコンポーネントに混在 | 責務違反 | hooks/utilsに分離 |
| スタイル計算ロジックが散在 | 保守困難 | ユーティリティ関数に抽出 |
| 同じ変換処理が複数箇所に | DRY違反 | 共通関数に抽出 |

良い抽象化の例:

```tsx
// 条件分岐が肥大化
function UserBadge({ user }) {
  if (user.role === 'admin') {
    return <span className="bg-red-500">管理者</span>
  } else if (user.role === 'moderator') {
    return <span className="bg-yellow-500">モデレーター</span>
  } else if (user.role === 'premium') {
    return <span className="bg-purple-500">プレミアム</span>
  } else {
    return <span className="bg-gray-500">一般</span>
  }
}

// Mapで抽象化
const ROLE_CONFIG = {
  admin: { label: '管理者', className: 'bg-red-500' },
  moderator: { label: 'モデレーター', className: 'bg-yellow-500' },
  premium: { label: 'プレミアム', className: 'bg-purple-500' },
  default: { label: '一般', className: 'bg-gray-500' },
}

function UserBadge({ user }) {
  const config = ROLE_CONFIG[user.role] ?? ROLE_CONFIG.default
  return <span className={config.className}>{config.label}</span>
}
```

```tsx
// 抽象度が混在
function OrderList() {
  const [orders, setOrders] = useState([])
  useEffect(() => {
    fetch('/api/orders')
      .then(res => res.json())
      .then(data => setOrders(data))
  }, [])

  return orders.map(order => (
    <div>{order.total.toLocaleString()}円</div>
  ))
}

// 抽象度を揃える
function OrderList() {
  const { data: orders } = useOrders()  // データ取得を隠蔽

  return orders.map(order => (
    <OrderItem key={order.id} order={order} />
  ))
}
```

## フロントエンドとバックエンドの責務分離

### 表示形式の責務

バックエンドは「データ」を返し、フロントエンドが「表示形式」に変換する。

```tsx
// フロントエンド: 表示形式に変換
export function formatPrice(amount: number): string {
  return `¥${amount.toLocaleString()}`
}

export function formatDate(date: Date): string {
  return format(date, 'yyyy年M月d日')
}
```

| 基準 | 判定 |
|------|------|
| バックエンドが表示用文字列を返している | 設計見直しを提案 |
| 同じフォーマット処理が複数箇所にコピペ | ユーティリティ関数に統一 |
| コンポーネント内でインラインフォーマット | 関数に抽出 |

### ドメインロジックの配置（SmartUI排除）

ドメインロジック（ビジネスルール）はバックエンドに配置。フロントエンドは状態の表示・編集のみ。

ドメインロジックとは:
- 集約のビジネスルール（在庫判定、価格計算、ステータス遷移）
- バリデーション（業務制約の検証）
- 不変条件の保証

フロントエンドの責務:
- サーバーから受け取った状態を表示
- ユーザー入力を収集し、コマンドとしてバックエンドに送信
- UI専用の一時状態管理（フォーカス、ホバー、モーダル開閉）
- 表示形式の変換（フォーマット、ソート、フィルタ）

| 基準 | 判定 |
|------|------|
| フロントエンドで価格計算・在庫判定 | バックエンドに移動 → REJECT |
| フロントエンドでステータス遷移ルール | バックエンドに移動 → REJECT |
| フロントエンドでビジネスバリデーション | バックエンドに移動 → REJECT |
| サーバー側で計算可能な値をフロントで再計算 | 冗長 → REJECT |

良い例 vs 悪い例:

```tsx
// BAD - フロントエンドでビジネスルール
function OrderForm({ order }: { order: Order }) {
  const totalPrice = order.items.reduce((sum, item) =>
    sum + item.price * item.quantity, 0
  )
  const canCheckout = totalPrice >= 1000 && order.items.every(i => i.stock > 0)

  return <button disabled={!canCheckout}>注文確定</button>
}

// GOOD - バックエンドから受け取った状態を表示
function OrderForm({ order }: { order: Order }) {
  // totalPrice, canCheckout はサーバーから受け取る
  return (
    <>
      <div>{formatPrice(order.totalPrice)}</div>
      <button disabled={!order.canCheckout}>注文確定</button>
    </>
  )
}
```

```tsx
// BAD - フロントエンドでステータス遷移判定
function TaskCard({ task }: { task: Task }) {
  const canStart = task.status === 'pending' && task.assignee !== null
  const canComplete = task.status === 'in_progress' && /* 複雑な条件... */

  return (
    <>
      <button onClick={startTask} disabled={!canStart}>開始</button>
      <button onClick={completeTask} disabled={!canComplete}>完了</button>
    </>
  )
}

// GOOD - サーバーが許可するアクションを返す
function TaskCard({ task }: { task: Task }) {
  // task.allowedActions = ['start', 'cancel'] など、サーバーが計算
  const canStart = task.allowedActions.includes('start')
  const canComplete = task.allowedActions.includes('complete')

  return (
    <>
      <button onClick={startTask} disabled={!canStart}>開始</button>
      <button onClick={completeTask} disabled={!canComplete}>完了</button>
    </>
  )
}
```

例外（フロントエンドにロジックを置いてもOK）:

| ケース | 理由 |
|--------|------|
| UI専用バリデーション | 「必須入力」「文字数制限」等のUXフィードバック（サーバー側でも検証必須） |
| クライアント側フィルタ/ソート | サーバーから受け取ったリストの表示順序変更 |
| 表示条件の分岐 | 「ログイン済みなら詳細表示」等のUI制御 |
| リアルタイムフィードバック | 入力中のプレビュー表示 |

判断基準: 「この計算結果がサーバーとズレたら業務が壊れるか?」
- YES → バックエンドに配置（ドメインロジック）
- NO → フロントエンドでもOK（表示ロジック）

## 横断的関心事の処理層

横断的関心事は適切な層で処理する。コンポーネント内に散在させない。

| 関心事 | 処理層 | パターン |
|-------|--------|---------|
| 認証トークン付与 | APIクライアント層 | リクエストインターセプタ |
| 認証エラー（401/403） | APIクライアント層 | レスポンスインターセプタ |
| ルート保護 | レイアウト層 | ProtectedRoute + Outlet |
| ロール別振り分け | レイアウト層 | ユーザー種別による分岐 |
| ローディング/エラー表示 | View（Container）層 | 早期リターン |

```tsx
// CORRECT - 横断的関心事はインターセプタ層で処理
// api/axios-instance.ts
instance.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// WRONG - 各コンポーネントで個別にトークンを付与
const MyComponent = () => {
  const token = localStorage.getItem('auth_token')
  const { data } = useQuery({
    queryFn: () => fetch('/api/data', {
      headers: { Authorization: `Bearer ${token}` },
    }),
  })
}
```

```tsx
// CORRECT - ルート保護はレイアウト層で
// shared/components/layout/protected-route.tsx
function ProtectedRoute() {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Layout><Outlet /></Layout>
}

// routes でラップ
<Route element={<ProtectedRoute />}>
  <Route path="/dashboard" element={<DashboardView />} />
</Route>

// WRONG - 各ページで個別に認証チェック
function DashboardView() {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" />
  return <div>...</div>
}
```

## パフォーマンス

| 基準 | 判定 |
|------|------|
| 不要な再レンダリング | 最適化が必要 |
| 大きなリストの仮想化なし | 警告 |
| 画像の最適化なし | 警告 |
| バンドルに未使用コード | tree-shakingを確認 |
| メモ化の過剰使用 | 本当に必要か確認 |

最適化チェックリスト:
- `React.memo` / `useMemo` / `useCallback` は適切か
- 大きなリストは仮想スクロール対応か
- Code Splittingは適切か
- 画像はlazy loadingされているか

アンチパターン:

```tsx
// レンダリングごとに新しいオブジェクト
<Child style={{ color: 'red' }} />

// 定数化 or useMemo
const style = useMemo(() => ({ color: 'red' }), []);
<Child style={style} />
```

## アクセシビリティ

| 基準 | 判定 |
|------|------|
| インタラクティブ要素にキーボード対応なし | REJECT |
| 画像にalt属性なし | REJECT |
| フォーム要素にlabelなし | REJECT |
| 色だけで情報を伝達 | REJECT |
| フォーカス管理の欠如（モーダル等） | REJECT |

チェックリスト:
- セマンティックHTMLを使用しているか
- ARIA属性は適切か（過剰でないか）
- キーボードナビゲーション可能か
- スクリーンリーダーで意味が通じるか
- カラーコントラストは十分か

## TypeScript/型安全性

| 基準 | 判定 |
|------|------|
| `any` 型の使用 | REJECT |
| 型アサーション（as）の乱用 | 要検討 |
| Props型定義なし | REJECT |
| イベントハンドラの型が不適切 | 修正が必要 |

## フロントエンドセキュリティ

| 基準 | 判定 |
|------|------|
| dangerouslySetInnerHTML使用 | XSSリスクを確認 |
| ユーザー入力の未サニタイズ | REJECT |
| 機密情報のフロントエンド保存 | REJECT |
| CSRFトークンの未使用 | 要確認 |

## テスタビリティ

| 基準 | 判定 |
|------|------|
| data-testid等の未付与 | 警告 |
| テスト困難な構造 | 分離を検討 |
| ビジネスロジックのUIへの埋め込み | REJECT |

## アンチパターン検出

以下を見つけたら REJECT:

| アンチパターン | 問題 |
|---------------|------|
| God Component | 1コンポーネントに全機能が集中 |
| Prop Drilling | 深いPropsバケツリレー |
| Inline Styles乱用 | 保守性低下 |
| useEffect地獄 | 依存関係が複雑すぎる |
| Premature Optimization | 不要なメモ化 |
| Magic Strings | ハードコードされた文字列 |
| Hidden Dependencies | 子コンポーネントの隠れたAPI呼び出し |
| Over-generalization | 無理やり汎用化したコンポーネント |


---

# React知識

## effect と再実行

`useEffect` は「いつ再実行してよいか」を明示する仕組みであり、初期化処理の置き場ではない。初期表示で1回だけ行う処理か、依存変化で再実行すべき処理かを先に決める。

| 基準 | 判定 |
|------|------|
| 初期表示の一度きりのロードなのに、再生成される関数参照を依存に置く | REJECT |
| 再取得条件が明確でないのに、Context/Provider 由来関数を依存に置く | REJECT |
| mount-only 初期化を `useEffect(..., [])` で表現し、意図をコメントで残す | OK |
| 依存変化時の再取得が仕様として必要で、その依存を明示している | OK |

```tsx
// REJECT - 初期取得なのに不安定な関数依存を経由して再実行されうる
const fetchList = useCallback(async () => {
  await loadItems()
}, [setIsLoading, errorPage])

useEffect(() => {
  fetchList()
}, [fetchList])

// OK - 初期表示の一度きりロードとして固定
useEffect(() => {
  void loadItemsOnMount()
  // mount-only initial load
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [])
```

## Context と Provider value

Context の `value={{ ... }}` は Provider の再描画ごとに新しい参照になる。Context から受け取った関数を `useEffect` の依存に置くと、利用側が意図せず再実行ループに入ることがある。

| 基準 | 判定 |
|------|------|
| Context 由来関数の参照安定性を確認せず、effect 依存に入れる | REJECT |
| Provider 側で value の安定性が保証されていないのに mount effect の依存に使う | REJECT |
| Context 関数はイベントハンドラから使い、初期取得は mount-only に閉じる | OK |
| Provider 側で value 安定化を行い、再取得条件も仕様で定義する | OK |

```tsx
// REJECT - Context 関数をそのまま初期取得 effect の依存に使う
const { setIsLoading, errorPage } = useAppContext()
useEffect(() => {
  void loadInitialData(setIsLoading, errorPage)
}, [setIsLoading, errorPage])

// OK - 初期取得は mount-only、Context 関数は内部で使う
const { setIsLoading, errorPage } = useAppContext()
useEffect(() => {
  void loadInitialData({ setIsLoading, errorPage })
  // mount-only initial load
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [])
```

## 初期表示ロード

初期表示ロードは「画面を開いたときに1回だけ必要な処理」か、「状態変化に応じて再実行する処理」かを区別する。後者でない限り、再取得のトリガーは明示的なユーザー操作や URL/検索条件の変化に限定する。

| 条件 | 推奨 |
|------|------|
| 初期表示で一覧を1回読むだけ | mount-only effect |
| フィルタ、ページング、URL パラメータ変更で再取得 | その状態を依存に明示 |
| loading state 更新で再取得が走る | REJECT |
| message 表示や dialog 開閉で再取得が走る | REJECT |

## データフェッチライブラリのキャッシュ適性

データフェッチライブラリ（React Query 等）のキャッシュはすべてのデータ取得に適するわけではない。データの変動頻度とページング方式で判断する。

| データ特性 | キャッシュ | 判定 |
|-----------|----------|------|
| 単一リソースの詳細（設定値、プロフィール等） | 有効 | OK |
| 安定した一覧（マスタデータ、変更頻度が低い） | 有効 | OK |
| cursor ページングかつ途中で追加・削除・並び替えが起きる一覧 | 無効 | local state で取得 |
| offset ページングかつ途中でデータ変動が起きる一覧 | 無効 | local state で取得 |

cursor ページングとキャッシュの相性が悪い理由:

- nextId（cursor）が古くなり、次ページ取得で欠落や重複が発生する
- 削除された行を基準に次ページを取ると取りこぼしが起きる
- タブ復帰時に途中ページを自動再取得すると「いま見えている一覧」とサーバーの実態がズレる

データフェッチライブラリを使う場合でもキャッシュを実質無効にする必要があるなら、そのライブラリを使う意味がない。画面の責務として毎回取り直す方が安全。

```tsx
// REJECT - 変動する cursor paged 一覧に React Query のキャッシュを適用
const { data } = useInfiniteQuery({
  queryKey: ['records'],
  queryFn: ({ pageParam }) => fetchRecords(pageParam),
  getNextPageParam: (last) => last.nextId,
  staleTime: 5 * 60 * 1000,  // 途中で削除されうるのにキャッシュを効かせている
})

// OK - local state で画面の責務として取得
const [records, setRecords] = useState<Record[]>([])
const [nextId, setNextId] = useState<string | undefined>()

const loadMore = async () => {
  const result = await fetchRecords(nextId)
  setRecords(prev => [...prev, ...result.items])
  setNextId(result.nextId)
}
```

## custom hook の責務

React custom hook は「React の state/effect/ref を使う状態遷移」に限定する。純粋計算だけなら custom hook ではなく関数モジュールでよい。

| 基準 | 判定 |
|------|------|
| React の state/effect を使わないのに `use*` と命名する | 警告 |
| 純関数群を custom hook として扱う | 警告 |
| stateful な UI 制御は custom hook に、純粋計算は function module に分ける | OK |
| hook が JSX を返す | REJECT |

## exhaustive-deps の扱い

`react-hooks/exhaustive-deps` は無条件で従うものではなく、effect の意味を壊さない範囲で従う。mount-only 初期化で依存を増やすと挙動が壊れる場合は、理由を残して抑制する。

| 基準 | 判定 |
|------|------|
| ルールに従うためだけに不要な再実行依存を追加する | REJECT |
| lint 抑制を無言で入れる | 警告 |
| mount-only の理由をコメントで説明して抑制する | OK |
| 再実行が必要な effect なのに `[]` にする | REJECT |


---

# セキュリティ知識

## AI生成コードのセキュリティ問題

AI生成コードには特有の脆弱性パターンがある。

| パターン | リスク | 例 |
|---------|--------|-----|
| もっともらしいが危険なデフォルト | 高 | `cors: { origin: '*' }` は問題なく見えるが危険 |
| 古いセキュリティプラクティス | 中 | 非推奨の暗号化、古い認証パターンの使用 |
| 不完全なバリデーション | 高 | 形式は検証するがビジネスルールを検証しない |
| 入力を過度に信頼 | 重大 | 内部APIは常に安全と仮定 |
| コピペによる脆弱性 | 高 | 同じ危険なパターンが複数ファイルで繰り返される |

特に厳しく審査が必要:
- 認証・認可ロジック（AIはエッジケースを見落としがち）
- 入力バリデーション（AIは構文を検証しても意味を見落とす可能性）
- エラーメッセージ（AIは内部詳細を露出する可能性）
- 設定ファイル（AIは学習データから危険なデフォルトを使う可能性）

## 優先順位解決・オーバーライド・信頼境界

複数の設定ソースや定義ソースを優先順位で解決する仕組み、意図的なオーバーライド、拡張ポイントは、それ自体では脆弱性ではない。重要なのは、変更が信頼境界を壊したか、低信頼側に新しい攻撃能力を与えたかである。

| 基準 | 判定 |
|------|------|
| documented な優先順位に従い、同じ利用者・同じ trust level 内で設定や定義が解決される | OK |
| 明示的な selector や引数指定で対象が選ばれ、既存の優先順位モデルに従って解決される | OK |
| 低い優先順位の定義より高い優先順位の定義が採用されても、それが既存のカスタマイズ契約の範囲内で、権限拡大や新しいデータアクセスを伴わない | 警告以下。通常は REJECT にしない |
| 低信頼側が高信頼側の設定や定義を上書きでき、その結果として新しいコード実行、高信頼資産の内容変更、データ取得、認可回避が可能になる | REJECT |
| 対話的な確認ステップがなくなったが、明示指定で意図は十分に一意で、trust boundary も変わらない | OK |
| 対話的な確認ステップが唯一の境界防御であり、それを外すことで低信頼側の override が silent に有効になる | REJECT になりうる。攻撃前提と影響を具体化する |

### 判定のしかた

優先順位解決やオーバーライドを脆弱性として扱うには、次を具体的に示す必要がある。

- 誰が低信頼側で、どの入力や設定を制御できるか
- 何が高信頼資産か
- 変更前にはできず、変更後に初めて可能になったことは何か
- その挙動が仕様上の precedence や拡張点の範囲を超えている理由

既に複数スコープの定義ファイルや設定ソースで挙動を調整できる設計なら、同じ trust level の別の定義を選べるようになっただけでは、通常は新しい攻撃能力とはいえない。

## インジェクション攻撃

**SQLインジェクション**

- 文字列連結によるSQL構築 → REJECT
- パラメータ化クエリの不使用 → REJECT
- ORMの raw query での未サニタイズ入力 → REJECT

```typescript
// NG
db.query(`SELECT * FROM users WHERE id = ${userId}`)

// OK
db.query('SELECT * FROM users WHERE id = ?', [userId])
```

**コマンドインジェクション**

- `exec()`, `spawn()` での未検証入力 → REJECT
- シェルコマンド構築時のエスケープ不足 → REJECT

```typescript
// NG
exec(`ls ${userInput}`)

// OK
execFile('ls', [sanitizedInput])
```

**XSS (Cross-Site Scripting)**

- HTML/JSへの未エスケープ出力 → REJECT
- `innerHTML`, `dangerouslySetInnerHTML` の不適切な使用 → REJECT
- URLパラメータの直接埋め込み → REJECT

## 認証・認可

**認証の問題**

- ハードコードされたクレデンシャル → 即REJECT
- 平文パスワードの保存 → 即REJECT
- 弱いハッシュアルゴリズム (MD5, SHA1) → REJECT
- セッショントークンの不適切な管理 → REJECT

**認可の問題**

- 権限チェックの欠如 → REJECT
- IDOR (Insecure Direct Object Reference) → REJECT
- 権限昇格の可能性 → REJECT

```typescript
// NG - 権限チェックなし
app.get('/user/:id', (req, res) => {
  return db.getUser(req.params.id)
})

// OK
app.get('/user/:id', authorize('read:user'), (req, res) => {
  if (req.user.id !== req.params.id && !req.user.isAdmin) {
    return res.status(403).send('Forbidden')
  }
  return db.getUser(req.params.id)
})
```

## データ保護

**機密情報の露出**

- APIキー、シークレットのハードコーディング → 即REJECT
- ログへの機密情報出力 → REJECT
- エラーメッセージでの内部情報露出 → REJECT
- `.env` ファイルのコミット → REJECT

**データ検証**

- 入力値の未検証 → REJECT
- 型チェックの欠如 → REJECT
- サイズ制限の未設定 → REJECT

## ログとマスキング

機密情報がログやレスポンスに露出するのを防ぐ。

**ログに出力してはいけない情報:**
- パスワード、トークン、APIキー
- クレジットカード番号、個人識別番号
- セッションID、認証ヘッダの値
- 個人情報（メールアドレス、電話番号）のうち、デバッグ目的で不要なもの

**マスキングパターン:**

```typescript
// NG - パスワードがログに露出
logger.info('User login attempt', { email, password })

// OK - 機密フィールドを除外
logger.info('User login attempt', { email })
```

```kotlin
// NG - リクエスト全体をログ出力
logger.info("Request: {}", request)

// OK - 機密フィールドをマスク
logger.info("Request: userId={}, action={}", request.userId, request.action)
```

**構造化ログでのフィールドフィルタリング:**

ログ出力にオブジェクトを渡す場合、`toString()` や JSON シリアライズで機密フィールドが含まれないようにする。

```kotlin
// NG - data class の toString() がパスワードを含む
data class UserCredentials(val email: String, val password: String)

// OK - toString() をオーバーライドしてマスク
data class UserCredentials(val email: String, val password: String) {
    override fun toString(): String = "UserCredentials(email=$email, password=***)"
}
```

| 基準 | 判定 |
|------|------|
| ログ出力にパスワード・トークン・APIキーが含まれる | REJECT |
| エラーレスポンスにスタックトレースや内部パスが含まれる | REJECT |
| data class の toString() が機密フィールドを露出する | REJECT |
| ログレベルに関わらず機密情報が出力される可能性がある | REJECT |
| デバッグログに個人情報が含まれるが本番で無効化されている | 警告。設定ミスのリスクがある |

## 暗号化

- 弱い暗号アルゴリズムの使用 → REJECT
- 固定IV/Nonceの使用 → REJECT
- 暗号化キーのハードコーディング → 即REJECT
- HTTPSの未使用（本番環境） → REJECT

## ファイル操作

**パストラバーサル**

- ユーザー入力を含むファイルパス → REJECT
- `../` のサニタイズ不足 → REJECT

```typescript
// NG
const filePath = path.join(baseDir, userInput)
fs.readFile(filePath)

// OK
const safePath = path.resolve(baseDir, userInput)
if (!safePath.startsWith(path.resolve(baseDir))) {
  throw new Error('Invalid path')
}
```

**ファイルアップロード**

- ファイルタイプの未検証 → REJECT
- ファイルサイズ制限なし → REJECT
- 実行可能ファイルのアップロード許可 → REJECT

## 依存関係

- 既知の脆弱性を持つパッケージ → REJECT
- メンテナンスされていないパッケージ → 警告
- 不必要な依存関係 → 警告

## エラーハンドリング

- スタックトレースの本番露出 → REJECT
- 詳細なエラーメッセージの露出 → REJECT
- エラーの握りつぶし（セキュリティイベント） → REJECT

## レート制限・DoS対策

- レート制限の欠如（認証エンドポイント） → 警告
- リソース枯渇攻撃の可能性 → 警告
- 無限ループの可能性 → REJECT

## マルチテナントデータ分離

テナント境界を超えたデータアクセスを防ぐ。認可（誰が操作できるか）とスコーピング（どのテナントのデータか）は別の関心事。

| 基準 | 判定 |
|------|------|
| 読み取りはテナントスコープだが書き込みはスコープなし | REJECT |
| 書き込み操作でクライアント提供のテナントIDを使用 | REJECT |
| テナントリゾルバーを使うエンドポイントに認可制御がない | REJECT |
| ロール分岐の一部パスでテナント解決が未考慮 | REJECT |

### 読み書きの一貫性

テナントスコーピングは読み取りと書き込みの両方に適用する。片方だけでは、参照できないが変更できる状態が生まれる。

読み取りにテナントフィルタを追加したら、対応する書き込みも必ずテナント検証する。

### 書き込みのテナント検証

書き込み操作では、リクエストボディのテナントIDではなく認証済みユーザーから解決したテナントIDを使う。

```kotlin
// NG - クライアント提供のテナントIDを信頼
fun create(request: CreateRequest) {
    service.create(request.tenantId, request.data)
}

// OK - 認証情報からテナントを解決
fun create(request: CreateRequest) {
    val tenantId = tenantResolver.resolve()
    service.create(tenantId, request.data)
}
```

### 認可とリゾルバーの整合性

テナントリゾルバーが特定ロール（例: スタッフ）を前提とする場合、エンドポイントに対応する認可制御が必要。認可なしだと、前提外のロールがアクセスしてリゾルバーが失敗する。

```kotlin
// NG - リゾルバーが STAFF を前提とするが認可制御なし
fun getSettings(): SettingsResponse {
    val tenantId = tenantResolver.resolve()  // STAFF 以外で失敗
    return settingsService.getByTenant(tenantId)
}

// OK - 認可制御でロールを保証
@Authorized(roles = ["STAFF"])
fun getSettings(): SettingsResponse {
    val tenantId = tenantResolver.resolve()
    return settingsService.getByTenant(tenantId)
}
```

ロール分岐があるエンドポイントでは、全パスでテナント解決が成功するか検証する。

## OWASP Top 10 チェックリスト

| カテゴリ | 確認事項 |
|---------|---------|
| A01 Broken Access Control | 認可チェック、CORS設定 |
| A02 Cryptographic Failures | 暗号化、機密データ保護 |
| A03 Injection | SQL, コマンド, XSS |
| A04 Insecure Design | セキュリティ設計パターン |
| A05 Security Misconfiguration | デフォルト設定、不要な機能 |
| A06 Vulnerable Components | 依存関係の脆弱性 |
| A07 Auth Failures | 認証メカニズム |
| A08 Software Integrity | コード署名、CI/CD |
| A09 Logging Failures | セキュリティログ |
| A10 SSRF | サーバーサイドリクエスト |


---

# アーキテクチャ知識

## 構造・設計

**ファイル分割**

| 基準           | 判定 |
|--------------|------|
| 1ファイル200行超   | 分割を検討 |
| 1ファイル300行超   | Warning。分割を提案 |
| 1ファイルに複数の責務  | REJECT |
| 関連性の低いコードが同居 | REJECT |

行数は設計レビューや doctor で扱う警告観点であり、unit test や snapshot test の pass/fail 条件にしない。

**モジュール構成**

- 高凝集: 関連する機能がまとまっているか
- 低結合: モジュール間の依存が最小限か
- 循環依存がないか
- 適切なディレクトリ階層か

**操作の一覧性**

同じ汎用関数への呼び出しがコードベースに散在すると、システムが何をしているか把握できなくなる。操作には目的に応じた名前を付けて関数化し、関連する操作を1つのモジュールにまとめる。そのモジュールを読めば「このシステムが行う操作の全体像」がわかる状態にする。

| 判定 | 基準 |
|------|------|
| REJECT | 同じ汎用関数が目的の異なる3箇所以上から直接呼ばれている |
| REJECT | 呼び出し元を全件 grep しないとシステムの操作一覧がわからない |
| OK | 目的ごとに名前付き関数が定義され、1モジュールに集約されている |

**パブリック API の公開範囲**

パブリック API が公開するのは、ドメインの操作に対応する関数・型のみ。インフラの実装詳細（特定プロバイダーの関数、内部パーサー等）を公開しない。

| 判定 | 基準 |
|------|------|
| REJECT | インフラ層の関数がパブリック API からエクスポートされている |
| REJECT | 内部実装の関数が外部から直接呼び出し可能になっている |
| OK | 外部消費者がドメインレベルの抽象のみを通じて対話する |

**関数設計**

- 1関数1責務になっているか
- 30行を超える関数は分割を検討
- 副作用が明確か

**レイヤー設計**

- 依存の方向: 上位層 → 下位層（逆方向禁止）
- Controller → Service → Repository の流れが守られているか
- 1インターフェース = 1責務（巨大なServiceクラス禁止）

**ディレクトリ構造**

構造パターンの選択:

| パターン | 適用場面 | 例 |
|---------|---------|-----|
| レイヤード | 小規模、CRUD中心 | `controllers/`, `services/`, `repositories/` |
| Vertical Slice | 中〜大規模、機能独立性が高い | `features/auth/`, `features/order/` |
| ハイブリッド | 共通基盤 + 機能モジュール | `core/` + `features/` |

Vertical Slice Architecture（機能単位でコードをまとめる構造）:

```
src/
├── features/
│   ├── auth/
│   │   ├── LoginCommand.ts
│   │   ├── LoginHandler.ts
│   │   ├── AuthRepository.ts
│   │   └── auth.test.ts
│   └── order/
│       ├── CreateOrderCommand.ts
│       ├── CreateOrderHandler.ts
│       └── ...
└── shared/           # 複数featureで共有
    ├── database/
    └── middleware/
```

Vertical Slice の判定基準:

| 基準 | 判定 |
|------|------|
| 1機能が3ファイル以上のレイヤーに跨る | Slice化を検討 |
| 機能間の依存がほぼない | Slice化推奨 |
| 共通処理が50%以上 | レイヤード維持 |
| チームが機能別に分かれている | Slice化必須 |

禁止パターン:

| パターン | 問題 |
|---------|------|
| `utils/` の肥大化 | 責務不明の墓場になる |
| `common/` への安易な配置 | 依存関係が不明確になる |
| 深すぎるネスト（4階層超） | ナビゲーション困難 |
| 機能とレイヤーの混在 | `features/services/` は禁止 |

**責務の分離**

- 読み取りと書き込みの責務が分かれているか
- データ取得はルート（View/Controller）で行い、子に渡しているか
- エラーハンドリングが一元化されているか（各所でtry-catch禁止）
- ビジネスロジックがController/Viewに漏れていないか

## 境界での解決

設定、Option、provider、権限、パスのような値は、境界で解決してから内部へ渡す。メイン処理は「何が解決済みか」を前提に組み立て、各所で設定ソースを問い合わせない。

| 基準 | 判定 |
|------|------|
| 入口で `ExecutionContext` や `ResolvedOptions` のような解決済みオブジェクトを作る | OK |
| オーケストレーション層が解決済みの値だけを扱う | OK |
| 下位層が global/project/env を再読込して同じ値を再解決する | REJECT |
| 表示用と実行用で別々の解決関数を持つ | REJECT |
| 未解決の options を深い層まで運び、先で `??` 解決する | REJECT |

```typescript
// REJECT - 実行層が設定ソースを直接知っている
async function executeWorkflow(options) {
  const engine = new WorkflowEngine({
    provider: options.provider ?? globalConfig.provider,
  });
}

class AgentRunner {
  run(step, options) {
    const provider = options.provider ?? resolveProviderFromConfig();
    return getProvider(provider).call();
  }
}

// OK - 境界で解決し、内部は解決済み値を使う
async function executeWorkflow(options) {
  const context = resolveExecutionContext(options);
  const engine = new WorkflowEngine(context);
}

class AgentRunner {
  run(step, options) {
    return getProvider(options.resolvedProvider).call();
  }
}
```

### Tell, Don't Ask

下位層に設定ソースを問い合わせさせるのではなく、上位層が「これを使え」と解決済みの値を渡す。値の選択責務と実行責務を分離する。

| パターン | 判定 |
|---------|------|
| 上位層が `resolvedProvider` のような値を渡す | OK |
| 下位層が `options` を覗いて自前で解決する | REJECT |
| 実行オブジェクトが `setup(config)` 後は `run()` だけ公開する | OK |
| 実行中に `getGlobalConfig()` を呼んで分岐する | REJECT |

### 腐敗防止層

優先順位解決や外部設定形式の吸収は、境界の専用層に閉じ込める。内部モデルへは正規化済みの値だけを渡す。

| パターン | 判定 |
|---------|------|
| YAML/env/CLI 差分を resolver/adapter に閉じ込める | OK |
| ドメイン層が env 名や設定キー文字列を直接扱う | REJECT |
| 外部形式から内部形式への変換が1箇所に集約されている | OK |
| 同じ正規化ロジックが複数箇所にコピーされている | REJECT |

### フェーズ分離

入力、解釈、実行、出力を段階で分ける。反復処理は、できる限り「解釈済みの入力をまとめて受け取り、実行だけを繰り返す」構造にする。

| 基準 | 判定 |
|------|------|
| 入口で raw input を `Resolved*` 型へ変換してから本処理に渡す | OK |
| ループ本体が解決済みデータに対する実行だけを担う | OK |
| ループ内で毎回 config/env/option を解釈する | REJECT |
| 反復ごとに「入力取得→解釈→実行→出力」を1関数に詰め込む | REJECT |
| 最適化で逐次処理が必要でも、解釈フェーズを専用メソッドに隔離している | OK |

```typescript
// REJECT - 各反復が入力解釈まで担う
for (const item of items) {
  const resolved = resolveItem(item, rawOptions, config);
  const result = execute(resolved);
  output(result);
}

// OK - 先に解釈し、反復は実行だけ
const resolvedItems = items.map((item) => resolveItem(item, rawOptions, config));

for (const item of resolvedItems) {
  const result = execute(item);
  output(result);
}
```

逐次解釈が必要なケースでも、`nextRawInput()` と `resolveInput()` と `executeResolved()` の責務は分ける。性能要件でフェーズを近づけても、責務まで混ぜない。

## コード品質の検出手法

**説明コメント（What/How）の検出基準**

コードの動作をそのまま言い換えているコメントを検出する。

| 判定 | 基準 |
|------|------|
| REJECT | コードの動作をそのまま自然言語で言い換えている |
| REJECT | 関数名・変数名から明らかなことを繰り返している |
| REJECT | JSDocが関数名の言い換えだけで情報を追加していない |
| OK | なぜその実装を選んだかの設計判断を説明している |
| OK | 一見不自然に見える挙動の理由を説明している |
| 最良 | コメントなしでコード自体が意図を語っている |

```typescript
// REJECT - コードの言い換え（What）
// If interrupted, abort immediately
if (status === 'interrupted') {
  return ABORT_STEP;
}

// REJECT - ループの存在を言い換えただけ
// Check transitions in order
for (const transition of step.transitions) {

// REJECT - 関数名の繰り返し
/** Check if status matches transition condition. */
export function matchesCondition(status: Status, condition: TransitionCondition): boolean {

// OK - 設計判断の理由（Why）
// ユーザー中断はワークフロー定義のトランジションより優先する
if (status === 'interrupted') {
  return ABORT_STEP;
}

// OK - 一見不自然な挙動の理由
// stay はループを引き起こす可能性があるが、ユーザーが明示的に指定した場合のみ使われる
return step.name;
```

**状態の直接変更の検出基準**

配列やオブジェクトの直接変更（ミューテーション）を検出する。

```typescript
// REJECT - 配列の直接変更
const steps: Step[] = getSteps();
steps.push(newStep);           // 元の配列を破壊
steps.splice(index, 1);       // 元の配列を破壊
steps[0].status = 'done';     // ネストされたオブジェクトも直接変更

// OK - イミュータブルな操作
const withNew = [...steps, newStep];
const without = steps.filter((_, i) => i !== index);
const updated = steps.map((s, i) =>
  i === 0 ? { ...s, status: 'done' } : s
);

// REJECT - オブジェクトの直接変更
function updateConfig(config: Config) {
  config.logLevel = 'debug';   // 引数を直接変更
  config.steps.push(newStep);  // ネストも直接変更
  return config;
}

// OK - 新しいオブジェクトを返す
function updateConfig(config: Config): Config {
  return {
    ...config,
    logLevel: 'debug',
    steps: [...config.steps, newStep],
  };
}
```

## セキュリティ（基本チェック）

- インジェクション対策（SQL, コマンド, XSS）
- ユーザー入力の検証
- 機密情報のハードコーディング

## テスタビリティ

- 依存性注入が可能な設計か
- モック可能か
- テストが書かれているか

## アンチパターン検出

以下のパターンを見つけたら REJECT:

| アンチパターン | 問題 |
|---------------|------|
| God Class/Component | 1つのクラスが多くの責務を持っている |
| Feature Envy | 他モジュールのデータを頻繁に参照している |
| Shotgun Surgery | 1つの変更が複数ファイルに波及する構造 |
| 過度な汎用化 | 今使わないバリアントや拡張ポイント |
| 隠れた依存 | 子コンポーネントが暗黙的にAPIを呼ぶ等 |
| 非イディオマティック | 言語・FWの作法を無視した独自実装 |

## 抽象化レベルの評価

**条件分岐の肥大化検出**

| パターン | 判定 |
|---------|------|
| 同じif-elseパターンが3箇所以上 | ポリモーフィズムで抽象化 → REJECT |
| switch/caseが5分岐以上 | Strategy/Mapパターンを検討 |
| フラグ引数で挙動を変える | 別関数に分割 → REJECT |
| 型による分岐（instanceof/typeof） | ポリモーフィズムに置換 → REJECT |
| ネストした条件分岐（3段以上） | 早期リターンまたは抽出 → REJECT |

**抽象度の不一致検出**

| パターン | 問題 | 修正案 |
|---------|------|--------|
| 高レベル処理の中に低レベル詳細 | 読みにくい | 詳細を関数に抽出 |
| 1関数内で抽象度が混在 | 認知負荷 | 同じ粒度に揃える |
| ビジネスロジックにDB操作が混在 | 責務違反 | Repository層に分離 |
| 設定値と処理ロジックが混在 | 変更困難 | 設定を外部化 |

**良い抽象化の例**

```typescript
// 条件分岐の肥大化
function process(type: string) {
  if (type === 'A') { /* 処理A */ }
  else if (type === 'B') { /* 処理B */ }
  else if (type === 'C') { /* 処理C */ }
  // ...続く
}

// Mapパターンで抽象化
const processors: Record<string, () => void> = {
  A: processA,
  B: processB,
  C: processC,
};
function process(type: string) {
  processors[type]?.();
}
```

```typescript
// 抽象度の混在
function createUser(data: UserData) {
  // 高レベル: ビジネスロジック
  validateUser(data);
  // 低レベル: DB操作の詳細
  const conn = await pool.getConnection();
  await conn.query('INSERT INTO users...');
  conn.release();
}

// 抽象度を揃える
function createUser(data: UserData) {
  validateUser(data);
  await userRepository.save(data);  // 詳細は隠蔽
}
```

## その場しのぎの検出

「とりあえず動かす」ための妥協を見逃さない。

| パターン | 例 |
|---------|-----|
| 不要なパッケージ追加 | 動かすためだけに入れた謎のライブラリ |
| テストの削除・スキップ | `@Disabled`、`.skip()`、コメントアウト |
| 空実装・スタブ放置 | `return null`、`// TODO: implement`、`pass` |
| モックデータの本番混入 | ハードコードされたダミーデータ |
| エラー握りつぶし | 空の `catch {}`、`rescue nil` |
| マジックナンバー | 説明なしの `if (status == 3)` |

## TODOコメントの厳格な禁止

「将来やる」は決してやらない。今やらないことは永遠にやらない。

TODOコメントは即REJECT。

```kotlin
// REJECT - 将来を見越したTODO
// TODO: 施設IDによる認可チェックを追加
fun deleteCustomHoliday(@PathVariable id: String) {
    deleteCustomHolidayInputPort.execute(input)
}

// APPROVE - 今実装する
fun deleteCustomHoliday(@PathVariable id: String) {
    val currentUserFacilityId = getCurrentUserFacilityId()
    val holiday = findHolidayById(id)
    require(holiday.facilityId == currentUserFacilityId) {
        "Cannot delete holiday from another facility"
    }
    deleteCustomHolidayInputPort.execute(input)
}
```

TODOが許容される唯一のケース:

| 条件 | 例 | 判定 |
|------|-----|------|
| 外部依存で今は実装不可 + Issue化済み | `// TODO(#123): APIキー取得後に実装` | 許容 |
| 技術的制約で回避不可 + Issue化済み | `// TODO(#456): ライブラリバグ修正待ち` | 許容 |
| 「将来実装」「後で追加」 | `// TODO: バリデーション追加` | REJECT |
| 「時間がないので」 | `// TODO: リファクタリング` | REJECT |

正しい対処:
- 今必要 → 今実装する
- 今不要 → コードを削除する
- 外部要因で不可 → Issue化してチケット番号をコメントに入れる

## DRY違反の検出

基本的に重複は排除する。本質的に同じロジックであり、まとめるべきと判断したら DRY にする。回数で機械的に判断しない。

| パターン | 判定 |
|---------|------|
| 本質的に同じロジックの重複 | REJECT - 関数/メソッドに抽出 |
| 同じバリデーションの重複 | REJECT - バリデーター関数に抽出 |
| 本質的に同じ構造のコンポーネント | REJECT - 共通コンポーネント化 |
| コピペで派生したコード | REJECT - パラメータ化または抽象化 |

DRY にしないケース:
- ドメインが異なる重複は抽象化しない（例: 顧客用バリデーションと管理者用バリデーションは別物）
- 表面的に似ているが、変更理由が異なるコードは別物として扱う

## 仕様準拠の検証

変更が、プロジェクトの文書化された仕様に準拠しているか検証する。

検証対象:

| 対象 | 確認内容 |
|------|---------|
| CLAUDE.md / README.md | スキーマ定義、設計原則、制約に従っているか |
| 型定義・Zodスキーマ | 新しいフィールドがスキーマに反映されているか |
| YAML/JSON設定ファイル | 文書化されたフォーマットに従っているか |

具体的なチェック:

1. 設定ファイル（YAML等）を変更・追加した場合:
   - CLAUDE.md等に記載されたスキーマ定義と突合する
   - 無視されるフィールドや無効なフィールドが含まれていないか
   - 必須フィールドが欠落していないか

2. 型定義やインターフェースを変更した場合:
   - ドキュメントのスキーマ説明が更新されているか
   - 既存の設定ファイルが新しいスキーマと整合するか

このパターンを見つけたら REJECT:

| パターン | 問題 |
|---------|------|
| 仕様に存在しないフィールドの使用 | 無視されるか予期しない動作 |
| 仕様上無効な値の設定 | 実行時エラーまたは無視される |
| 文書化された制約への違反 | 設計意図に反する |

## 呼び出しチェーン検証

新しいパラメータ・フィールドが追加された場合、変更ファイル内だけでなく呼び出し元も検証する。

検証手順:
1. 新しいオプショナルパラメータや interface フィールドを見つけたら、`Grep` で全呼び出し元を検索
2. 全呼び出し元が新しいパラメータを渡しているか確認
3. フォールバック値（`?? default`）がある場合、フォールバックが使われるケースが意図通りか確認

危険パターン:

| パターン | 問題 | 検出方法 |
|---------|------|---------|
| `options.xxx ?? fallback` で全呼び出し元が `xxx` を省略 | 機能が実装されているのに常にフォールバック | grep で呼び出し元を確認 |
| テストがモックで直接値をセット | 実際の呼び出しチェーンを経由しない | テストの構築方法を確認 |
| `executeXxx()` が内部で使う `options` を引数で受け取らない | 上位から値を渡す口がない | 関数シグネチャを確認 |

```typescript
// 配線漏れ: projectCwd を受け取る口がない
export async function executeWorkflow(config, cwd, task) {
  const engine = new WorkflowEngine(config, cwd, task);  // options なし
}

// 配線済み: projectCwd を渡せる
export async function executeWorkflow(config, cwd, task, options?) {
  const engine = new WorkflowEngine(config, cwd, task, options);
}
```

呼び出し元の制約による論理的デッドコード:

呼び出しチェーンの検証は「配線漏れ」だけでなく、逆方向——呼び出し元が既に保証している条件に対する不要な防御コード——にも適用する。

| パターン | 問題 | 検出方法 |
|---------|------|---------|
| 呼び出し元がTTY必須なのに関数内でTTYチェック | 到達しない分岐が残る | grep で全呼び出し元の前提条件を確認 |
| 呼び出し元がnullチェック済みなのに再度nullガード | 冗長な防御 | 呼び出し元の制約を追跡 |
| 呼び出し元が型で制約しているのにランタイムチェック | 型安全を信頼していない | TypeScriptの型制約を確認 |

検証手順:
1. 防御的な条件分岐（TTYチェック、nullガード等）を見つけたら、grep で全呼び出し元を確認
2. 全呼び出し元がその条件を既に保証しているなら、防御は不要 → REJECT
3. 一部の呼び出し元が保証していない場合は、防御を残す

## 品質特性

| 特性 | 確認観点 |
|------|---------|
| Scalability | 負荷増加に対応できる設計か |
| Maintainability | 変更・修正が容易か |
| Observability | ログ・監視が可能な設計か |

## 大局観

細かい「クリーンコード」の指摘に終始しない。

確認すべきこと:
- このコードは将来どう変化するか
- スケーリングの必要性は考慮されているか
- 技術的負債を生んでいないか
- ビジネス要件と整合しているか
- 命名がドメインと一貫しているか

## 変更スコープの評価

変更スコープを確認し、レポートに記載する（ブロッキングではない）。

| スコープサイズ | 変更行数 | 対応 |
|---------------|---------|------|
| Small | 〜200行 | そのままレビュー |
| Medium | 200-500行 | そのままレビュー |
| Large | 500行以上 | レビューは継続。分割可能か提案を付記 |

大きな変更が必要なタスクもある。行数だけでREJECTしない。

確認すること:
- 変更が論理的にまとまっているか（無関係な変更が混在していないか）
- Coderのスコープ宣言と実際の変更が一致しているか

提案として記載すること（ブロッキングではない）:
- 分割可能な場合は分割案を提示
