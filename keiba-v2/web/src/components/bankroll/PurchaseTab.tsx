'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TodaySummary } from '@/components/bankroll/TodaySummary';
import { DailyPurchaseList } from '@/components/bankroll/DailyPurchaseList';

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

interface PurchaseTabProps {
  refreshKey: number;
}

export function PurchaseTab({ refreshKey }: PurchaseTabProps) {
  const today = new Date();

  const [raceDates, setRaceDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState('');

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

  return (
    <div className="space-y-6">
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
    </div>
  );
}
