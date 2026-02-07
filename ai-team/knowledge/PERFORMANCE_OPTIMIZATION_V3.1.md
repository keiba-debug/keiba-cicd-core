# フロントエンド最適化計画（v3.1）

> **目的**: 画面描画パフォーマンスを50-70%改善し、快適なユーザー体験を提供

---

## 📌 現状分析

### パフォーマンス問題

現在のボトルネック：

1. **クライアントサイドレンダリング**
   - 大量の馬データ/調教データを一度に描画
   - React コンポーネントの再レンダリング過多
   - 仮想スクロール未実装

2. **データ取得の非効率**
   - 複数のJSONファイルを逐次読み込み
   - 不要なデータまで取得
   - キャッシング未実装

3. **データ変換処理**
   - クライアントサイドでの重い計算
   - 調教評価の再計算など

### 測定基準

**現状（v3.0）**:
- レース詳細ページ初回表示: 2-3秒
- 馬プロファイルページ初回表示: 3-5秒
- スクロール時のフレームレート: 30-40fps

**目標（v3.1）**:
- レース詳細ページ初回表示: < 1秒（60-70%改善）
- 馬プロファイルページ初回表示: < 2秒（50-60%改善）
- スクロール時のフレームレート: 60fps

---

## 🎯 最適化戦略

### 優先順位

| 施策 | 影響度 | 実装コスト | 優先度 |
|-----|-------|----------|--------|
| SWR/React Query導入 | 大 | 低 | ⭐⭐⭐ |
| React.memo/useMemo | 大 | 低 | ⭐⭐⭐ |
| react-window導入 | 中 | 中 | ⭐⭐ |
| Server Components | 中 | 高 | ⭐ |
| Code Splitting | 小 | 低 | ⭐ |

---

## 📋 実装計画

### 1. SWR導入（データキャッシング）⭐ 最優先

**目的**: APIレスポンスをキャッシュし、不要な再取得を防ぐ

**期待効果**: 30-40%のパフォーマンス改善

#### インストール

```bash
cd keiba-cicd-core/KeibaCICD.WebViewer
npm install swr
```

#### 実装例

**Before（v3.0）**:

```tsx
// src/app/races/[raceId]/page.tsx
export default async function RaceDetailPage({ params }: { params: { raceId: string } }) {
  // 毎回ファイルを読み込む
  const raceData = await fetch(`/api/races/${params.raceId}`).then(r => r.json());
  const trainingSummary = await fetch(`/api/training-summary/${params.raceId}`).then(r => r.json());

  return <RaceDetail data={raceData} training={trainingSummary} />;
}
```

**After（v3.1）**:

```tsx
// src/hooks/useRaceData.ts
import useSWR from 'swr';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export function useRaceData(raceId: string) {
  const { data, error, isLoading } = useSWR(
    `/api/races/${raceId}`,
    fetcher,
    {
      revalidateOnFocus: false,    // フォーカス時に再検証しない
      revalidateOnReconnect: false, // 再接続時に再検証しない
      dedupingInterval: 60000,      // 60秒間は同じリクエストを重複排除
      focusThrottleInterval: 5000   // 5秒以内のフォーカスは無視
    }
  );

  return {
    raceData: data,
    isLoading,
    error
  };
}

export function useTrainingSummary(raceId: string) {
  const { data, error, isLoading } = useSWR(
    `/api/training-summary/${raceId}`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000
    }
  );

  return {
    trainingSummary: data,
    isLoading,
    error
  };
}

// src/app/races/[raceId]/page.tsx
'use client';

export default function RaceDetailPage({ params }: { params: { raceId: string } }) {
  const { raceData, isLoading: raceLoading } = useRaceData(params.raceId);
  const { trainingSummary, isLoading: trainingLoading } = useTrainingSummary(params.raceId);

  if (raceLoading || trainingLoading) {
    return <LoadingSpinner />;
  }

  return <RaceDetail data={raceData} training={trainingSummary} />;
}
```

