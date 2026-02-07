# フロントエンド最適化 v3.1 - 完了レポート

> **ステータス**: 完了（2026-02-07）
> **目的**: 画面描画パフォーマンスを改善し、快適なユーザー体験を提供

---

## 実施結果サマリ

| 施策 | 状況 | 適用規模 | 備考 |
|-----|------|---------|------|
| SWR導入 | ✅ 完了 | `swr@2.4.0` / 1フック | Server Componentsが主流のため最小限で十分 |
| React.memo | ✅ 完了 | 5コンポーネント / 23箇所 | データ量の多いテーブル行に適用 |
| useMemo | ✅ 完了 | 13ファイル / 56箇所 | 重い計算処理を広くカバー |
| useCallback | ✅ 完了 | 18ファイル / 50箇所 | イベントハンドラ全般 |
| Server Components | ✅ 完了 | ページ層で適切に分離 | Next.js App Router活用 |
| Code Splitting | ✅ 完了 | 2ファイル（next/dynamic） | TrainingInfoSection, TrainingAnalysisSection |
| loading.tsx | ✅ 完了 | 3ルート | SkeletonコンポーネントによるストリーミングUI |
| react-window | ⏭️ 見送り | インストール済み・適用なし | 下記「判断理由」参照 |

---

## 各施策の詳細

### 1. SWR（データキャッシング）

- **パッケージ**: `swr@2.4.0`
- **実装**: `src/hooks/useBankrollAlerts.ts`
- **設計判断**: メインページ（レース詳細・馬プロファイル）はServer Componentで直接データ取得しているため、SWRはクライアントサイドのミューテーションが必要な箇所（bankroll等）のみに限定。Server Components + loading.tsx の組み合わせの方がNext.jsアーキテクチャに適合。

### 2. React.memo / useMemo / useCallback

**React.memo 適用コンポーネント**:
- `TrainingAnalysisSection.tsx`（調教分析行）
- `TrainingInfoSection.tsx`（調教情報行）
- `StakeholderCommentsSection.tsx`（関係者コメント行）
- `HorsePastRacesTable.tsx`（過去レース行）
- `HorseEntryTable.tsx`（出走表行）

**useMemo 主要適用箇所**:
- `race-detail-content.tsx` - レースデータの変換処理
- `HorseEntryTable.tsx` - ソート・フィルタ処理
- `TrainingInfoSection.tsx` - 調教評価計算
- `odds-board/page.tsx` - オッズ計算

### 3. Server Components

**Server Component**（データ取得をサーバーで実行）:
- `app/page.tsx` - トップページ（レース一覧）
- `app/races-v2/[date]/[track]/[id]/page.tsx` - レース詳細

**Client Component**（インタラクティブ機能が必要）:
- `admin/page.tsx` - 管理画面
- `bankroll/page.tsx` - 資金管理
- `odds-board/page.tsx` - オッズボード
- `multi-view/page.tsx` - マルチビュー

### 4. Code Splitting（next/dynamic）

- `race-detail-content.tsx`: `TrainingInfoSection` と `TrainingAnalysisSection` を遅延ロード
- `multi-view/page.tsx`: マルチビューコンポーネントの動的インポート

### 5. loading.tsx（ストリーミングUI）

- `app/loading.tsx` - トップページ（日付タブ + 3場カードスケルトン）
- `app/races-v2/[date]/[track]/[id]/loading.tsx` - レース詳細（ヘッダー + 出走表スケルトン）
- `app/horses-v2/[id]/loading.tsx` - 馬プロファイル（統計 + 過去レーススケルトン）
- **Skeletonコンポーネント**: `components/ui/skeleton.tsx`（shadcn/ui標準）

### 6. react-window（見送り判断）

**インストール済み**: `react-window` は dependency に追加済み。将来必要になった場合すぐ使える。

**適用を見送った理由**:
- `HorsePastRacesTable` は行の高さが可変（展開/折りたたみ、サマリー行の有無）
- `FixedSizeList` は不適合、`VariableSizeList` は複雑すぎる
- 既存のIntersectionObserver + React.memo + useMemoによる段階的レンダリング（10件ずつ）で十分なパフォーマンス

---

## アーキテクチャ上の決定

### Server Components vs SWR

当初計画ではSWRをメインのデータ取得戦略としていたが、実装を進める中でServer Componentsの方がNext.js App Routerアーキテクチャに適合することが判明。

**採用した戦略**:
```
Server Component (page.tsx)
  → サーバーでデータ取得（fs直接読み込み）
  → loading.tsx でストリーミングUI
  → Client Component は最小限（インタラクション必要箇所のみ）
```

**SWRを使わなかった理由**:
1. Server Componentで直接ファイル読み込みの方が高速（APIリクエスト不要）
2. loading.tsx が初回表示の体感速度を改善
3. SWRはClient Component前提のため、Server Componentとの併用でアーキテクチャが複雑化

### IntersectionObserver vs react-window

`HorsePastRacesTable` で採用した段階的レンダリング:
```
初回: 10件のみレンダリング
→ IntersectionObserver がスクロール検知
→ 10件ずつ追加レンダリング
→ React.memo で既存行の再レンダリングを防止
```

react-windowの`FixedSizeList`は固定高さの行にのみ適合するため、展開可能な行を持つテーブルには不適切と判断。

---

## 今後の改善機会

v3.1は完了とするが、将来的に効果が見込まれる施策:

1. **react-windowの適用**: 固定高さのリスト（馬検索結果一覧等）が増えた場合
2. **Bundle分析**: `@next/bundle-analyzer` で不要なライブラリの特定
3. **Image最適化**: `next/image` の活用（馬画像等が追加された場合）

---

**完了日**: 2026-02-07
**実施者**: カカシ（Claude Code）
**承認**: ふくだ君
