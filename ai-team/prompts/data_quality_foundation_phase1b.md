# データ品質基盤 Phase 1b - UI実装 開発指示書

**作成日**: 2026-02-01
**対象**: Phase 1b（UI実装）
**実装期間**: 1週間（Day 1-5）
**前提**: Phase 1aのAPI完成、React、TypeScript、shadcn/ui

---

## 📋 概要

管理画面（`/admin`）に**データ品質ダッシュボード**を追加します。

### 追加する機能

1. **📊 データ品質セクション**
   - DataStatusCard - データ状況表示
   - ValidationResultsCard - 検証結果表示

2. **💚 システム状態セクション**
   - SystemHealthCard - ヘルスチェック表示（30秒自動更新）

3. **リアルタイム更新**
   - バッチ実行完了後に自動でデータ品質を再取得

---

## 🗂️ 作成するファイル

```
keiba-cicd-core/KeibaCICD.WebViewer/src/
├── components/admin/
│   ├── data-quality/
│   │   ├── index.ts                    # NEW - エクスポート
│   │   ├── DataStatusCard.tsx          # NEW - データ状況カード
│   │   ├── ValidationResultsCard.tsx   # NEW - 検証結果カード
│   │   └── SystemHealthCard.tsx        # NEW - システムヘルスカード
│   └── index.ts                        # UPDATE - エクスポート追加
└── app/admin/
    └── page.tsx                        # UPDATE - セクション追加
```

---

## 📦 Phase 1b-1: データ状況カード

**ファイル**: `src/components/admin/data-quality/DataStatusCard.tsx`

**実装内容**:

```typescript
'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Skeleton } from '@/components/ui/skeleton';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { DataStatusResponse } from '@/types/data-quality';

interface DataStatusCardProps {
  selectedDate: string;
  refreshKey?: number; // 外部からの強制リフレッシュ用
}

export function DataStatusCard({ selectedDate, refreshKey }: DataStatusCardProps) {
  const [status, setStatus] = useState<DataStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  useEffect(() => {
    fetchStatus();
  }, [selectedDate, refreshKey]);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/data/status?date=${selectedDate}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setStatus(data);
    } catch (err) {
      console.error('[DataStatusCard] Error:', err);
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-950 rounded text-sm text-red-700 dark:text-red-300">
        ⚠️ データ状況の取得に失敗しました: {error}
      </div>
    );
  }

  if (!status) return null;

  const coverageColor =
    status.summary.coveragePercent >= 80 ? 'default' :
    status.summary.coveragePercent >= 50 ? 'secondary' :
    'destructive';

  return (
    <div className="space-y-3">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <h3 className="font-medium">データ状況</h3>
        <Badge variant={coverageColor}>
          カバレッジ: {status.summary.coveragePercent}%
        </Badge>
      </div>

      {/* サマリー統計 */}
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div className="p-2 bg-muted/30 rounded">
          <div className="text-muted-foreground text-xs">総日数</div>
          <div className="font-bold">{status.summary.totalDates}</div>
        </div>
        <div className="p-2 bg-green-500/10 rounded">
          <div className="text-muted-foreground text-xs">データあり</div>
          <div className="font-bold text-green-600 dark:text-green-400">
            {status.summary.datesWithData}
          </div>
        </div>
        <div className="p-2 bg-yellow-500/10 rounded">
          <div className="text-muted-foreground text-xs">データなし</div>
          <div className="font-bold text-yellow-600 dark:text-yellow-400">
            {status.summary.datesWithoutData}
          </div>
        </div>
      </div>

      {/* 詳細（折りたたみ） */}
      {status.dates.length > 0 && (
        <Collapsible open={isDetailsOpen} onOpenChange={setIsDetailsOpen}>
          <CollapsibleTrigger className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline">
            詳細を表示 ({status.dates.length}件)
            {isDetailsOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 space-y-2 max-h-60 overflow-y-auto">
              {status.dates.map((date) => (
                <div
                  key={date.date}
                  className="p-2 bg-muted/20 rounded text-sm"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{date.displayDate}</span>
                    <Badge variant={date.hasData ? 'default' : 'secondary'} className="text-xs">
                      {date.hasData ? '✓' : '×'}
                    </Badge>
                  </div>
                  {date.hasData && date.tracks.length > 0 && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {date.tracks.map((t) => `${t.track}(${t.raceCount}R)`).join(', ')}
                    </div>
                  )}
                  {date.hasData && date.tracks.length === 0 && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      未開催レース（race_info.jsonのみ）
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* ディスク使用量 */}
      <div className="pt-2 border-t text-xs text-muted-foreground">
        ディスク使用量: {status.diskUsage.totalSizeMB.toFixed(1)} MB
        ({status.diskUsage.fileCount.toLocaleString()} ファイル)
      </div>
    </div>
  );
}
```

