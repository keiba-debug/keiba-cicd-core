'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  TrendingUp, TrendingDown, Target, BarChart3, Calendar, Crosshair, ShoppingCart,
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

interface StrategyBet {
  date: string;
  race_id: string;
  umaban: number;
  horse_name: string;
  odds: number;
  win_amount: number;
  strength: string;
  win_vb_gap: number;
  win_ev: number;
  finish_position: number | null;
  is_win: boolean;
  win_return: number;
}

interface PurchaseStats {
  total_bets: number;
  invested: number;
  payout: number;
  profit: number;
  roi: number;
  wins: number;
  losses: number;
  pending: number;
  hit_rate: number;
  matched_with_recommendation: number;
  follow_rate: number;
  items: Array<{
    date: string;
    race_id: string;
    bet_type: string;
    selection: string;
    amount: number;
    odds: number | null;
    status: string;
    payout: number;
    is_intersection: boolean;
  }>;
}

interface StrategyPerformance {
  preset: string;
  year: number;
  overall: {
    bets: number;
    hits: number;
    hitRate: number;
    invested: number;
    returned: number;
    profit: number;
    roi: number;
    avgOdds: number;
  };
  monthly: MonthlyRow[];
  bets: StrategyBet[];
  backtest: {
    expectedRoi: number;
    expectedHitRate: number;
    annualBets: number;
    monthlyBets: number;
  } | null;
  purchase_stats: PurchaseStats | null;
}

// =====================================================================
// PerformanceTab コンポーネント
// =====================================================================

