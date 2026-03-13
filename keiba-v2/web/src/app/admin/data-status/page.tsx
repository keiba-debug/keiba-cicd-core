'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import type { DateDataStatus } from '@/app/api/admin/data-status/route';

// ── ステータスセル ──

function StatusBadge({ ok, label }: { ok: boolean; label?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${
        ok ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
      }`}
    >
      {ok ? '✓' : '✗'}{label ? ` ${label}` : ''}
    </span>
  );
}

function RateCell({ rate, count }: { rate: number; count: number }) {
  if (count === 0) return <span className="text-muted-foreground text-xs">—</span>;
  const color =
    rate === 100
      ? 'text-green-600 dark:text-green-400'
      : rate >= 50
        ? 'text-yellow-600 dark:text-yellow-400'
        : 'text-red-600 dark:text-red-400';
  return <span className={`text-xs font-mono ${color}`}>{rate}%</span>;
}

function BabaStatusCell({ status }: { status: 'ok' | 'partial' | 'none' | null }) {
  if (status === null) return <span className="text-muted-foreground text-xs">—</span>;
  if (status === 'ok')
    return <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">✓</span>;
  if (status === 'partial')
    return <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">△</span>;
  return <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">✗</span>;
}

// ── メインページ ──

export default function DataStatusPage() {
  const [dates, setDates] = useState<DateDataStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/data-status');
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setDates(data.dates);
      setLastRefreshed(new Date().toLocaleTimeString('ja-JP'));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="container mx-auto p-4 max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">データ登録状況</h1>
          {lastRefreshed && (
            <p className="text-xs text-muted-foreground mt-0.5">最終更新: {lastRefreshed}</p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
          更新
        </Button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">直近12週 開催日別ステータス</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left px-3 py-2 font-medium">日付</th>
                  <th className="text-right px-3 py-2 font-medium">インデックス</th>
                  <th className="text-right px-3 py-2 font-medium">race JSON</th>
                  <th className="text-center px-3 py-2 font-medium">KB登録率</th>
                  <th className="text-center px-3 py-2 font-medium">JRDB</th>
                  <th className="text-center px-3 py-2 font-medium">馬場</th>
                  <th className="text-center px-3 py-2 font-medium">成績</th>
                  <th className="text-center px-3 py-2 font-medium">予測</th>
                  <th className="text-left px-3 py-2 font-medium">予測生成日時</th>
                </tr>
              </thead>
              <tbody>
                {loading && dates.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-muted-foreground">
                      読み込み中...
                    </td>
                  </tr>
                ) : dates.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-muted-foreground">
                      データなし
                    </td>
                  </tr>
                ) : (
                  dates.map((d) => {
                    const isToday =
                      d.date === new Date().toISOString().substring(0, 10);
                    const raceJsonMissing = d.indexCount > 0 && d.raceJsonCount < d.indexCount;
                    return (
                      <tr
                        key={d.date}
                        className={`border-b last:border-0 hover:bg-muted/30 ${isToday ? 'bg-blue-50/50 dark:bg-blue-950/30' : ''}`}
                      >
                        {/* 日付 */}
                        <td className="px-3 py-2 font-mono text-sm">
                          {d.date}
                          {isToday && (
                            <span className="ml-1.5 text-xs text-blue-600 dark:text-blue-400">今日</span>
                          )}
                        </td>

                        {/* インデックス */}
                        <td className="px-3 py-2 text-right font-mono text-sm">
                          {d.indexCount > 0 ? (
                            <span className="text-foreground">{d.indexCount}R</span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>

                        {/* race JSON */}
                        <td className="px-3 py-2 text-right font-mono text-sm">
                          {d.raceJsonCount > 0 ? (
                            <span className={raceJsonMissing ? 'text-yellow-600 dark:text-yellow-400' : 'text-foreground'}>
                              {d.raceJsonCount}
                              {raceJsonMissing && (
                                <span className="text-xs ml-0.5">/{d.indexCount}</span>
                              )}
                            </span>
                          ) : d.indexCount > 0 ? (
                            <span className="text-red-500">0</span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>

                        {/* KB登録率 */}
                        <td className="px-3 py-2 text-center">
                          <RateCell rate={d.kbRate} count={d.raceJsonCount} />
                        </td>

                        {/* JRDB */}
                        <td className="px-3 py-2 text-center">
                          <RateCell rate={d.jrdbRate} count={d.raceJsonCount} />
                        </td>

                        {/* 馬場（含水率/クッション値） */}
                        <td className="px-3 py-2 text-center">
                          <BabaStatusCell status={d.babaStatus} />
                        </td>

                        {/* 成績 */}
                        <td className="px-3 py-2 text-center">
                          {d.raceJsonCount > 0 ? (
                            <StatusBadge ok={d.hasResults} />
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                        </td>

                        {/* 予測 */}
                        <td className="px-3 py-2 text-center">
                          {d.indexCount > 0 ? (
                            <StatusBadge ok={d.hasPredictions} />
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                        </td>

                        {/* 予測生成日時 */}
                        <td className="px-3 py-2 text-xs text-muted-foreground font-mono">
                          {d.predictionsAt
                            ? d.predictionsAt.replace('T', ' ').substring(0, 16)
                            : '—'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 凡例 */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <div><span className="font-medium text-foreground">インデックス</span>: race_date_index のレース数</div>
        <div><span className="font-medium text-foreground">race JSON</span>: race_*.json ファイル数（黄=不足、赤=0）</div>
        <div><span className="font-medium text-foreground">KB登録率</span>: kb_ext ファイル数 / race JSON 数</div>
        <div><span className="font-medium text-foreground">JRDB</span>: jrdb_pre_idm 設定済みレース率</div>
        <div><span className="font-medium text-foreground">馬場</span>: 含水率/クッション値 ✓=全R有 △=一部 ✗=なし</div>
        <div><span className="font-medium text-foreground">成績</span>: finish_position データあり</div>
        <div><span className="font-medium text-foreground">予測</span>: predictions.json 存在</div>
      </div>
    </div>
  );
}
