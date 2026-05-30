'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { CalendarRange, Crosshair } from 'lucide-react';
import type { PeriodSummary } from '@/lib/data/ledger-reader';

const formatCurrency = (amount: number) => `¥${amount.toLocaleString()}`;
const formatPercent = (value: number) => `${value.toFixed(1)}%`;

const getProfitColor = (profit: number) => {
  if (profit > 0) return 'text-green-600 dark:text-green-400';
  if (profit < 0) return 'text-red-600 dark:text-red-400';
  return 'text-muted-foreground';
};

const getRoiColor = (roi: number) => {
  if (roi >= 100) return 'text-green-600 dark:text-green-400';
  if (roi > 0) return 'text-red-600 dark:text-red-400';
  return 'text-muted-foreground';
};

/** 月次の戦略別ROI + 日次推移（当月、ledger 期間集計 API） */
export function AutoPurchaseMonthly() {
  const [data, setData] = useState<PeriodSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSummary = async () => {
      setLoading(true);
      try {
        // 引数なし = 当月
        const res = await fetch('/api/bankroll/ledger/summary');
        if (res.ok) {
          const result: PeriodSummary = await res.json();
          setData(result);
        } else {
          setData(null);
        }
      } catch {
        setData(null);
      }
      setLoading(false);
    };
    fetchSummary();
  }, []);

  const byStrategy = data?.by_strategy ?? [];
  const daily = (data?.daily ?? []).filter((d) => d.total_bet > 0 || d.total_payout > 0);
  const summary = data?.summary;
  const hasData = byStrategy.length > 0 || daily.length > 0;

  // 日次バーの最大絶対値（収支の振れ幅）
  const maxAbsDailyProfit = daily.reduce((m, d) => Math.max(m, Math.abs(d.profit)), 1);

  return (
    <Card className="border-indigo-200 dark:border-indigo-800">
      <CardHeader className="py-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <CalendarRange className="h-4 w-4 text-indigo-600" />
          月次サマリー（自動投票）
          {data && (
            <Badge variant="outline" className="text-xs">
              {data.from} 〜 {data.to}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {loading ? (
          <div className="text-center py-6 text-muted-foreground">月次集計中...</div>
        ) : !hasData ? (
          <div className="text-center py-6 text-muted-foreground">
            当月の自動投票データがありません
          </div>
        ) : (
          <div className="space-y-4">
            {/* 当月 KPI */}
            {summary && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">回収率</div>
                  <div className={`text-2xl font-bold ${getRoiColor(summary.recovery_rate)}`}>
                    {formatPercent(summary.recovery_rate)}
                  </div>
                </div>
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">収支</div>
                  <div className={`text-xl font-bold ${getProfitColor(summary.profit)}`}>
                    {summary.profit >= 0 ? '+' : ''}{formatCurrency(summary.profit)}
                  </div>
                </div>
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">投資 / 払戻</div>
                  <div className="text-base font-bold">
                    {formatCurrency(summary.total_bet)}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    払戻 {formatCurrency(summary.total_payout)}
                  </div>
                </div>
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/30 p-3">
                  <div className="text-xs text-muted-foreground">点数</div>
                  <div className="text-2xl font-bold">
                    {summary.bet_count}
                    {summary.pending_count > 0 && (
                      <span className="text-amber-600 dark:text-amber-400 text-xs ml-1">
                        +{summary.pending_count}未確定
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {summary.win_count}/{summary.settled_count}的中
                  </div>
                </div>
              </div>
            )}

            {/* 戦略別ROI（期間集計） */}
            {byStrategy.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground mb-1 flex items-center gap-1">
                  <Crosshair className="h-3 w-3 text-indigo-600" />
                  戦略別ROI（当月累計・確定分のみ）
                </div>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>戦略</TableHead>
                        <TableHead className="text-right">点数</TableHead>
                        <TableHead className="text-right">的中</TableHead>
                        <TableHead className="text-right">投資</TableHead>
                        <TableHead className="text-right">払戻</TableHead>
                        <TableHead className="text-right">収支</TableHead>
                        <TableHead className="text-right">回収率</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {byStrategy.map((s) => (
                        <TableRow key={s.strategy_name} className="hover:bg-indigo-50/50 dark:hover:bg-indigo-950/20">
                          <TableCell className="font-medium">{s.strategy_name}</TableCell>
                          <TableCell className="text-right font-mono">
                            {s.settled_count}
                            {s.pending_count > 0 && (
                              <span className="text-amber-600 dark:text-amber-400 text-xs ml-1">
                                +{s.pending_count}
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {s.hit_count}
                            <span className="text-muted-foreground text-xs ml-1">
                              ({formatPercent(s.hit_rate)})
                            </span>
                          </TableCell>
                          <TableCell className="text-right font-mono">{formatCurrency(s.settled_invest)}</TableCell>
                          <TableCell className="text-right font-mono">{formatCurrency(s.payout)}</TableCell>
                          <TableCell className={`text-right font-mono font-bold ${getProfitColor(s.pnl)}`}>
                            {s.pnl >= 0 ? '+' : ''}{formatCurrency(s.pnl)}
                          </TableCell>
                          <TableCell className={`text-right font-mono ${getRoiColor(s.recovery_rate)}`}>
                            {formatPercent(s.recovery_rate)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}

            {/* 日次推移（簡易バー） */}
            {daily.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground mb-2">日次収支推移</div>
                <div className="space-y-1.5">
                  {daily.map((d) => {
                    const pct = (Math.abs(d.profit) / maxAbsDailyProfit) * 100;
                    const isPositive = d.profit >= 0;
                    return (
                      <div key={d.date} className="flex items-center gap-2">
                        <div className="w-20 text-xs text-muted-foreground font-mono flex-shrink-0">
                          {d.date.slice(5)}
                        </div>
                        <div className="flex-1 relative h-5">
                          <div className="absolute inset-0 bg-gray-100 dark:bg-gray-800 rounded" />
                          <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-px h-full bg-gray-300 dark:bg-gray-600" />
                          </div>
                          <div
                            className={`absolute top-0 h-full rounded ${isPositive ? 'bg-green-500/70 left-1/2' : 'bg-red-500/70'}`}
                            style={{
                              width: `${pct / 2}%`,
                              ...(isPositive ? {} : { right: '50%' }),
                            }}
                          />
                        </div>
                        <div className={`w-24 text-right text-xs font-mono flex-shrink-0 ${getProfitColor(d.profit)}`}>
                          {d.profit >= 0 ? '+' : ''}{formatCurrency(d.profit)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
