'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  TrendingUp, TrendingDown, Target, BarChart3, Calendar,
} from 'lucide-react';

// =====================================================================
// 型定義
// =====================================================================

interface MonthlySummary {
  year: number;
  month: number;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  race_count: number;
  hit_count?: number;
  has_data?: boolean;
  file_exists?: boolean;
}

interface MonthlyRow {
  month: string; // YYYY-MM
  bets: number;
  hits: number;
  hitRate: number;
  invested: number;
  returned: number;
  profit: number;
  roi: number;
}

// =====================================================================
// PerformanceTab コンポーネント
// =====================================================================

export function PerformanceTab() {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1;

  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [monthlyData, setMonthlyData] = useState<MonthlyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [yearTotal, setYearTotal] = useState<MonthlyRow | null>(null);

  // 年間の月別データをロード
  useEffect(() => {
    const fetchAllMonths = async () => {
      setLoading(true);
      const rows: MonthlyRow[] = [];
      const maxMonth = selectedYear === currentYear ? currentMonth : 12;

      const promises = Array.from({ length: maxMonth }, (_, i) => i + 1).map(async (month) => {
        try {
          const res = await fetch(
            `/api/bankroll/summary?year=${selectedYear}&month=${month}`
          );
          if (!res.ok) return null;
          const data: MonthlySummary = await res.json();
          if (!data.has_data && !data.file_exists) return null;

          return {
            month: `${selectedYear}-${String(month).padStart(2, '0')}`,
            bets: data.race_count || 0,
            hits: data.hit_count || 0,
            hitRate: data.race_count > 0 && data.hit_count
              ? (data.hit_count / data.race_count) * 100
              : 0,
            invested: data.total_bet,
            returned: data.total_payout,
            profit: data.profit,
            roi: data.recovery_rate,
          } satisfies MonthlyRow;
        } catch {
          return null;
        }
      });

      const results = await Promise.all(promises);
      for (const r of results) {
        if (r && (r.invested > 0 || r.returned > 0)) {
          rows.push(r);
        }
      }

      setMonthlyData(rows);

      // 年間合計
      if (rows.length > 0) {
        const totInvest = rows.reduce((s, r) => s + r.invested, 0);
        const totReturn = rows.reduce((s, r) => s + r.returned, 0);
        const totBets = rows.reduce((s, r) => s + r.bets, 0);
        const totHits = rows.reduce((s, r) => s + r.hits, 0);
        setYearTotal({
          month: `${selectedYear}年合計`,
          bets: totBets,
          hits: totHits,
          hitRate: totBets > 0 ? (totHits / totBets) * 100 : 0,
          invested: totInvest,
          returned: totReturn,
          profit: totReturn - totInvest,
          roi: totInvest > 0 ? (totReturn / totInvest) * 100 : 0,
        });
      } else {
        setYearTotal(null);
      }

      setLoading(false);
    };

    fetchAllMonths();
  }, [selectedYear, currentYear, currentMonth]);

  const formatCurrency = (amount: number) =>
    `¥${Math.abs(amount).toLocaleString()}`;

  const getProfitColor = (profit: number) => {
    if (profit > 0) return 'text-green-600 dark:text-green-400';
    if (profit < 0) return 'text-red-600 dark:text-red-400';
    return 'text-muted-foreground';
  };

  const getRoiColor = (roi: number) => {
    if (roi >= 100) return 'text-green-600 dark:text-green-400 font-bold';
    if (roi >= 80) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  return (
    <div className="space-y-6">
      {/* KPIカード */}
      {yearTotal && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">年間ROI</div>
              <div className={`text-2xl font-bold ${getRoiColor(yearTotal.roi)}`}>
                {yearTotal.roi.toFixed(1)}%
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">年間収支</div>
              <div className={`text-2xl font-bold flex items-center gap-1 ${getProfitColor(yearTotal.profit)}`}>
                {yearTotal.profit >= 0 ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                {yearTotal.profit >= 0 ? '+' : '-'}{formatCurrency(yearTotal.profit)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">レース数</div>
              <div className="text-2xl font-bold">{yearTotal.bets}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">投資額</div>
              <div className="text-xl font-bold">{formatCurrency(yearTotal.invested)}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">払戻額</div>
              <div className="text-xl font-bold">{formatCurrency(yearTotal.returned)}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* バックテスト vs ライブ比較 */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Target className="h-4 w-4 text-indigo-600" />
            Intersection Filter 目標値（バックテスト基準）
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-xs text-muted-foreground">目標ROI</div>
              <div className="text-lg font-bold text-indigo-600">310.7%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">目標的中率</div>
              <div className="text-lg font-bold text-indigo-600">19.6%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">月間ベット</div>
              <div className="text-lg font-bold text-indigo-600">~4回</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">許容MaxDD</div>
              <div className="text-lg font-bold text-amber-600">30%</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 年選択 + 月別テーブル */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              月別収支
            </CardTitle>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <select value={selectedYear}
                onChange={(e) => setSelectedYear(parseInt(e.target.value))}
                className="rounded-md border bg-background px-3 py-1.5 text-sm">
                {Array.from({ length: 5 }, (_, i) => currentYear - i).map((year) => (
                  <option key={year} value={year}>{year}年</option>
                ))}
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">データを読み込み中...</div>
          ) : monthlyData.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {selectedYear}年のデータがありません
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="py-2 px-2 text-left">月</th>
                    <th className="py-2 px-2 text-right">レース数</th>
                    <th className="py-2 px-2 text-right">投資額</th>
                    <th className="py-2 px-2 text-right">払戻額</th>
                    <th className="py-2 px-2 text-right">収支</th>
                    <th className="py-2 px-2 text-right">回収率</th>
                    <th className="py-2 px-2 text-center">状態</th>
                  </tr>
                </thead>
                <tbody>
                  {monthlyData.map((row) => (
                    <tr key={row.month} className="border-b hover:bg-muted/50">
                      <td className="py-2 px-2 font-medium">{row.month}</td>
                      <td className="py-2 px-2 text-right font-mono">{row.bets}</td>
                      <td className="py-2 px-2 text-right font-mono">{formatCurrency(row.invested)}</td>
                      <td className="py-2 px-2 text-right font-mono">{formatCurrency(row.returned)}</td>
                      <td className={`py-2 px-2 text-right font-mono ${getProfitColor(row.profit)}`}>
                        {row.profit >= 0 ? '+' : '-'}{formatCurrency(row.profit)}
                      </td>
                      <td className={`py-2 px-2 text-right font-mono ${getRoiColor(row.roi)}`}>
                        {row.roi.toFixed(1)}%
                      </td>
                      <td className="py-2 px-2 text-center">
                        {row.roi >= 100 ? (
                          <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">黒字</Badge>
                        ) : (
                          <Badge variant="secondary" className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">赤字</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
                {yearTotal && (
                  <tfoot>
                    <tr className="border-t-2 font-bold bg-muted/30">
                      <td className="py-2 px-2">合計</td>
                      <td className="py-2 px-2 text-right font-mono">{yearTotal.bets}</td>
                      <td className="py-2 px-2 text-right font-mono">{formatCurrency(yearTotal.invested)}</td>
                      <td className="py-2 px-2 text-right font-mono">{formatCurrency(yearTotal.returned)}</td>
                      <td className={`py-2 px-2 text-right font-mono ${getProfitColor(yearTotal.profit)}`}>
                        {yearTotal.profit >= 0 ? '+' : '-'}{formatCurrency(yearTotal.profit)}
                      </td>
                      <td className={`py-2 px-2 text-right font-mono ${getRoiColor(yearTotal.roi)}`}>
                        {yearTotal.roi.toFixed(1)}%
                      </td>
                      <td className="py-2 px-2 text-center">
                        {yearTotal.roi >= 100 ? (
                          <Badge className="bg-green-600 text-white">年間黒字</Badge>
                        ) : (
                          <Badge variant="destructive">年間赤字</Badge>
                        )}
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 累積P&Lバーグラフ（シンプル版） */}
      {monthlyData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">累積収支推移</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(() => {
                let cumulative = 0;
                const maxAbs = monthlyData.reduce((max, row) => {
                  cumulative += row.profit;
                  return Math.max(max, Math.abs(cumulative));
                }, 1);
                cumulative = 0;

                return monthlyData.map((row) => {
                  cumulative += row.profit;
                  const pct = (cumulative / maxAbs) * 100;
                  const isPositive = cumulative >= 0;

                  return (
                    <div key={row.month} className="flex items-center gap-2">
                      <div className="w-16 text-xs text-muted-foreground font-mono">
                        {row.month.slice(5)}月
                      </div>
                      <div className="flex-1 relative h-6">
                        <div className="absolute inset-0 bg-gray-100 dark:bg-gray-800 rounded" />
                        <div
                          className={`absolute top-0 h-full rounded ${
                            isPositive
                              ? 'bg-green-500/70 left-1/2'
                              : 'bg-red-500/70 right-1/2'
                          }`}
                          style={{
                            width: `${Math.abs(pct) / 2}%`,
                            ...(isPositive ? {} : { right: '50%', left: 'auto' }),
                          }}
                        />
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div className="w-px h-full bg-gray-300 dark:bg-gray-600" />
                        </div>
                      </div>
                      <div className={`w-24 text-right text-xs font-mono ${getProfitColor(cumulative)}`}>
                        {cumulative >= 0 ? '+' : '-'}{formatCurrency(cumulative)}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
