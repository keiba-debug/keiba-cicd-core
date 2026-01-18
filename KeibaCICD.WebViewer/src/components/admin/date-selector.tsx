'use client';

import React from 'react';
import { Button } from '@/components/ui/button';

interface DateSelectorProps {
  date: string; // YYYY-MM-DD形式
  onChange: (date: string) => void;
  disabled?: boolean;
}

export function DateSelector({ date, onChange, disabled = false }: DateSelectorProps) {
  const handleTodayClick = () => {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    onChange(`${yyyy}-${mm}-${dd}`);
  };

  const handleTomorrowClick = () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const yyyy = tomorrow.getFullYear();
    const mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
    const dd = String(tomorrow.getDate()).padStart(2, '0');
    onChange(`${yyyy}-${mm}-${dd}`);
  };

  const formatDisplayDate = (dateStr: string) => {
    if (!dateStr) return '';
    const [year, month, day] = dateStr.split('-');
    const d = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
    const weekday = weekdays[d.getDay()];
    return `${year}年${parseInt(month)}月${parseInt(day)}日（${weekday}）`;
  };

  return (
    <div className="space-y-3">
      <label className="text-base font-semibold flex items-center gap-2">
        📅 対象日付
      </label>
      <div className="flex items-center gap-3 flex-wrap">
        <input
          type="date"
          value={date}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="w-48 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
        />
        <Button
          variant="outline"
          size="sm"
          onClick={handleTodayClick}
          disabled={disabled}
        >
          今日
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleTomorrowClick}
          disabled={disabled}
        >
          明日
        </Button>
        <span className="text-muted-foreground text-sm ml-2">
          {formatDisplayDate(date)}
        </span>
      </div>
    </div>
  );
}
