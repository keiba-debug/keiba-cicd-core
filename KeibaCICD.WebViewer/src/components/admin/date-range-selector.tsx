'use client';

import React from 'react';
import { Button } from '@/components/ui/button';

interface DateRangeSelectorProps {
  startDate: string; // YYYY-MM-DD形式
  endDate: string;   // YYYY-MM-DD形式
  onStartDateChange: (date: string) => void;
  onEndDateChange: (date: string) => void;
  disabled?: boolean;
  label?: string;
}

export function DateRangeSelector({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  disabled = false,
  label = '📅 対象期間',
}: DateRangeSelectorProps) {
  
  const formatDate = (offset: number): string => {
    const d = new Date();
    d.setDate(d.getDate() + offset);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  // 先週のレース（土日）
  const handleLastWeekend = () => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    
    // 先週の土曜日
    const lastSaturday = new Date(today);
    lastSaturday.setDate(today.getDate() - dayOfWeek - 1); // 直前の土曜日
    if (dayOfWeek === 0) lastSaturday.setDate(lastSaturday.getDate() - 7); // 今日が日曜なら先週
    if (dayOfWeek === 6) lastSaturday.setDate(lastSaturday.getDate() - 7); // 今日が土曜なら先週
    
    // 先週の日曜日
    const lastSunday = new Date(lastSaturday);
    lastSunday.setDate(lastSaturday.getDate() + 1);
    
    onStartDateChange(formatDateString(lastSaturday));
    onEndDateChange(formatDateString(lastSunday));
  };

  // 過去7日間
  const handleLast7Days = () => {
    onStartDateChange(formatDate(-7));
    onEndDateChange(formatDate(-1));
  };

  // 過去14日間
  const handleLast14Days = () => {
    onStartDateChange(formatDate(-14));
    onEndDateChange(formatDate(-1));
  };

  const formatDateString = (d: Date): string => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  const formatDisplayDate = (dateStr: string) => {
    if (!dateStr) return '';
    const [year, month, day] = dateStr.split('-');
    const d = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
    const weekday = weekdays[d.getDay()];
    return `${parseInt(month)}/${parseInt(day)}(${weekday})`;
  };

  const calculateDays = (): number => {
    if (!startDate || !endDate) return 0;
    const start = new Date(startDate);
    const end = new Date(endDate);
    const diff = end.getTime() - start.getTime();
    return Math.ceil(diff / (1000 * 60 * 60 * 24)) + 1;
  };

  return (
    <div className="space-y-3">
      <label className="text-base font-semibold flex items-center gap-2">
        {label}
      </label>
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            disabled={disabled}
            className="w-40 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
          <span className="text-muted-foreground">〜</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            disabled={disabled}
            className="w-40 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleLastWeekend}
            disabled={disabled}
          >
            先週末
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleLast7Days}
            disabled={disabled}
          >
            過去7日
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleLast14Days}
            disabled={disabled}
          >
            過去14日
          </Button>
        </div>
      </div>
      <div className="text-sm text-muted-foreground">
        {startDate && endDate && (
          <>
            {formatDisplayDate(startDate)} 〜 {formatDisplayDate(endDate)}
            <span className="ml-2 text-xs">（{calculateDays()}日間）</span>
          </>
        )}
      </div>
    </div>
  );
}
