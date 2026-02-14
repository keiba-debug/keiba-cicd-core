'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ShoppingCart, AlertCircle, TrendingUp, TrendingDown, ChevronDown, ChevronRight, Check, X, Clock, HelpCircle } from 'lucide-react';

interface BetDetail {
  bet_type: string;
  selection: string;
  amount: number;
  odds: number;
  is_hit: boolean;
  payout: number;
}

interface RacePurchase {
  race_id?: string;
  venue: string;
  race_number: number;
  race_name: string;
  post_time: string;
  distance: string;
  track_condition: string;
  grade?: string;
  entries: number;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  hits: string[];
  bets?: BetDetail[];
  confirmed?: boolean; // 結果確定済みかどうか
}

interface DailyData {
  date: string;
  races: RacePurchase[];
  summary: {
    total_bet: number;
    total_payout: number;
    profit: number;
    recovery_rate: number;
    race_count: number;
    win_count: number;
  };
  has_data?: boolean;
  file_exists?: boolean;
}

interface DailyPurchaseListProps {
  dateStr?: string; // YYYYMMDD形式
  refreshKey?: number; // 変更時に再取得
}

export function DailyPurchaseList({ dateStr, refreshKey }: DailyPurchaseListProps) {
  const [data, setData] = useState<DailyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRaces, setExpandedRaces] = useState<Set<number>>(new Set());

  // デフォルトは今日の日付
  const today = new Date();
  const targetDateStr = dateStr || today.toISOString().slice(0, 10).replace(/-/g, '');

  useEffect(() => {
    const fetchDailyData = async () => {
      setLoading(true);
      setError(null);
      setExpandedRaces(new Set()); // リセット

      try {
        const res = await fetch(`/api/bankroll/daily/${targetDateStr}`);
        if (!res.ok) {
          throw new Error('購入リストの取得に失敗しました');
        }
        const result = await res.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'エラーが発生しました');
      } finally {
        setLoading(false);
      }
    };

    fetchDailyData();
  }, [targetDateStr, refreshKey]);

  // 行の展開/折りたたみ
  const toggleRaceExpand = (index: number) => {
    const newExpanded = new Set(expandedRaces);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedRaces(newExpanded);
  };

  const formatCurrency = (amount: number) => {
    return `¥${amount.toLocaleString()}`;
  };

  const formatPercent = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getProfitColor = (profit: number) => {
    if (profit > 0) return 'text-green-600 dark:text-green-400';
    if (profit < 0) return 'text-red-600 dark:text-red-400';
    return 'text-muted-foreground';
  };

  const getRowClass = (race: RacePurchase) => {
    // 未確定の場合
    if (race.confirmed === false) {
      return 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800';
    }
    // 確定後的中
    if (race.profit > 0) {
      return 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800';
    }
    // 確定後はずれ
    return 'bg-slate-50 dark:bg-slate-900/20';
  };

  // 状態に応じたバッジを返す
  const getStatusBadge = (race: RacePurchase) => {
    if (race.confirmed === false) {
      return (
        <Badge variant="outline" className="text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300 border-amber-300">
          <Clock className="h-3 w-3 mr-1" />
          未確定
        </Badge>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            【購入リスト】
          </CardTitle>
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
          <CardTitle className="text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            【購入リスト】
          </CardTitle>
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

  // データがない場合
  if (!data || !data.races || data.races.length === 0) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            【購入リスト】
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center py-4">
            この日の購入データはありません
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <ShoppingCart className="h-5 w-5" />
          【購入リスト】
          <Badge variant="secondary" className="ml-2">
            {data.races.length}レース
          </Badge>
          <Badge variant="outline" className="text-xs ml-2">
            時刻順
          </Badge>
          <span className="text-sm font-normal text-muted-foreground ml-auto">
            ※ 行クリックで詳細表示
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {data.races.map((race, index) => {
            const isExpanded = expandedRaces.has(index);
            return (
              <div key={index} className={`rounded-lg border ${getRowClass(race)}`}>
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
                    {race.race_name && (
                      <span className="mr-2">{race.race_name}</span>
                    )}
                    {race.distance && (
                      <span className="text-muted-foreground">{race.distance}</span>
                    )}
                  </span>
                  {/* 購入計 */}
                  <span className="text-right w-20 flex-shrink-0">{formatCurrency(race.total_bet)}</span>
                  {/* 払戻計 */}
                  <span className="text-right w-20 flex-shrink-0">{formatCurrency(race.total_payout)}</span>
                  {/* 収支 */}
                  <span className={`text-right font-bold w-24 flex-shrink-0 flex items-center justify-end gap-1 ${getProfitColor(race.profit)}`}>
                    {race.profit > 0 && <TrendingUp className="h-3 w-3" />}
                    {race.profit < 0 && <TrendingDown className="h-3 w-3" />}
                    {race.profit >= 0 ? '+' : ''}{formatCurrency(race.profit)}
                  </span>
                  {/* 回収率 */}
                  <span className={`text-right w-14 flex-shrink-0 ${getProfitColor(race.profit)}`}>
                    {formatPercent(race.recovery_rate)}
                  </span>
                  {/* 的中/状態 */}
                  <span className="w-24 flex-shrink-0">
                    {race.confirmed === false ? (
                      // 未確定
                      <Badge variant="outline" className="text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300 border-amber-300">
                        <Clock className="h-3 w-3 mr-1" />
                        未確定
                      </Badge>
                    ) : race.hits && race.hits.length > 0 ? (
                      // 確定後的中
                      <div className="flex flex-wrap gap-1">
                        {race.hits.map((hit, i) => (
                          <Badge key={i} variant="default" className="text-xs bg-green-600">
                            {hit}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      // 確定後はずれ
                      <Badge variant="secondary" className="text-xs">
                        <X className="h-3 w-3 mr-1" />
                        はずれ
                      </Badge>
                    )}
                  </span>
                </button>

                {/* 買い目詳細 */}
                {isExpanded && race.bets && race.bets.length > 0 && (
                  <div className="border-t bg-muted/30 p-3">
                    {race.confirmed === false && (
                      <div className="mb-2 p-2 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-sm flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        レース結果未確定のため、払戻は予想値です
                      </div>
                    )}
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[80px]">券種</TableHead>
                          <TableHead className="w-[100px]">買い目</TableHead>
                          <TableHead className="w-[80px] text-right">金額</TableHead>
                          <TableHead className="w-[70px] text-right">オッズ</TableHead>
                          <TableHead className="w-[100px] text-right">払戻</TableHead>
                          <TableHead className="w-[60px] text-center">結果</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {race.bets.map((bet, betIndex) => {
                          // 未確定の場合の行スタイル
                          const rowClass = race.confirmed === false
                            ? 'bg-amber-50/50 dark:bg-amber-900/10'
                            : bet.is_hit
                              ? 'bg-green-100 dark:bg-green-900/30'
                              : '';
                          
                          return (
                            <TableRow key={betIndex} className={rowClass}>
                              <TableCell className="font-medium">{bet.bet_type}</TableCell>
                              <TableCell>{bet.selection}</TableCell>
                              <TableCell className="text-right">{formatCurrency(bet.amount)}</TableCell>
                              <TableCell className="text-right">{bet.odds.toFixed(1)}</TableCell>
                              <TableCell className={`text-right font-bold ${
                                race.confirmed === false
                                  ? 'text-amber-600 dark:text-amber-400'
                                  : bet.is_hit
                                    ? 'text-green-600'
                                    : 'text-muted-foreground'
                              }`}>
                                {race.confirmed === false ? (
                                  // 未確定: オッズから予想払戻を表示
                                  <span className="flex items-center justify-end gap-1">
                                    <span className="text-xs text-muted-foreground">(予想)</span>
                                    {formatCurrency(Math.floor(bet.amount * bet.odds))}
                                  </span>
                                ) : bet.is_hit ? (
                                  formatCurrency(bet.payout)
                                ) : (
                                  '-'
                                )}
                              </TableCell>
                              <TableCell className="text-center">
                                {race.confirmed === false ? (
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
      </CardContent>
    </Card>
  );
}
