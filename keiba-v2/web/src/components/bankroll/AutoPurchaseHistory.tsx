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
import {
  ShoppingCart, AlertCircle, TrendingUp, TrendingDown, ChevronDown, ChevronRight,
  Check, X, Clock, HelpCircle, Bot, Crosshair,
} from 'lucide-react';
import type { LedgerDaily, LedgerRacePurchase } from '@/lib/data/ledger-reader';

interface AutoPurchaseHistoryProps {
  dateStr?: string; // YYYYMMDD形式
}

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

export function AutoPurchaseHistory({ dateStr }: AutoPurchaseHistoryProps) {
  // デフォルトは今日の日付 (YYYY-MM-DD: input[type=date] 用)
  const today = new Date();
  const defaultIso = today.toISOString().slice(0, 10);
  const initialIso = dateStr
    ? `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
    : defaultIso;

  const [selectedDate, setSelectedDate] = useState<string>(initialIso); // YYYY-MM-DD
  const [data, setData] = useState<LedgerDaily | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRaces, setExpandedRaces] = useState<Set<number>>(new Set());

  useEffect(() => {
    const fetchLedger = async () => {
      setLoading(true);
      setError(null);
      setExpandedRaces(new Set());

      try {
        const res = await fetch(`/api/bankroll/ledger/${selectedDate}`);
        if (!res.ok) {
          throw new Error('自動投票履歴の取得に失敗しました');
        }
        const result: LedgerDaily = await res.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'エラーが発生しました');
      } finally {
        setLoading(false);
      }
    };

    fetchLedger();
  }, [selectedDate]);

  const toggleRaceExpand = (index: number) => {
    const newExpanded = new Set(expandedRaces);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedRaces(newExpanded);
  };

  const getRowClass = (race: LedgerRacePurchase) => {
    if (!race.confirmed) {
      return 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800';
    }
    if (race.profit > 0) {
      return 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800';
    }
    return 'bg-slate-50 dark:bg-slate-900/20';
  };

  // 日付ピッカー
  const DatePicker = (
    <div className="flex items-center gap-2">
      <Clock className="h-4 w-4 text-muted-foreground" />
      <input
        type="date"
        value={selectedDate}
        onChange={(e) => setSelectedDate(e.target.value)}
        className="rounded-md border bg-background px-3 py-1.5 text-sm"
      />
    </div>
  );

  if (loading) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Bot className="h-5 w-5" />
              自動投票履歴
            </CardTitle>
            {DatePicker}
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Bot className="h-5 w-5" />
              自動投票履歴
            </CardTitle>
            {DatePicker}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <AlertCircle className="h-5 w-5" />
            <p>{error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const summary = data?.summary;
  const byStrategy = data?.by_strategy ?? [];
  const races = data?.races ?? [];
  const hasData = !!data?.has_data && races.length > 0;

  return (
    <div className="space-y-6">
      {/* ヘッダー + 日付ピッカー */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Bot className="h-5 w-5" />
              自動投票サマリー
              <span className="text-sm font-normal text-muted-foreground">{selectedDate}</span>
            </CardTitle>
            {DatePicker}
          </div>
        </CardHeader>
        <CardContent>
          {!summary || !hasData ? (
            <p className="text-muted-foreground text-center py-4">
              この日の自動投票データはありません
            </p>
          ) : (
            <>
            {!summary.all_reconciled && summary.settled_count > 0 && (
              <div className="mb-3 p-2.5 rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 flex items-start gap-2 text-sm">
                <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <div>
                  <span className="font-semibold">⚠ 未突合・暫定値</span>{' '}
                  — 収支は DB 確定配当ベースの暫定値です。IPAT 実投票履歴との突合（reconcile）が未実施のため、実取引と差異がある可能性があります（券種・点数の記録漏れを含む）。突合後に確定します。
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
              {/* 投資額 */}
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">投資額</div>
                <div className="text-xl font-bold">{formatCurrency(summary.total_bet)}</div>
              </div>
              {/* 払戻 */}
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">払戻</div>
                <div className="text-xl font-bold">{formatCurrency(summary.total_payout)}</div>
              </div>
              {/* 収支 */}
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">収支</div>
                <div className={`text-xl font-bold flex items-center gap-1 ${getProfitColor(summary.profit)}`}>
                  {summary.profit > 0 && <TrendingUp className="h-4 w-4" />}
                  {summary.profit < 0 && <TrendingDown className="h-4 w-4" />}
                  {summary.profit >= 0 ? '+' : ''}{formatCurrency(summary.profit)}
                </div>
              </div>
              {/* 回収率 */}
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">回収率</div>
                <div className={`text-xl font-bold ${getRoiColor(summary.recovery_rate)}`}>
                  {formatPercent(summary.recovery_rate)}
                </div>
              </div>
              {/* 点数 */}
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">点数</div>
                <div className="text-xl font-bold">{summary.bet_count}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{summary.race_count}レース</div>
              </div>
              {/* 的中 */}
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">的中</div>
                <div className="text-xl font-bold">
                  {summary.win_count}<span className="text-sm text-muted-foreground">/{summary.settled_count}</span>
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">確定分</div>
              </div>
              {/* 未確定 */}
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">未確定</div>
                <div className={`text-xl font-bold ${summary.pending_count > 0 ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                  {summary.pending_count}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">点</div>
              </div>
            </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* ===== 戦略別ROIテーブル（目玉） ===== */}
      {hasData && byStrategy.length > 0 && (
        <Card className="border-indigo-200 dark:border-indigo-800">
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Crosshair className="h-4 w-4 text-indigo-600" />
              戦略別ROI（自動投票）
              <Badge variant="outline" className="text-xs">{byStrategy.length}戦略</Badge>
              <span className="text-xs font-normal text-muted-foreground ml-auto">
                ※ 確定(settled)分のみで集計
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
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
                            +{s.pending_count}未確定
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
          </CardContent>
        </Card>
      )}

      {/* ===== レース別購入リスト ===== */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            レース別購入
            {hasData && (
              <Badge variant="secondary" className="ml-2">
                {races.length}レース
              </Badge>
            )}
            <span className="text-sm font-normal text-muted-foreground ml-auto">
              ※ 行クリックで詳細表示
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!hasData ? (
            <p className="text-muted-foreground text-center py-4">
              この日の購入データはありません
            </p>
          ) : (
            <div className="space-y-1">
              {races.map((race, index) => {
                const isExpanded = expandedRaces.has(index);
                return (
                  <div key={race.race_id || index} className={`rounded-lg border ${getRowClass(race)}`}>
                    {/* サマリー行 */}
                    <button
                      onClick={() => toggleRaceExpand(index)}
                      className="w-full flex items-center gap-2 p-3 text-left hover:bg-muted/50 transition-colors"
                    >
                      <span className="text-muted-foreground flex-shrink-0">
                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </span>
                      {/* 発走時刻 */}
                      <span className="text-sm text-muted-foreground w-12 flex-shrink-0">
                        {race.post_time || '--:--'}
                      </span>
                      {/* 場所・R */}
                      <span className="font-bold w-20 flex-shrink-0">{race.venue} {race.race_number}R</span>
                      {/* レース名・距離 */}
                      <span className="text-sm truncate flex-1 min-w-0">
                        {race.race_name && <span className="mr-2">{race.race_name}</span>}
                        {race.distance && <span className="text-muted-foreground">{race.distance}</span>}
                      </span>
                      {/* 購入計 */}
                      <span className="text-right w-20 flex-shrink-0">{formatCurrency(race.total_bet)}</span>
                      {/* 払戻計 */}
                      <span className="text-right w-20 flex-shrink-0">
                        {race.confirmed ? formatCurrency(race.total_payout) : '—'}
                      </span>
                      {/* 収支 */}
                      <span className={`text-right font-bold w-24 flex-shrink-0 flex items-center justify-end gap-1 ${getProfitColor(race.profit)}`}>
                        {race.confirmed && race.profit > 0 && <TrendingUp className="h-3 w-3" />}
                        {race.confirmed && race.profit < 0 && <TrendingDown className="h-3 w-3" />}
                        {race.confirmed ? `${race.profit >= 0 ? '+' : ''}${formatCurrency(race.profit)}` : '—'}
                      </span>
                      {/* 回収率 */}
                      <span className={`text-right w-14 flex-shrink-0 ${getProfitColor(race.profit)}`}>
                        {race.confirmed ? formatPercent(race.recovery_rate) : '—'}
                      </span>
                      {/* 的中/状態 */}
                      <span className="w-24 flex-shrink-0 flex flex-col items-start gap-0.5">
                        {!race.confirmed ? (
                          <Badge variant="outline" className="text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300 border-amber-300">
                            <Clock className="h-3 w-3 mr-1" />
                            未確定
                          </Badge>
                        ) : race.hits && race.hits.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {race.hits.map((hit, i) => (
                              <Badge key={i} variant="default" className="text-xs bg-green-600">
                                {hit}
                              </Badge>
                            ))}
                          </div>
                        ) : (
                          <Badge variant="secondary" className="text-xs">
                            <X className="h-3 w-3 mr-1" />
                            はずれ
                          </Badge>
                        )}
                        {race.confirmed && !race.reconciled && (
                          <span className="text-[10px] text-amber-600 dark:text-amber-400" title="DB配当ベースの暫定値。IPAT突合前。">暫定</span>
                        )}
                      </span>
                    </button>

                    {/* 買い目詳細 */}
                    {isExpanded && race.bets && race.bets.length > 0 && (
                      <div className="border-t bg-muted/30 p-3">
                        {!race.confirmed && (
                          <div className="mb-2 p-2 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-sm flex items-center gap-2">
                            <Clock className="h-4 w-4" />
                            レース結果未確定のため精算待ち
                          </div>
                        )}
                        {race.confirmed && !race.reconciled && (
                          <div className="mb-2 p-2 rounded bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 text-sm flex items-center gap-2">
                            <AlertCircle className="h-4 w-4" />
                            DB 確定配当ベースの<strong>暫定値</strong>（IPAT 突合前）。実取引と差異の可能性があります。
                          </div>
                        )}
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="w-[120px]">戦略</TableHead>
                              <TableHead className="w-[70px]">券種</TableHead>
                              <TableHead className="w-[100px]">買い目</TableHead>
                              <TableHead className="w-[80px] text-right">金額</TableHead>
                              <TableHead className="w-[70px] text-right">オッズ</TableHead>
                              <TableHead className="w-[100px] text-right">払戻</TableHead>
                              <TableHead className="w-[90px]">受付</TableHead>
                              <TableHead className="w-[60px] text-right">EV</TableHead>
                              <TableHead className="w-[60px] text-center">結果</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {race.bets.map((bet, betIndex) => {
                              const rowClass = !race.confirmed
                                ? 'bg-amber-50/50 dark:bg-amber-900/10'
                                : bet.is_hit
                                  ? 'bg-green-100 dark:bg-green-900/30'
                                  : '';

                              return (
                                <TableRow key={betIndex} className={rowClass}>
                                  <TableCell className="font-medium">{bet.strategy_name}</TableCell>
                                  <TableCell>{bet.bet_type}</TableCell>
                                  <TableCell>{bet.selection}</TableCell>
                                  <TableCell className="text-right">{formatCurrency(bet.amount)}</TableCell>
                                  <TableCell className="text-right">
                                    {race.confirmed && bet.is_hit && bet.odds > 0 ? bet.odds.toFixed(1) : '—'}
                                  </TableCell>
                                  <TableCell className={`text-right font-bold ${
                                    !race.confirmed
                                      ? 'text-amber-600 dark:text-amber-400'
                                      : bet.is_hit
                                        ? 'text-green-600'
                                        : 'text-muted-foreground'
                                  }`}>
                                    {!race.confirmed ? '—' : bet.is_hit ? formatCurrency(bet.payout) : '-'}
                                  </TableCell>
                                  <TableCell className="font-mono text-xs text-muted-foreground">
                                    {bet.receipt_number || '—'}
                                  </TableCell>
                                  <TableCell className="text-right font-mono text-xs">
                                    {typeof bet.ev_at_decision === 'number' ? bet.ev_at_decision.toFixed(2) : '—'}
                                  </TableCell>
                                  <TableCell className="text-center">
                                    {!race.confirmed ? (
                                      <HelpCircle className="h-5 w-5 text-amber-500 mx-auto" />
                                    ) : bet.is_hit ? (
                                      <Check className="h-5 w-5 text-green-600 mx-auto" />
                                    ) : (
                                      <X className="h-5 w-5 text-muted-foreground mx-auto" />
                                    )}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    )}

                    {/* 買い目データがない場合 */}
                    {isExpanded && (!race.bets || race.bets.length === 0) && (
                      <div className="border-t bg-muted/30 p-4 text-center text-muted-foreground text-sm">
                        買い目詳細データがありません
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