**メリット**:
- 同じデータを複数回取得しない
- ページ遷移後の戻るボタンでキャッシュから即座に表示
- メモリ内キャッシュで高速

---

### 2. React.memo/useMemo導入⭐ 最優先

**目的**: 不要な再レンダリングを防ぐ

**期待効果**: 20-30%のパフォーマンス改善

#### 実装例

**Before（v3.0）**:

```tsx
// src/components/race-v2/TrainingAnalysisSection.tsx
function TrainingAnalysisRow({ entry, trainingSummary }: Props) {
  // 親コンポーネントが再レンダリングされるたびに、
  // すべての行が再レンダリングされる
  return (
    <tr>
      <td>{entry.horse_name}</td>
      <td>{formatTrainingDetail(trainingSummary?.detail)}</td>
    </tr>
  );
}

export function TrainingAnalysisSection({ entries }: { entries: Entry[] }) {
  return (
    <table>
      {entries.map(entry => (
        <TrainingAnalysisRow key={entry.horse_number} entry={entry} />
      ))}
    </table>
  );
}
```

**After（v3.1）**:

```tsx
// src/components/race-v2/TrainingAnalysisSection.tsx
import { memo, useMemo } from 'react';

// React.memoで不要な再レンダリングを防ぐ
const TrainingAnalysisRow = memo(function TrainingAnalysisRow({ entry, trainingSummary }: Props) {
  // useMemoで重い計算をキャッシュ
  const formattedTraining = useMemo(() => {
    return formatTrainingDetail(
      trainingSummary?.detail,
      trainingSummary?.finalLap,
      trainingSummary?.weekendLap,
      trainingSummary?.weekAgoLap
    );
  }, [trainingSummary]);

  return (
    <tr>
      <td>{entry.horse_name}</td>
      <td>{formattedTraining}</td>
    </tr>
  );
});

export function TrainingAnalysisSection({ entries }: { entries: Entry[] }) {
  // ソート処理もuseMemoでキャッシュ
  const sortedEntries = useMemo(() => {
    return [...entries].sort((a, b) => a.horse_number - b.horse_number);
  }, [entries]);

  return (
    <table>
      {sortedEntries.map(entry => (
        <TrainingAnalysisRow
          key={entry.horse_number}
          entry={entry}
          trainingSummary={trainingSummaryMap[entry.horse_name]}
        />
      ))}
    </table>
  );
}
```

**適用箇所**:
- `TrainingAnalysisRow`（調教分析行）
- `RaceEntryRow`（出走表行）
- `HorseProfileCard`（馬プロファイルカード）
- `PedigreeTree`（血統表）

**メリット**:
- 変更がない行は再レンダリングされない
- スクロール時のフレームレート向上
- CPU使用率削減

---

### 3. react-window導入（仮想スクロール）

**目的**: 長いリストの描画を最適化

**期待効果**: 10-20%のパフォーマンス改善（馬プロファイルページ等）

#### インストール

```bash
npm install react-window
npm install --save-dev @types/react-window
```

#### 実装例

**Before（v3.0）**:

```tsx
// 馬プロファイルページの過去レース一覧（100件以上）
export function PastRacesList({ races }: { races: Race[] }) {
  return (
    <div className="space-y-2">
      {races.map(race => (
        <PastRaceCard key={race.race_id} race={race} />
      ))}
    </div>
  );
}
```

**After（v3.1）**:

```tsx
import { FixedSizeList } from 'react-window';

export function PastRacesList({ races }: { races: Race[] }) {
  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => (
    <div style={style}>
      <PastRaceCard race={races[index]} />
    </div>
  );

  return (
    <FixedSizeList
      height={600}          // 表示領域の高さ
      itemCount={races.length}
      itemSize={120}        // 各アイテムの高さ
      width="100%"
    >
      {Row}
    </FixedSizeList>
  );
}
```

**適用箇所**:
- 馬プロファイルページの過去レース一覧
- レース一覧ページ（週末レース一覧）
- 調教履歴一覧

