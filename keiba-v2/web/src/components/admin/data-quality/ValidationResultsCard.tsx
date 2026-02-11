'use client';

import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { ValidationResponse } from '@/types/data-quality';

interface ValidationResultsCardProps {
  selectedDate: string;
  refreshKey?: number;
}

export function ValidationResultsCard({
  selectedDate,
  refreshKey,
}: ValidationResultsCardProps) {
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
        <div className="h-6 w-32 animate-pulse rounded bg-muted" />
        <div className="h-20 w-full animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
        ⚠️ 検証結果の取得に失敗しました: {error}
      </div>
    );
  }

  if (!validation) return null;

  const statusVariant =
    validation.validation.overallStatus === 'healthy'
      ? 'default'
      : validation.validation.overallStatus === 'warning'
        ? 'secondary'
        : 'destructive';

  const statusIcon =
    validation.validation.overallStatus === 'healthy'
      ? '✅'
      : validation.validation.overallStatus === 'warning'
        ? '⚠️'
        : '❌';

  const statusText =
    validation.validation.overallStatus === 'healthy'
      ? '正常'
      : validation.validation.overallStatus === 'warning'
        ? '警告あり'
        : 'エラーあり';

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
          <div className="rounded bg-red-500/10 p-2">
            <div className="text-xs text-muted-foreground">重大な問題</div>
            <div className="font-bold text-red-600 dark:text-red-400">
              {validation.validation.criticalIssues}
            </div>
          </div>
          <div className="rounded bg-yellow-500/10 p-2">
            <div className="text-xs text-muted-foreground">警告</div>
            <div className="font-bold text-yellow-600 dark:text-yellow-400">
              {validation.validation.warnings}
            </div>
          </div>
        </div>
      )}

      {/* 問題リスト */}
      {validation.dates.some((d) => d.issues.length > 0) && (
        <div className="max-h-60 space-y-2 overflow-y-auto">
          {validation.dates.map((date) =>
            date.issues.length > 0 ? (
              <div key={date.date} className="rounded border p-2">
                <div className="mb-1 text-sm font-medium">{date.date}</div>
                {date.issues.map((issue, idx) => (
                  <div
                    key={idx}
                    className={`flex items-start gap-1 py-1 text-xs ${
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
        <div className="rounded bg-green-50 p-4 text-center text-sm text-green-700 dark:bg-green-950 dark:text-green-300">
          ✅ すべてのチェックに合格しました
        </div>
      )}
    </div>
  );
}
