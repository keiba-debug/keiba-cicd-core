'use client';

import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
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
        <div className="h-6 w-32 animate-pulse rounded bg-muted" />
        <div className="h-20 w-full animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
        ⚠️ データ状況の取得に失敗しました: {error}
      </div>
    );
  }

  if (!status) return null;

  const coverageColor =
    status.summary.coveragePercent >= 80
      ? 'default'
      : status.summary.coveragePercent >= 50
        ? 'secondary'
        : 'destructive';

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
        <div className="rounded bg-muted/30 p-2">
          <div className="text-xs text-muted-foreground">総日数</div>
          <div className="font-bold">{status.summary.totalDates}</div>
        </div>
        <div className="rounded bg-green-500/10 p-2">
          <div className="text-xs text-muted-foreground">データあり</div>
          <div className="font-bold text-green-600 dark:text-green-400">
            {status.summary.datesWithData}
          </div>
        </div>
        <div className="rounded bg-yellow-500/10 p-2">
          <div className="text-xs text-muted-foreground">データなし</div>
          <div className="font-bold text-yellow-600 dark:text-yellow-400">
            {status.summary.datesWithoutData}
          </div>
        </div>
      </div>

      {/* 詳細（折りたたみ） */}
      {status.dates.length > 0 && (
        <Collapsible open={isDetailsOpen} onOpenChange={setIsDetailsOpen}>
          <CollapsibleTrigger className="flex items-center gap-1 text-sm text-blue-600 hover:underline dark:text-blue-400">
            詳細を表示 ({status.dates.length}件)
            {isDetailsOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 max-h-60 space-y-2 overflow-y-auto">
              {status.dates.map((date) => (
                <div
                  key={date.date}
                  className="rounded bg-muted/20 p-2 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{date.displayDate}</span>
                    <Badge
                      variant={date.hasData ? 'default' : 'secondary'}
                      className="text-xs"
                    >
                      {date.hasData ? '✓' : '×'}
                    </Badge>
                  </div>
                  {date.hasData && date.tracks.length > 0 && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {date.tracks
                        .map((t) => `${t.track}(${t.raceCount}R)`)
                        .join(', ')}
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
      <div className="border-t pt-2 text-xs text-muted-foreground">
        ディスク使用量: {status.diskUsage.totalSizeMB.toFixed(1)} MB (
        {status.diskUsage.fileCount.toLocaleString()} ファイル)
      </div>
    </div>
  );
}