export function PerformanceTab() {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1;

  const [selectedYear, setSelectedYear] = useState(currentYear);

  // TARGET CSV 全体成績
  const [monthlyData, setMonthlyData] = useState<MonthlyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [yearTotal, setYearTotal] = useState<MonthlyRow | null>(null);

  // Intersection 成績
  const [strategyData, setStrategyData] = useState<StrategyPerformance | null>(null);
  const [strategyLoading, setStrategyLoading] = useState(true);

  // TARGET CSV 全体成績をロード
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

  // Intersection Strategy 成績をロード
  useEffect(() => {
    const fetchStrategy = async () => {
      setStrategyLoading(true);
      try {
        const res = await fetch(
          `/api/bankroll/strategy-performance?preset=intersection&year=${selectedYear}`
        );
        if (res.ok) {
          const data: StrategyPerformance = await res.json();
          setStrategyData(data);
        } else {
          setStrategyData(null);
        }
      } catch {
        setStrategyData(null);
      }
      setStrategyLoading(false);
    };
    fetchStrategy();
  }, [selectedYear]);

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

  const sp = strategyData?.overall;
  const bt = strategyData?.backtest;
  const ps = strategyData?.purchase_stats;

  return (
    <div className="space-y-6">
      {/* ===== Intersection Filter 成績 ===== */}
      <Card className="border-indigo-200 dark:border-indigo-800">
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Crosshair className="h-4 w-4 text-indigo-600" />
            Intersection Filter 成績（ML推奨ベースの集計）
            <Badge variant="outline" className="text-xs">
              rank_w=1 / Gap{'\u2265'}4 / EV{'\u2265'}1.3 / R{'\u2264'}60
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {strategyLoading ? (
            <div className="text-center py-6 text-muted-foreground">Intersection成績を集計中...</div>
          ) : !sp || sp.bets === 0 ? (
            <div className="text-center py-6 text-muted-foreground">
              {selectedYear}年のIntersection推奨データがありません
              <p className="text-xs mt-1">predictions.json に推奨が記録されると集計されます</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* KPIグリッド: 実績 vs バックテスト */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">ROI</div>
                  <div className={`text-2xl font-bold ${getRoiColor(sp.roi)}`}>
                    {sp.roi.toFixed(1)}%
                  </div>
                  {bt && (
                    <div className="text-xs text-indigo-500 mt-0.5">
                      目標: {bt.expectedRoi}%
                    </div>
                  )}
                </div>
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">的中率</div>
                  <div className="text-2xl font-bold">
                    {(sp.hitRate * 100).toFixed(1)}%
                  </div>
                  {bt && (
                    <div className="text-xs text-indigo-500 mt-0.5">
                      目標: {bt.expectedHitRate}%
                    </div>
                  )}
                </div>
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">収支</div>
                  <div className={`text-xl font-bold flex items-center gap-1 ${getProfitColor(sp.profit)}`}>
                    {sp.profit >= 0 ? '+' : '-'}{formatCurrency(sp.profit)}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {sp.bets}ベット / {sp.hits}的中
                  </div>
                </div>
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">平均オッズ</div>
                  <div className="text-2xl font-bold">{sp.avgOdds.toFixed(1)}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    投資 {formatCurrency(sp.invested)}
                  </div>
                </div>
              </div>

              {/* 月別 Intersection 成績テーブル */}
              {strategyData!.monthly.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-xs text-muted-foreground">
                        <th className="py-1.5 px-2 text-left">月</th>
                        <th className="py-1.5 px-2 text-right">ベット</th>
                        <th className="py-1.5 px-2 text-right">的中</th>
                        <th className="py-1.5 px-2 text-right">投資</th>
                        <th className="py-1.5 px-2 text-right">払戻</th>
                        <th className="py-1.5 px-2 text-right">収支</th>
                        <th className="py-1.5 px-2 text-right">ROI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategyData!.monthly.map((row) => (
                        <tr key={row.month} className="border-b hover:bg-indigo-50/50 dark:hover:bg-indigo-950/20">
                          <td className="py-1.5 px-2 font-medium">{row.month}</td>
                          <td className="py-1.5 px-2 text-right font-mono">{row.bets}</td>
                          <td className="py-1.5 px-2 text-right font-mono">{row.hits}</td>
                          <td className="py-1.5 px-2 text-right font-mono">{formatCurrency(row.invested)}</td>
                          <td className="py-1.5 px-2 text-right font-mono">{formatCurrency(row.returned)}</td>
                          <td className={`py-1.5 px-2 text-right font-mono ${getProfitColor(row.profit)}`}>
                            {row.profit >= 0 ? '+' : '-'}{formatCurrency(row.profit)}
                          </td>
                          <td className={`py-1.5 px-2 text-right font-mono ${getRoiColor(row.roi)}`}>
                            {row.roi.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* 個別ベット履歴 */}
              {strategyData!.bets.length > 0 && (
                <details className="group">
                  <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                    個別ベット履歴を表示 ({strategyData!.bets.length}件)
                  </summary>
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-muted-foreground">
                          <th className="py-1 px-1 text-left">日付</th>
                          <th className="py-1 px-1 text-left">馬名</th>
                          <th className="py-1 px-1 text-right">Gap</th>
                          <th className="py-1 px-1 text-right">EV</th>
                          <th className="py-1 px-1 text-right">オッズ</th>
                          <th className="py-1 px-1 text-right">投資</th>
                          <th className="py-1 px-1 text-center">着順</th>
                          <th className="py-1 px-1 text-right">払戻</th>
                        </tr>
                      </thead>
                      <tbody>
                        {strategyData!.bets.map((b, idx) => (
                          <tr key={`${b.race_id}-${b.umaban}-${idx}`}
                            className={`border-b ${b.is_win ? 'bg-green-50 dark:bg-green-950/20' : ''}`}>
                            <td className="py-1 px-1 font-mono">{b.date.slice(5)}</td>
                            <td className="py-1 px-1">{b.horse_name}</td>
                            <td className="py-1 px-1 text-right font-mono">+{b.win_vb_gap}</td>
                            <td className="py-1 px-1 text-right font-mono">{b.win_ev.toFixed(2)}</td>
                            <td className="py-1 px-1 text-right font-mono">{b.odds.toFixed(1)}</td>
                            <td className="py-1 px-1 text-right font-mono">¥{b.win_amount.toLocaleString()}</td>
                            <td className="py-1 px-1 text-center">
                              {b.finish_position === null ? '—' :
                                b.finish_position === 0 ? '取消' :
                                b.is_win ? (
                                  <Badge className="bg-green-600 text-white text-xs px-1">1着</Badge>
                                ) : (
                                  <span className="text-muted-foreground">{b.finish_position}着</span>
                                )}
                            </td>
                            <td className={`py-1 px-1 text-right font-mono ${b.win_return > 0 ? 'text-green-600 font-bold' : 'text-muted-foreground'}`}>
                              {b.win_return > 0 ? `¥${b.win_return.toLocaleString()}` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== 実購入成績 ===== */}
      {ps && ps.total_bets > 0 && (
        <Card className="border-green-200 dark:border-green-800">
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <ShoppingCart className="h-4 w-4 text-green-600" />
              実購入成績（ExecuteTab経由の実際の購入）
              <Badge variant="outline" className="text-xs">{ps.total_bets}件</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-4">
              {/* KPIグリッド */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3">
                  <div className="text-xs text-muted-foreground">ROI</div>
                  <div className={`text-2xl font-bold ${ps.pending > 0 ? 'text-muted-foreground' : getRoiColor(ps.roi)}`}>
                    {ps.wins + ps.losses > 0 ? `${ps.roi.toFixed(1)}%` : '未確定'}
                  </div>
                  {sp && sp.bets > 0 && (
                    <div className="text-xs text-muted-foreground mt-0.5">
                      推奨: {sp.roi.toFixed(1)}%
                    </div>
                  )}
                </div>
                <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3">
                  <div className="text-xs text-muted-foreground">的中率</div>
                  <div className="text-2xl font-bold">
                    {ps.wins + ps.losses > 0 ? `${ps.hit_rate.toFixed(1)}%` : '—'}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {ps.wins}的中 / {ps.losses}不的中{ps.pending > 0 ? ` / ${ps.pending}未確定` : ''}
                  </div>
                </div>
                <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3">
                  <div className="text-xs text-muted-foreground">収支</div>
                  <div className={`text-xl font-bold ${getProfitColor(ps.profit)}`}>
                    {ps.profit >= 0 ? '+' : '-'}{formatCurrency(ps.profit)}
                  </div>
                </div>
                <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3">
                  <div className="text-xs text-muted-foreground">投資額</div>
                  <div className="text-xl font-bold">{formatCurrency(ps.invested)}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    払戻 {formatCurrency(ps.payout)}
                  </div>
                </div>
                <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3">
                  <div className="text-xs text-muted-foreground">推奨追従率</div>
                  <div className="text-2xl font-bold">
                    {ps.follow_rate.toFixed(0)}%
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {ps.matched_with_recommendation}/{ps.total_bets}件がIntersection
                  </div>
                </div>
              </div>

              {/* 個別購入履歴 */}
              {ps.items.length > 0 && (
                <details className="group">
                  <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                    個別購入履歴を表示 ({ps.items.length}件)
                  </summary>
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-muted-foreground">
                          <th className="py-1 px-1 text-left">日付</th>
                          <th className="py-1 px-1 text-left">券種</th>
                          <th className="py-1 px-1 text-left">馬券</th>
                          <th className="py-1 px-1 text-right">金額</th>
                          <th className="py-1 px-1 text-right">オッズ</th>
                          <th className="py-1 px-1 text-center">結果</th>
                          <th className="py-1 px-1 text-right">払戻</th>
                          <th className="py-1 px-1 text-center">INT</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ps.items.map((item, i) => (
                          <tr key={`${item.race_id}-${i}`}
                            className={`border-b ${item.status === 'result_win' ? 'bg-green-50 dark:bg-green-950/20' : ''}`}>
                            <td className="py-1 px-1 font-mono">{item.date.slice(5)}</td>
                            <td className="py-1 px-1">{item.bet_type}</td>
                            <td className="py-1 px-1">{item.selection}</td>
                            <td className="py-1 px-1 text-right font-mono">¥{item.amount.toLocaleString()}</td>
                            <td className="py-1 px-1 text-right font-mono">{item.odds?.toFixed(1) ?? '—'}</td>
                            <td className="py-1 px-1 text-center">
                              {item.status === 'result_win' && <Badge className="bg-green-600 text-white text-xs px-1">的中</Badge>}
                              {item.status === 'result_lose' && <span className="text-muted-foreground">✗</span>}
                              {item.status === 'purchased' && <Badge variant="outline" className="text-xs px-1">未確定</Badge>}
                            </td>
                            <td className={`py-1 px-1 text-right font-mono ${item.payout > 0 ? 'text-green-600 font-bold' : 'text-muted-foreground'}`}>
                              {item.payout > 0 ? `¥${item.payout.toLocaleString()}` : '—'}
                            </td>
                            <td className="py-1 px-1 text-center">
                              {item.is_intersection ? (
                                <Crosshair className="h-3 w-3 text-indigo-500 inline" />
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ===== バックテスト vs ライブ比較 ===== */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Target className="h-4 w-4 text-indigo-600" />
            バックテスト vs ライブ
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-xs text-muted-foreground">ROI</div>
              <div className="text-xs text-indigo-500">BT: 310.7%</div>
              <div className={`text-lg font-bold ${sp ? getRoiColor(sp.roi) : 'text-muted-foreground'}`}>
                {sp ? `${sp.roi.toFixed(1)}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">的中率</div>
              <div className="text-xs text-indigo-500">BT: 19.6%</div>
              <div className={`text-lg font-bold ${sp && sp.hitRate > 0 ? '' : 'text-muted-foreground'}`}>
                {sp ? `${(sp.hitRate * 100).toFixed(1)}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">年間ベット数</div>
              <div className="text-xs text-indigo-500">BT: ~46回</div>
              <div className="text-lg font-bold">
                {sp ? sp.bets : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">許容MaxDD</div>
              <div className="text-lg font-bold text-amber-600">30%</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ===== TARGET CSV 全体成績 ===== */}

      {/* 全体KPIカード */}
      {yearTotal && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">年間ROI (全体)</div>
              <div className={`text-2xl font-bold ${getRoiColor(yearTotal.roi)}`}>
                {yearTotal.roi.toFixed(1)}%
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">年間収支 (全体)</div>
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

      {/* 年選択 + 月別テーブル (TARGET全体) */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              月別収支（TARGET全体）
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

      {/* 累積P&Lバーグラフ */}
      {monthlyData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">累積収支推移（TARGET全体）</CardTitle>
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
