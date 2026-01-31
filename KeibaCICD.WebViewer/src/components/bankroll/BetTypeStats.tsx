'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { BarChart3, AlertCircle } from 'lucide-react';

interface BetTypeStat {
  bet_type: string;
  total_bet: number;
  total_payout: number;
  profit: number;
  count: number;
  win_count: number;
  recovery_rate: number;
  win_rate: number;
}

interface StatsData {
  period: string;
  period_label: string;
  date_range?: {
    from: string;
    to: string;
  };
  total_count: number;
  stats: { [key: string]: BetTypeStat };
  _meta?: {
    has_data: boolean;
    file_exists: boolean;
  };
}

type PeriodType = 'current_month' | '3months' | '6months' | '1year';

const PERIOD_OPTIONS: { value: PeriodType; label: string }[] = [
  { value: 'current_month', label: '今月' },
  { value: '3months', label: '直近3ヶ月' },
  { value: '6months', label: '直近6ヶ月' },
  { value: '1year', label: '過去1年' },
];

const PERIOD_STORAGE_KEY = 'bankroll_stats_period';

export function BetTypeStats() {
  const [period, setPeriod] = useState<PeriodType>('current_month');
  const [data, setData] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // localStorageから期間設定を復元
  useEffect(() => {
    const savedPeriod = localStorage.getItem(PERIOD_STORAGE_KEY) as PeriodType | null;
    if (savedPeriod && PERIOD_OPTIONS.some((opt) => opt.value === savedPeriod)) {
      setPeriod(savedPeriod);
    }
  }, []);

  // データ取得
  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      setError(null);

      try {
        const res = await fetch(`/api/bankroll/stats?period=${period}`);
        if (!res.ok) {
          throw new Error('馬券種別実績の取得に失敗しました');
        }
        const result = await res.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'エラーが発生しました');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [period]);

  // 期間変更ハンドラ
  const handlePeriodChange = (newPeriod: PeriodType) => {
    setPeriod(newPeriod);
    localStorage.setItem(PERIOD_STORAGE_KEY, newPeriod);
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

  const getRecoveryRateColor = (rate: number) => {
    if (rate >= 100) return 'text-green-600 dark:text-green-400';
    if (rate >= 80) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  // 警告メッセージは表示しない（ユーザービリティ向上のため削除）

  // 統計データを回収率降順でソート
  const getSortedStats = (): BetTypeStat[] => {
    if (!data || !data.stats) return [];
    return Object.values(data.stats)
      .filter((stat) => stat.count > 0)
      .sort((a, b) => b.recovery_rate - a.recovery_rate);
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            【馬券種別実績】
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
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            【馬券種別実績】
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

  const sortedStats = getSortedStats();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            【馬券種別実績】
          </CardTitle>
        </div>
        {/* 期間選択ボタン */}
        <div className="flex flex-wrap gap-2 mt-3">
          {PERIOD_OPTIONS.map((option) => (
            <Button
              key={option.value}
              variant={period === option.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => handlePeriodChange(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {sortedStats.length === 0 ? (
          <div className="text-center py-8">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">データがありません</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[80px]">券種</TableHead>
                    <TableHead className="w-[100px] text-right">購入金額</TableHead>
                    <TableHead className="w-[100px] text-right">払戻金額</TableHead>
                    <TableHead className="w-[100px] text-right">収支</TableHead>
                    <TableHead className="w-[80px] text-right">回収率</TableHead>
                    <TableHead className="w-[80px] text-right">的中率</TableHead>
                    <TableHead className="w-[60px] text-right">件数</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedStats.map((stat) => (
                    <TableRow key={stat.bet_type}>
                      <TableCell className="font-medium">{stat.bet_type}</TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(stat.total_bet)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(stat.total_payout)}
                      </TableCell>
                      <TableCell
                        className={`text-right font-bold ${getProfitColor(stat.profit)}`}
                      >
                        {stat.profit >= 0 ? '+' : ''}
                        {formatCurrency(stat.profit)}
                      </TableCell>
                      <TableCell
                        className={`text-right font-bold ${getRecoveryRateColor(
                          stat.recovery_rate
                        )}`}
                      >
                        {formatPercent(stat.recovery_rate)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatPercent(stat.win_rate)}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {stat.count}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* フッター情報 */}
            <div className="mt-4 pt-3 border-t text-sm text-muted-foreground">
              {data?.date_range && (
                <span>
                  {data.period_label}（{data.date_range.from}〜{data.date_range.to}）
                </span>
              )}
              {data?.total_count && <span className="ml-4">購入件数: {data.total_count}件</span>}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