**メリット**:
- 表示されている行のみレンダリング
- スクロールがスムーズ（60fps）
- メモリ使用量削減

---

### 4. Server Components導入（検討）

**目的**: サーバーサイドでのレンダリングで初回表示を高速化

**期待効果**: 10-20%のパフォーマンス改善

#### Next.js 14 App Router活用

**src/app/races/[raceId]/page.tsx**:

```tsx
// Server Component（デフォルト）
export default async function RaceDetailPage({ params }: { params: { raceId: string } }) {
  // サーバーサイドでデータ取得
  const raceData = await getRaceData(params.raceId);
  const trainingSummary = await getTrainingSummary(params.raceId);

  return (
    <div>
      {/* 静的な部分はサーバーでレンダリング */}
      <RaceHeader data={raceData} />

      {/* インタラクティブな部分のみClient Component */}
      <TrainingAnalysisSection entries={raceData.entries} training={trainingSummary} />
    </div>
  );
}

// src/components/race-v2/TrainingAnalysisSection.tsx
'use client';  // Client Componentとして明示

export function TrainingAnalysisSection({ entries, training }: Props) {
  // クライアントサイドのインタラクションが必要な部分
  const [expanded, setExpanded] = useState(false);
  // ...
}
```

**メリット**:
- 初回表示が高速（HTMLがサーバーから送られる）
- SEO改善
- JavaScript bundle サイズ削減

**注意点**:
- Client ComponentとServer Componentの境界を適切に設計
- useState/useEffect等はClient Componentのみで使用可能

---

### 5. Code Splitting（コード分割）

**目的**: 初回ロード時のJavaScript bundle サイズ削減

**期待効果**: 5-10%のパフォーマンス改善

#### Dynamic Import

```tsx
import dynamic from 'next/dynamic';

// 血統表は初回表示時に不要なので遅延ロード
const PedigreeTree = dynamic(() => import('@/components/horse/PedigreeTree'), {
  loading: () => <div>血統表読み込み中...</div>,
  ssr: false  // クライアントサイドのみでレンダリング
});

// チャートも遅延ロード
const PerformanceChart = dynamic(() => import('@/components/charts/PerformanceChart'), {
  loading: () => <LoadingSpinner />,
  ssr: false
});

export default function HorseProfilePage({ horseId }: { horseId: string }) {
  const [showPedigree, setShowPedigree] = useState(false);

  return (
    <div>
      <HorseBasicInfo horseId={horseId} />

      <button onClick={() => setShowPedigree(true)}>血統表を表示</button>

      {showPedigree && <PedigreeTree horseId={horseId} />}

      <PerformanceChart horseId={horseId} />
    </div>
  );
}
```

**適用箇所**:
- 血統表コンポーネント
- チャートコンポーネント
- モーダルダイアログ

---

## 📊 測定と検証

### パフォーマンス測定ツール

#### 1. Next.js Built-in Metrics

```tsx
// src/app/layout.tsx
import { Analytics } from '@vercel/analytics/react';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

#### 2. React DevTools Profiler

```tsx
import { Profiler } from 'react';

function onRenderCallback(
  id: string,
  phase: "mount" | "update",
  actualDuration: number,
  baseDuration: number,
  startTime: number,
  commitTime: number
) {
  console.log(`${id} (${phase}): ${actualDuration}ms`);
}