**配置先**: `keiba-cicd-core/KeibaCICD.WebViewer/src/components/admin/data-quality/DataStatusCard.tsx`

---

## 🔍 Phase 1b-2: 検証結果カード

**ファイル**: `src/components/admin/data-quality/ValidationResultsCard.tsx`

**実装内容**:

```typescript
'use client';

import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { ValidationResponse } from '@/types/data-quality';

interface ValidationResultsCardProps {
  selectedDate: string;
  refreshKey?: number;
}

export function ValidationResultsCard({ selectedDate, refreshKey }: ValidationResultsCardProps) {
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deepMode, setDeepMode] = useState(false);

  useEffect(() => {
    fetchValidation();
  }, [selectedDate, deepMode, refreshKey]);

  const fetchValidation = async () => {
    setLoading(true);
    setError(null);

    try {
      const url = `/api/data/validation?date=${selectedDate}${deepMode ? '&deep=true' : ''}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setValidation(data);
    } catch (err) {
      console.error('[ValidationResultsCard] Error:', err);
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-950 rounded text-sm text-red-700 dark:text-red-300">
        ⚠️ 検証結果の取得に失敗しました: {error}
      </div>
    );
  }

  if (!validation) return null;

  const statusVariant =
    validation.validation.overallStatus === 'healthy' ? 'default' :
    validation.validation.overallStatus === 'warning' ? 'secondary' :
    'destructive';

  const statusIcon =
    validation.validation.overallStatus === 'healthy' ? '✅' :
    validation.validation.overallStatus === 'warning' ? '⚠️' :
    '❌';

  const statusText =
    validation.validation.overallStatus === 'healthy' ? '正常' :
    validation.validation.overallStatus === 'warning' ? '警告あり' :
    'エラーあり';

  return (
    <div className="space-y-3">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <h3 className="font-medium">検証結果</h3>
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant}>
            {statusIcon} {statusText}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDeepMode(!deepMode)}
          >
            {deepMode ? '簡易モード' : '詳細検証'}
          </Button>
        </div>
      </div>

      {/* 問題サマリー */}
      {validation.validation.totalIssues > 0 && (
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="p-2 bg-red-500/10 rounded">
            <div className="text-muted-foreground text-xs">重大な問題</div>
            <div className="font-bold text-red-600 dark:text-red-400">
              {validation.validation.criticalIssues}
            </div>
          </div>
          <div className="p-2 bg-yellow-500/10 rounded">
            <div className="text-muted-foreground text-xs">警告</div>
            <div className="font-bold text-yellow-600 dark:text-yellow-400">
              {validation.validation.warnings}
            </div>
          </div>
        </div>
      )}

      {/* 問題リスト */}
      {validation.dates.some((d) => d.issues.length > 0) && (
        <div className="space-y-2 max-h-60 overflow-y-auto">
          {validation.dates.map((date) =>
            date.issues.length > 0 ? (
              <div key={date.date} className="p-2 border rounded">
                <div className="font-medium text-sm mb-1">{date.date}</div>
                {date.issues.map((issue, idx) => (
                  <div
                    key={idx}
                    className={`text-xs py-1 flex items-start gap-1 ${
                      issue.level === 'critical'
                        ? 'text-red-600 dark:text-red-400'
                        : issue.level === 'warning'
                        ? 'text-yellow-600 dark:text-yellow-400'
                        : 'text-blue-600 dark:text-blue-400'
                    }`}
                  >
                    <span className="flex-shrink-0">
                      {issue.level === 'critical' && '🔴'}
                      {issue.level === 'warning' && '🟡'}
                      {issue.level === 'info' && '🔵'}
                    </span>
                    <span>{issue.message}</span>
                  </div>
                ))}
              </div>
            ) : null
          )}
        </div>
      )}

      {/* 問題なし */}
      {validation.validation.totalIssues === 0 && (
        <div className="p-4 bg-green-50 dark:bg-green-950 rounded text-sm text-green-700 dark:text-green-300 text-center">
          ✅ すべてのチェックに合格しました
        </div>
      )}
    </div>
  );
}
```

**配置先**: `keiba-cicd-core/KeibaCICD.WebViewer/src/components/admin/data-quality/ValidationResultsCard.tsx`

---

## 💚 Phase 1b-3: システムヘルスカード

**ファイル**: `src/components/admin/data-quality/SystemHealthCard.tsx`

**実装内容**:

```typescript
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { RefreshCw } from 'lucide-react';
import type { HealthResponse } from '@/types/data-quality';

