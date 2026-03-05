'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  TrendingUp,
  TrendingDown,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Calendar,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TodaySummary } from '@/components/bankroll/TodaySummary';
import { DailyPurchaseList } from '@/components/bankroll/DailyPurchaseList';
import { BetTypeStats } from '@/components/bankroll/BetTypeStats';
import { FundManagement } from '@/components/bankroll/FundManagement';
import { NextBetCalculator } from '@/components/bankroll/NextBetCalculator';
import { WinningCollection } from '@/components/bankroll/WinningCollection';

interface MonthlySummary {
  year: number;
  month: number;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  race_count: number;
  has_data?: boolean;
  file_exists?: boolean;
}

const formatDateToStr = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}${m}${d}`;
};

const formatDateDisplay = (dateStr: string): string => {
  const year = parseInt(dateStr.slice(0, 4));
  const month = parseInt(dateStr.slice(4, 6));
  const day = parseInt(dateStr.slice(6, 8));
  const date = new Date(year, month - 1, day);
  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  const weekday = weekdays[date.getDay()];
  return `${year}年${month}月${day}日(${weekday})`;
};

interface FundTabProps {
  refreshKey: number;
}

export function FundTab({ refreshKey }: FundTabProps) {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1;

  const [raceDates, setRaceDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [selectedMonth, setSelectedMonth] = useState(currentMonth);
  const [monthlySummary, setMonthlySummary] = useState<MonthlySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRaceDates = useCallback(async () => {
    try {
      const res = await fetch('/api/race-dates');
      if (!res.ok) return;
      const { dates } = await res.json();
      const yyyymmdd = (dates as string[]).map((d) => d.replace(/-/g, ''));
      setRaceDates(yyyymmdd);
      if (yyyymmdd.length > 0) {
        const todayStr = formatDateToStr(today);
        const defaultDate = yyyymmdd.find(d => d <= todayStr) || yyyymmdd[0];
        setSelectedDate((prev) => prev || defaultDate);
      } else {
        setSelectedDate(formatDateToStr(today));
      }
    } catch {
      setSelectedDate(formatDateToStr(today));
    }
  }, []);

  useEffect(() => {
    loadRaceDates();
  }, [loadRaceDates]);

  const currentIndex = raceDates.indexOf(selectedDate);

  const goToPrevDay = () => {
    if (raceDates.length === 0) return;
    if (currentIndex < 0) { setSelectedDate(raceDates[0]); return; }
    if (currentIndex >= raceDates.length - 1) return;
    setSelectedDate(raceDates[currentIndex + 1]);
  };

  const goToNextDay = () => {
    if (raceDates.length === 0) return;
    if (currentIndex < 0) { setSelectedDate(raceDates[0]); return; }
    if (currentIndex <= 0) return;
    setSelectedDate(raceDates[currentIndex - 1]);
  };

  const goToLatest = () => {
    if (raceDates.length > 0) setSelectedDate(raceDates[0]);
  };

  const isLatest = raceDates.length > 0 && selectedDate === raceDates[0];
  const isOldest = raceDates.length > 0 && currentIndex >= raceDates.length - 1;

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const summaryRes = await fetch(
          `/api/bankroll/summary?year=${selectedYear}&month=${selectedMonth}`
        );
        if (!summaryRes.ok) throw new Error('月間サマリーの取得に失敗しました');
        const summaryData = await summaryRes.json();
        setMonthlySummary(summaryData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'データの取得に失敗しました');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [selectedYear, selectedMonth]);

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY' }).format(amount);

  const formatPercent = (value: number) => `${value.toFixed(1)}%`;

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

  return (
    <div className="space-y-6">
      {/* 次のベット額計算 */}
      <NextBetCalculator />

      {/* 資金管理 */}
      <FundManagement />

      {/* 開催日選択 */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon" onClick={goToPrevDay}
                disabled={raceDates.length === 0 || isOldest} title="前の開催日">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-muted-foreground" />
                <select value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="rounded-md border bg-background px-3 py-2 text-lg font-bold min-w-[200px]"
                  disabled={raceDates.length === 0}>
                  {raceDates.length === 0 && selectedDate && (
                    <option value={selectedDate}>{formatDateDisplay(selectedDate)}</option>
                  )}
                  {raceDates.map((d) => (
                    <option key={d} value={d}>{formatDateDisplay(d)}</option>
                  ))}
                </select>
              </div>
              <Button variant="outline" size="icon" onClick={goToNextDay}
                disabled={raceDates.length === 0 || isLatest} title="次の開催日">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            {!isLatest && raceDates.length > 0 && (
              <Button variant="ghost" size="sm" onClick={goToLatest}>最新の開催日へ</Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 選択日の成績 */}
      <TodaySummary dateStr={selectedDate} refreshKey={refreshKey} />

      {/* 選択日の購入リスト */}
      <DailyPurchaseList dateStr={selectedDate} refreshKey={refreshKey} />

      {/* 年月選択 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">期間選択（月間収支）</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">年:</label>
              <select value={selectedYear}
                onChange={(e) => setSelectedYear(parseInt(e.target.value))}
                className="rounded-md border bg-background px-3 py-1.5 text-sm">
                {Array.from({ length: 5 }, (_, i) => currentYear - i).map((year) => (
                  <option key={year} value={year}>{year}年</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">月:</label>
              <select value={selectedMonth}
                onChange={(e) => setSelectedMonth(parseInt(e.target.value))}
                className="rounded-md border bg-background px-3 py-1.5 text-sm">
                {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => (
                  <option key={month} value={month}>{month}月</option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 月間収支サマリー */}
      {loading ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-center">データを読み込み中...</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card className="border-red-200 dark:border-red-800">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <AlertCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </CardContent>
        </Card>
      ) : monthlySummary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">
              【{selectedYear}年{selectedMonth}月の収支】
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!monthlySummary.file_exists ? (
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">TARGETデータファイルが見つかりません</p>
                <p className="text-sm text-muted-foreground mt-2">
                  PD{selectedYear}{String(selectedMonth).padStart(2, '0')}.CSV が存在しません
                </p>
              </div>
            ) : !monthlySummary.has_data ? (
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">データがありません</p>
                <p className="text-sm text-muted-foreground mt-2">
                  この月の買い目データが登録されていません
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">購入計</div>
                    <div className="text-2xl font-bold">{formatCurrency(monthlySummary.total_bet)}</div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">払戻計</div>
                    <div className="text-2xl font-bold">{formatCurrency(monthlySummary.total_payout)}</div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">収支</div>
                    <div className={`text-2xl font-bold flex items-center gap-1 ${getProfitColor(monthlySummary.profit)}`}>
                      {monthlySummary.profit >= 0 ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                      {formatCurrency(monthlySummary.profit)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground mb-1">回収率</div>
                    <div className={`text-2xl font-bold ${getRecoveryRateColor(monthlySummary.recovery_rate)}`}>
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

      {/* 馬券種別実績 */}
      <BetTypeStats />

      {/* 的中コレクション */}
      <WinningCollection />
    </div>
  );
}
