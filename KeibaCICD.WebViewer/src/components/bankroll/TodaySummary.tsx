'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Calendar, AlertCircle } from 'lucide-react';

interface DailySummary {
  date: string;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  race_count: number;
  win_count?: number;
  has_data?: boolean;
  file_exists?: boolean;
}

interface TodaySummaryProps {
  dateStr?: string; // YYYYMMDD形式
}

// YYYYMMDD形式から表示用にフォーマット
const formatDateDisplay = (dateStr: string): string => {
  const year = parseInt(dateStr.slice(0, 4));
  const month = parseInt(dateStr.slice(4, 6));
  const day = parseInt(dateStr.slice(6, 8));
  return `${year}年${month}月${day}日`;
};

export function TodaySummary({ dateStr }: TodaySummaryProps) {
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // デフォルトは今日の日付
  const today = new Date();
  const targetDateStr = dateStr || today.toISOString().slice(0, 10).replace(/-/g, '');
  const displayDate = formatDateDisplay(targetDateStr);

  useEffect(() => {
    const fetchSummary = async () => {
      setLoading(true);
      setError(null);

      try {
        const res = await fetch(`/api/bankroll/summary?date=${targetDateStr}`);
        if (!res.ok) {
          throw new Error('成績の取得に失敗しました');
        }
        const data = await res.json();
        setSummary(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'エラーが発生しました');
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, [targetDateStr]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
    }).format(amount);
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

  if (loading) {
    return (
      <Card className="mb-6 border-2 border-primary/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            【成績】
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
      <Card className="mb-6 border-2 border-red-200 dark:border-red-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            【成績】
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
  if (!summary || !summary.has_data || summary.race_count === 0) {
    return (
      <Card className="mb-6 border-2 border-muted">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            【成績】
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
    <Card className="mb-6 border-2 border-primary/20 bg-gradient-to-r from-background to-muted/30">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          【成績】
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-sm text-muted-foreground mb-1">購入計</div>
            <div className="text-xl font-bold">
              {formatCurrency(summary.total_bet)}
            </div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground mb-1">払戻計</div>
            <div className="text-xl font-bold">
              {formatCurrency(summary.total_payout)}
            </div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground mb-1">収支</div>
            <div
              className={`text-xl font-bold flex items-center gap-1 ${getProfitColor(
                summary.profit
              )}`}
            >
              {summary.profit >= 0 ? (
                <TrendingUp className="h-4 w-4" />
              ) : (
                <TrendingDown className="h-4 w-4" />
              )}
              {formatCurrency(summary.profit)}
            </div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground mb-1">回収率</div>
            <div
              className={`text-xl font-bold ${getRecoveryRateColor(
                summary.recovery_rate
              )}`}
            >
              {formatPercent(summary.recovery_rate)}
            </div>
          </div>
        </div>
        <div className="mt-3 pt-3 border-t flex items-center gap-4 text-sm text-muted-foreground">
          <span>購入件数: {summary.race_count}件</span>
          {summary.win_count !== undefined && (
            <span>的中: {summary.win_count}件</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
