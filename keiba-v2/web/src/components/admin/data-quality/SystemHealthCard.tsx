'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
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
        <div className="h-6 w-40 animate-pulse rounded bg-muted" />
        <div className="h-40 w-full animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
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

  const CheckStatus = ({ status }: { status: string }) => {
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
              最終更新:{' '}
              {new Date(health.timestamp).toLocaleTimeString('ja-JP')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchHealth}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2">
            <Switch
              id="auto-refresh"
              checked={autoRefresh}
              onCheckedChange={setAutoRefresh}
            />
            <Label
              htmlFor="auto-refresh"
              className="cursor-pointer text-xs"
            >
              自動更新
            </Label>
          </div>
        </div>
      </div>

      {/* ヘルスチェックグリッド */}
      <div className="grid grid-cols-2 gap-3">
        {/* ディレクトリ */}
        <Card className="p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">📁 ディレクトリ</span>
            <CheckStatus status={health.checks.directories.status} />
          </div>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span>競馬データ</span>
              <span>
                {health.checks.directories.details.keibaDataRoot.exists
                  ? '✓'
                  : '×'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>JRA-VAN</span>
              <span>
                {health.checks.directories.details.jvDataRoot.exists
                  ? '✓'
                  : '×'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>レースデータ</span>
              <span>
                {health.checks.directories.details.racesDir.dateCount}日分
              </span>
            </div>
          </div>
        </Card>

        {/* ディスク容量 */}
        <Card className="p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">💾 ディスク容量</span>
            <CheckStatus status={health.checks.diskSpace.status} />
          </div>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span>レースデータ</span>
              <span>
                {health.checks.diskSpace.details.racesDataSizeMB.toFixed(0)} MB
              </span>
            </div>
            <div className="flex justify-between">
              <span>キャッシュ</span>
              <span>
                {health.checks.diskSpace.details.cacheSizeMB.toFixed(0)} MB
              </span>
            </div>
            <div className="flex justify-between font-medium">
              <span>合計</span>
              <span>
                {health.checks.diskSpace.details.totalSizeMB.toFixed(0)} MB
              </span>
            </div>
          </div>
        </Card>

        {/* インデックス */}
        <Card className="p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">📇 インデックス</span>
            <CheckStatus status={health.checks.indexHealth.status} />
          </div>
          <div className="space-y-1 text-xs">
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
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">🧠 メモリ</span>
            <CheckStatus status={health.checks.memory.status} />
          </div>
          <div className="space-y-1 text-xs">
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
            <div className="rounded bg-red-50 p-2 dark:bg-red-950">
              <div className="mb-1 text-sm font-medium text-red-700 dark:text-red-300">
                エラー
              </div>
              <ul className="space-y-1 text-xs text-red-600 dark:text-red-400">
                {health.errors.map((err, idx) => (
                  <li key={idx}>• {err}</li>
                ))}
              </ul>
            </div>
          )}
          {health.warnings.length > 0 && (
            <div className="rounded bg-yellow-50 p-2 dark:bg-yellow-950">
              <div className="mb-1 text-sm font-medium text-yellow-700 dark:text-yellow-300">
                警告
              </div>
              <ul className="space-y-1 text-xs text-yellow-600 dark:text-yellow-400">
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