export function SystemHealthCard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchHealth = useCallback(async () => {
    setError(null);

    try {
      const response = await fetch('/api/health');

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setHealth(data);
    } catch (err) {
      console.error('[SystemHealthCard] Error:', err);
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();

    if (autoRefresh) {
      const interval = setInterval(fetchHealth, 30000); // 30秒ごと
      return () => clearInterval(interval);
    }
  }, [autoRefresh, fetchHealth]);

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-950 rounded text-sm text-red-700 dark:text-red-300">
        ⚠️ ヘルスチェックに失敗しました: {error}
      </div>
    );
  }

  if (!health) return null;

  const statusIcon = {
    healthy: '✅',
    degraded: '⚠️',
    unhealthy: '❌',
  }[health.status];

  const StatusBadge = ({ status }: { status: string }) => {
    const variant = status === 'ok' ? 'default' : 'destructive';
    const text = status === 'ok' ? '✓' : '×';
    return <span className="text-xs">{text}</span>;
  };

  return (
    <div className="space-y-4">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{statusIcon}</span>
          <div>
            <h3 className="font-medium">システム状態</h3>
            <p className="text-xs text-muted-foreground">
              最終更新: {new Date(health.timestamp).toLocaleTimeString('ja-JP')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchHealth}>
            <RefreshCw className="w-4 h-4" />
          </Button>
          <div className="flex items-center gap-2">
            <Switch
              id="auto-refresh"
              checked={autoRefresh}
              onCheckedChange={setAutoRefresh}
            />
            <Label htmlFor="auto-refresh" className="text-xs cursor-pointer">
              自動更新
            </Label>
          </div>
        </div>
      </div>

      {/* ヘルスチェックグリッド */}
      <div className="grid grid-cols-2 gap-3">
        {/* ディレクトリ */}
        <Card className="p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">📁 ディレクトリ</span>
            <StatusBadge status={health.checks.directories.status} />
          </div>
          <div className="text-xs space-y-1">
            <div className="flex justify-between">
              <span>競馬データ</span>
              <span>{health.checks.directories.details.keibaDataRoot.exists ? '✓' : '×'}</span>
            </div>
            <div className="flex justify-between">
              <span>JRA-VAN</span>
              <span>{health.checks.directories.details.jvDataRoot.exists ? '✓' : '×'}</span>
            </div>
            <div className="flex justify-between">
              <span>レースデータ</span>
              <span>{health.checks.directories.details.racesDir.dateCount}日分</span>
            </div>
          </div>
        </Card>

        {/* ディスク容量 */}
        <Card className="p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">💾 ディスク容量</span>
            <StatusBadge status={health.checks.diskSpace.status} />
          </div>
          <div className="text-xs space-y-1">
            <div className="flex justify-between">
              <span>レースデータ</span>
              <span>{health.checks.diskSpace.details.racesDataSizeMB.toFixed(0)} MB</span>
            </div>
            <div className="flex justify-between">
              <span>キャッシュ</span>
              <span>{health.checks.diskSpace.details.cacheSizeMB.toFixed(0)} MB</span>
            </div>
            <div className="flex justify-between font-medium">
              <span>合計</span>
              <span>{health.checks.diskSpace.details.totalSizeMB.toFixed(0)} MB</span>
            </div>
          </div>
        </Card>

        {/* インデックス */}
        <Card className="p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">📇 インデックス</span>
            <StatusBadge status={health.checks.indexHealth.status} />
          </div>
          <div className="text-xs space-y-1">
            <div className="flex justify-between">
              <span>日付数</span>
              <span>{health.checks.indexHealth.details.dateCount}</span>
            </div>
            <div className="flex justify-between">
              <span>レース数</span>
              <span>{health.checks.indexHealth.details.raceCount}</span>
            </div>
            <div className="flex justify-between">
              <span>更新</span>
              <span>{health.checks.indexHealth.details.ageHours}時間前</span>
            </div>
          </div>
        </Card>

        {/* メモリ */}
        <Card className="p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">🧠 メモリ</span>
            <StatusBadge status={health.checks.memory.status} />
          </div>
          <div className="text-xs space-y-1">
            <div className="flex justify-between">
              <span>使用中</span>
              <span>{health.checks.memory.details.usedMB} MB</span>
            </div>
            <div className="flex justify-between">
              <span>ヒープ使用</span>
              <span>{health.checks.memory.details.heapUsedMB} MB</span>
            </div>
            <div className="flex justify-between">
              <span>ヒープ合計</span>
              <span>{health.checks.memory.details.heapTotalMB} MB</span>
            </div>
          </div>
        </Card>
      </div>

      {/* 警告・エラー */}
      {(health.warnings.length > 0 || health.errors.length > 0) && (
        <div className="space-y-2">
          {health.errors.length > 0 && (
            <div className="p-2 bg-red-50 dark:bg-red-950 rounded">
              <div className="text-sm font-medium text-red-700 dark:text-red-300 mb-1">
                エラー
              </div>
              <ul className="text-xs text-red-600 dark:text-red-400 space-y-1">
                {health.errors.map((error, idx) => (
                  <li key={idx}>• {error}</li>
                ))}
              </ul>
            </div>
          )}
          {health.warnings.length > 0 && (
            <div className="p-2 bg-yellow-50 dark:bg-yellow-950 rounded">
              <div className="text-sm font-medium text-yellow-700 dark:text-yellow-300 mb-1">
                警告
              </div>
              <ul className="text-xs text-yellow-600 dark:text-yellow-400 space-y-1">
                {health.warnings.map((warning, idx) => (
                  <li key={idx}>• {warning}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

**配置先**: `keiba-cicd-core/KeibaCICD.WebViewer/src/components/admin/data-quality/SystemHealthCard.tsx`

---

## 📤 Phase 1b-4: エクスポート設定

**ファイル1**: `src/components/admin/data-quality/index.ts`

```typescript
export { DataStatusCard } from './DataStatusCard';
export { ValidationResultsCard } from './ValidationResultsCard';
export { SystemHealthCard } from './SystemHealthCard';
```

**ファイル2**: `src/components/admin/index.ts` に追加

```typescript
// 既存のエクスポート
export { ActionButton } from './ActionButton';
export { DateSelector } from './DateSelector';
export { DateRangeSelector } from './DateRangeSelector';
export { LogViewer } from './LogViewer';
export { StatusBadge } from './StatusBadge';
export { RpciStandardsViewer } from './RpciStandardsViewer';

// NEW: データ品質コンポーネント
export {
  DataStatusCard,
  ValidationResultsCard,
  SystemHealthCard,
} from './data-quality';

// 型定義（既存）
export type { LogEntry, ExecutionStatus } from './LogViewer';
```

---

## 🔧 Phase 1b-5: 管理画面への統合

**ファイル**: `src/app/admin/page.tsx`

**修正箇所**: 「システム管理」セクションの**前**に2つの新しいセクションを追加

### ステップ1: import文を追加

```typescript
// ファイル冒頭のimport文に追加
import {
  ActionButton,
  DateSelector,
  DateRangeSelector,
  LogViewer,
  StatusBadge,
  DataStatusCard,           // NEW
  ValidationResultsCard,    // NEW
  SystemHealthCard,         // NEW
  type LogEntry,
  type ExecutionStatus,
} from '@/components/admin';
```

### ステップ2: state追加

```typescript
// page.tsx の state セクションに追加（約60行目付近）

// データ品質リフレッシュ用
const [dataQualityRefreshKey, setDataQualityRefreshKey] = useState(0);

// セクション開閉状態
const [isDataQualityOpen, setIsDataQualityOpen] = useState(false);
const [isSystemHealthOpen, setIsSystemHealthOpen] = useState(false);
```

### ステップ3: リフレッシュ関数追加

```typescript
// 約100行目付近、rebuildIndex の下に追加

const refreshDataQuality = useCallback(() => {
  setDataQualityRefreshKey((prev) => prev + 1);
}, []);
```

### ステップ4: SSEイベントハンドラーを修正

`handleSSEEvent` 関数の `case 'complete':` セクションに追加（約200行目付近）:

```typescript
case 'complete':
  addLog({ /* ... */ });
  setStatus('success');
  setCurrentAction(null);

  // NEW: バッチ実行完了後にデータ品質を更新
  if (['batch_prepare', 'batch_after_race', 'integrate'].includes(currentActionId)) {
    refreshDataQuality();
  }
  break;
```

### ステップ5: JSX に2つのセクションを追加

「📆 日付設定」セクションと「システム管理」セクションの**間**に挿入:

```tsx
{/* データ品質セクション - NEW */}
<Collapsible open={isDataQualityOpen} onOpenChange={setIsDataQualityOpen}>
  <Card className="border-muted">
    <CollapsibleTrigger asChild>
      <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
        <CardTitle className="text-lg flex items-center justify-between">
          <span className="flex items-center gap-2">
            📊 データ品質
            <span className="text-xs font-normal text-muted-foreground">
              （データ状態確認）
            </span>
          </span>
          {isDataQualityOpen ? (
            <ChevronUp className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          )}
        </CardTitle>
      </CardHeader>
    </CollapsibleTrigger>
    <CollapsibleContent>
      <CardContent>
        <div className="space-y-4">
          <DataStatusCard
            selectedDate={selectedDate}
            refreshKey={dataQualityRefreshKey}
          />
          <Separator />
          <ValidationResultsCard
            selectedDate={selectedDate}
            refreshKey={dataQualityRefreshKey}
          />
        </div>
      </CardContent>
    </CollapsibleContent>
  </Card>
</Collapsible>

{/* システム状態セクション - NEW */}
<Collapsible open={isSystemHealthOpen} onOpenChange={setIsSystemHealthOpen}>
  <Card className="border-muted">
    <CollapsibleTrigger asChild>
      <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
        <CardTitle className="text-lg flex items-center justify-between">
          <span className="flex items-center gap-2">
            💚 システム状態
            <span className="text-xs font-normal text-muted-foreground">
              （ヘルスチェック）
            </span>
          </span>
          {isSystemHealthOpen ? (
            <ChevronUp className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          )}
        </CardTitle>
      </CardHeader>
    </CollapsibleTrigger>
    <CollapsibleContent>
      <CardContent>
        <SystemHealthCard />
      </CardContent>
    </CollapsibleContent>
  </Card>
</Collapsible>
```

---

## ✅ テスト手順

### 1. ビルドエラーチェック

```bash
cd keiba-cicd-core/KeibaCICD.WebViewer
npm run build
```

TypeScriptエラーがないことを確認。

### 2. 開発サーバー起動

```bash
npm run dev
```

### 3. 管理画面を開く

```
http://localhost:3000/admin
```

### 4. UI動作確認

**データ品質セクション**:
- [ ] セクションが表示される
- [ ] クリックで開閉できる
- [ ] DataStatusCard が表示される
  - [ ] カバレッジ%が表示される
  - [ ] 統計（総日数、データあり、データなし）が表示される
  - [ ] 詳細を展開できる
  - [ ] ディスク使用量が表示される
- [ ] ValidationResultsCard が表示される
  - [ ] 検証ステータスが表示される
  - [ ] 簡易モード/詳細検証の切り替えができる
  - [ ] 問題リストが表示される
- [ ] 日付を変更すると両カードが更新される

**システム状態セクション**:
- [ ] セクションが表示される
- [ ] SystemHealthCard が表示される
  - [ ] ステータスアイコンが表示される
  - [ ] 4つのグリッド（ディレクトリ、ディスク、インデックス、メモリ）が表示される
  - [ ] 最終更新時刻が表示される
  - [ ] 手動更新ボタンが動作する
  - [ ] 自動更新トグルが動作する（30秒ごと）
  - [ ] 警告・エラーがあれば表示される

**リアルタイム更新**:
- [ ] バッチアクション（前日準備、レース後更新、統合）を実行
- [ ] 完了後、データ品質セクションが自動で更新される

### 5. レスポンシブ確認

- [ ] ブラウザ幅を変更してもレイアウトが崩れない
- [ ] モバイル表示でも見やすい

---

## 📋 完了チェックリスト

### コンポーネント作成
- [ ] `DataStatusCard.tsx` 作成完了
- [ ] `ValidationResultsCard.tsx` 作成完了
- [ ] `SystemHealthCard.tsx` 作成完了
- [ ] `data-quality/index.ts` 作成完了
- [ ] `admin/index.ts` 更新完了

### 管理画面統合
- [ ] `admin/page.tsx` に import 追加
- [ ] state 追加（refreshKey, セクション開閉）
- [ ] refreshDataQuality 関数追加
- [ ] SSE complete ハンドラー修正
- [ ] JSX に2セクション追加

### 動作確認
- [ ] TypeScriptコンパイルエラーなし
- [ ] すべてのカードが表示される
- [ ] API連携が正常動作
- [ ] リアルタイム更新が動作
- [ ] 自動更新（30秒）が動作
- [ ] レスポンシブ対応OK

---

## 🎯 完了後

カカシに報告してください。

```
Phase 1b 完了報告:
- 3つのコンポーネント実装 ✅
- 管理画面統合 ✅
- リアルタイム更新 ✅
- テスト完了 ✅
```

Phase 1c（統合・テスト・ドキュメント）に進みます。

---

**作成者**: カカシ（AI相談役）
**依存**: Phase 1a完了（API実装済み）
**推定時間**: 3-5時間
