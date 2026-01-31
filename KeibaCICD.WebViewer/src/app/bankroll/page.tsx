'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { TrendingUp, TrendingDown, DollarSign, Target, AlertCircle } from 'lucide-react';
import { AlertBar } from '@/components/bankroll/AlertBar';
import { AllocationGuide } from '@/components/bankroll/AllocationGuide';
import { BudgetForm } from '@/components/bankroll/BudgetForm';
import { PurchasePlanSection } from '@/components/bankroll/PurchasePlanSection';

interface MonthlySummary {
  year: number;
  month: number;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  race_count: number;
}

interface BetTypeStats {
  [betType: string]: {
    bet_type: string;
    total_bet: number;
    total_payout: number;
    count: number;
    win_count: number;
    recovery_rate: number;
    win_rate: number;
  };
}

interface DailySummary {
  date: string;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  race_count: number;
  races: any[];
}

export default function BankrollPage() {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1;

  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [selectedMonth, setSelectedMonth] = useState(currentMonth);
  const [monthlySummary, setMonthlySummary] = useState<MonthlySummary | null>(null);
  const [betTypeStats, setBetTypeStats] = useState<BetTypeStats | null>(null);
  const [dailyBudget, setDailyBudget] = useState(5000);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 設定を取得
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await fetch('/api/bankroll/config');
        if (res.ok) {
          const data = await res.json();
          const totalBankroll = data.settings?.total_bankroll || 100000;
          const dailyLimitPercent = data.settings?.daily_limit_percent || 5;
          setDailyBudget(Math.floor(totalBankroll * (dailyLimitPercent / 100)));
        }
      } catch (error) {
        console.error('設定取得エラー:', error);
      }
    };
    fetchConfig();
  }, []);

  // 月間サマリーと統計を取得
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        // 月間サマリー
        const summaryRes = await fetch(
          `/api/bankroll/summary?year=${selectedYear}&month=${selectedMonth}`
        );
        if (!summaryRes.ok) {
          throw new Error('月間サマリーの取得に失敗しました');
        }
        const summaryData = await summaryRes.json();
        setMonthlySummary(summaryData);

        // 馬券種別統計
        const statsRes = await fetch(
          `/api/bankroll/stats?year=${selectedYear}&month=${selectedMonth}`
        );
        if (!statsRes.ok) {
          throw new Error('馬券種別統計の取得に失敗しました');
        }
        const statsData = await statsRes.json();
        setBetTypeStats(statsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'データの取得に失敗しました');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedYear, selectedMonth]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
    }).format(amount);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  const getRecoveryRateColor = (rate: number) => {
    if (rate >= 100) return 'text-green-600 dark:text-green-400';
    if (rate >= 80) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getProfitColor = (profit: number) => {
    if (profit > 0) return 'text-green-600 dark:text-green-400';
    if (profit < 0) return 'text-red-600 dark:text-red-400';
    return 'text-muted-foreground';
  };

  if (loading) {
    return (
      <div className="container py-6 max-w-6xl">
        <div className="text-center py-12">
          <p className="text-muted-foreground">データを読み込み中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container py-6 max-w-6xl">
        <Card className="border-red-200 dark:border-red-800">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <AlertCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container py-6 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          💰 収支管理 (TARGET連携)
        </h1>
        <Badge variant="outline" className="text-sm">
          同期: 自動
        </Badge>
      </div>

      {/* アラートバー */}
      <AlertBar />

      {/* 年月選択 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">期間選択</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">年:</label>
              <select
                value={selectedYear}
                onChange={(e) => setSelectedYear(parseInt(e.target.value))}
                className="rounded-md border bg-background px-3 py-1.5 text-sm"
              >
                {Array.from({ length: 5 }, (_, i) => currentYear - i).map((year) => (
                  <option key={year} value={year}>
                    {year}年
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">月:</label>
              <select
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(parseInt(e.target.value))}
                className="rounded-md border bg-background px-3 py-1.5 text-sm"
              >
                {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => (
                  <option key={month} value={month}>
                    {month}月
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 月間収支サマリー */}
      {monthlySummary && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-xl">
              【{selectedYear}年{selectedMonth}月の収支】
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!monthlySummary.file_exists ? (
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  TARGETデータファイルが見つかりません
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  PD{selectedYear}{String(selectedMonth).padStart(2, '0')}.CSV が存在しません
                </p>
              </div>
            ) : !monthlySummary.has_data ? (
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  データがありません
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  この月の買い目データが登録されていません
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">購入計</div>
                    <div className="text-2xl font-bold">
                      {formatCurrency(monthlySummary.total_bet)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">払戻計</div>
                    <div className="text-2xl font-bold">
                      {formatCurrency(monthlySummary.total_payout)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">収支</div>
                    <div
                      className={`text-2xl font-bold flex items-center gap-1 ${getProfitColor(
                        monthlySummary.profit
                      )}`}
                    >
                      {monthlySummary.profit >= 0 ? (
                        <TrendingUp className="h-5 w-5" />
                      ) : (
                        <TrendingDown className="h-5 w-5" />
                      )}
                      {formatCurrency(monthlySummary.profit)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">回収率</div>
                    <div
                      className={`text-2xl font-bold ${getRecoveryRateColor(
                        monthlySummary.recovery_rate
                      )}`}
                    >
                      {formatPercent(monthlySummary.recovery_rate)}
                    </div>
                  </div>
                </div>
                <div className="mt-4 text-sm text-muted-foreground">
                  レース数: {monthlySummary.race_count}レース
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* 予算設定フォーム */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <BudgetForm />
        <AllocationGuide year={selectedYear} month={selectedMonth} />
      </div>

      {/* 購入管理セクション */}
      <div className="mb-6">
        <PurchasePlanSection dailyBudget={dailyBudget} />
      </div>

      {/* 馬券種別回収率 */}
      {betTypeStats && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">【馬券種別回収率】</CardTitle>
          </CardHeader>
          <CardContent>
            {betTypeStats._meta && !betTypeStats._meta.file_exists ? (
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  TARGETデータファイルが見つかりません
                </p>
              </div>
            ) : betTypeStats._meta && !betTypeStats._meta.has_data ? (
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  データがありません
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {Object.entries(betTypeStats)
                  .filter(([key]) => key !== '_meta')
                  .sort(([, a], [, b]) => b.recovery_rate - a.recovery_rate)
                  .map(([betType, stats]) => (
                    <div key={betType} className="flex items-center justify-between p-3 border rounded-lg">
                      <div className="flex items-center gap-3">
                        <span className="font-medium min-w-[80px]">{betType}</span>
                        <Badge
                          variant={
                            stats.recovery_rate >= 100
                              ? 'default'
                              : stats.recovery_rate >= 80
                                ? 'secondary'
                                : 'destructive'
                          }
                          className="text-xs"
                        >
                          {stats.count}件
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <div
                            className={`text-lg font-bold ${getRecoveryRateColor(
                              stats.recovery_rate
                            )}`}
                          >
                            {formatPercent(stats.recovery_rate)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            的中率: {formatPercent(stats.win_rate)}
                          </div>
                        </div>
                        {stats.recovery_rate < 50 && (
                          <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            )}
            {betTypeStats._meta && betTypeStats._meta.has_data && Object.keys(betTypeStats).filter(key => key !== '_meta').length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                データがありません
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