export function TrainingAnalysisSection(props: Props) {
  return (
    <Profiler id="TrainingAnalysisSection" onRender={onRenderCallback}>
      {/* ... */}
    </Profiler>
  );
}
```

#### 3. Lighthouse CI

```bash
# package.json
{
  "scripts": {
    "lighthouse": "lighthouse http://localhost:3000/races/2026020806010208 --view"
  }
}
```

**測定指標**:
- FCP (First Contentful Paint)
- LCP (Largest Contentful Paint)
- TTI (Time to Interactive)
- TBT (Total Blocking Time)
- CLS (Cumulative Layout Shift)

---

## 🔄 実装手順

### Week 1: SWR導入

1. SWRインストール
2. カスタムフック作成（`useRaceData`, `useTrainingSummary`）
3. レース詳細ページに適用
4. 馬プロファイルページに適用

**成果物**:
- `src/hooks/useRaceData.ts`
- `src/hooks/useTrainingSummary.ts`

### Week 2: React.memo/useMemo導入

1. `TrainingAnalysisRow`にReact.memo適用
2. `formatTrainingDetail`にuseMemo適用
3. その他のコンポーネントに順次適用
4. React DevTools Profilerで検証

**成果物**:
- 最適化されたコンポーネント（10-15ファイル）

### Week 3: react-window導入

1. react-windowインストール
2. 馬プロファイルページの過去レース一覧に適用
3. レース一覧ページに適用
4. スクロールパフォーマンス測定

**成果物**:
- 仮想スクロール対応コンポーネント（3-5ファイル）

### Week 4: Server Components検討

1. Server Component / Client Component の境界設計
2. レース詳細ページをServer Componentに変換
3. パフォーマンス測定
4. 効果が薄ければ保留

**成果物**:
- Server Component化したページ（1-2ファイル）

---

## ✅ 検証基準

### 成功基準

| 指標 | 現状（v3.0） | 目標（v3.1） | 測定方法 |
|-----|------------|------------|---------|
| レース詳細ページ初回表示 | 2-3秒 | < 1秒 | Lighthouse |
| 馬プロファイルページ初回表示 | 3-5秒 | < 2秒 | Lighthouse |
| スクロール時FPS | 30-40fps | 60fps | Chrome DevTools |
| LCP | 3-4秒 | < 2秒 | Lighthouse |
| TTI | 4-5秒 | < 2.5秒 | Lighthouse |
| Bundle Size | 未測定 | -20% | next build |

### 検証手順

1. **Before測定**（v3.0）:
   ```bash
   npm run build
   npm run start
   lighthouse http://localhost:3000/races/2026020806010208 --view
   ```

2. **各施策適用後に測定**:
   - SWR導入後
   - React.memo導入後
   - react-window導入後

3. **After測定**（v3.1完成時）:
   - 全施策適用後の最終測定
   - Before/After比較レポート作成

---

## 📝 注意事項

### パフォーマンス最適化の落とし穴

1. **過度な最適化**
   - React.memoをすべてのコンポーネントに適用しない
   - 小さなコンポーネントはメモ化のオーバーヘッドが逆効果

2. **測定なしの最適化**
   - 必ずBefore/After測定を行う
   - React DevTools Profilerで効果を確認

3. **キャッシュの罠**
   - SWRのキャッシュが古いデータを表示する可能性
   - レース結果更新時は`mutate()`で再取得

### トラブルシューティング

**SWRでデータが更新されない**:
```tsx
import { useSWRConfig } from 'swr';

function RefreshButton({ raceId }: { raceId: string }) {
  const { mutate } = useSWRConfig();

  const handleRefresh = () => {
    mutate(`/api/races/${raceId}`);
  };

  return <button onClick={handleRefresh}>更新</button>;
}
```

**React.memoで再レンダリングが防げない**:
```tsx
// ❌ ダメな例（オブジェクトを毎回新規作成）
<TrainingAnalysisRow entry={{ ...entry }} />

// ✅ 良い例（同じオブジェクトを渡す）
<TrainingAnalysisRow entry={entry} />
```

---

## 🚀 期待される効果

### 定量的効果

- **レース詳細ページ**: 2-3秒 → < 1秒（60-70%改善）
- **馬プロファイルページ**: 3-5秒 → < 2秒（50-60%改善）
- **スクロール時FPS**: 30-40fps → 60fps（50%改善）

### 定性的効果

- **ユーザー体験の向上**: ページ遷移が快適に
- **データ分析の効率化**: 素早く情報にアクセス可能
- **モバイル対応の改善**: 低スペック端末でも快適

---

**最終更新**: 2026-02-07（カカシ）
**承認**: ふくだ君（保留中）
