'use client';

import { useRouter } from 'next/navigation';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getDayOfWeek } from '../lib/helpers';

interface DateNavProps {
  dates: string[];
  currentDate: string;
  isArchive: boolean;
}

/** YYYY-MM-DD → "2026年2月22日(日)" */
function formatDateDisplay(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dow = getDayOfWeek(dateStr);
  return `${y}年${m}月${d}日(${dow})`;
}

export function DateNav({ dates, currentDate, isArchive }: DateNavProps) {
  const router = useRouter();

  if (dates.length === 0) return null;

  // dates は新しい順 (dates[0] が最新)
  const currentIndex = isArchive ? dates.indexOf(currentDate) : -1;
  const isLatest = !isArchive || currentIndex === 0;
  const isOldest = isArchive && currentIndex >= dates.length - 1;

  const goToPrev = () => {
    if (!isArchive) {
      // "最新" 表示中 → 1つ前の開催日に
      if (dates.length >= 2) router.push(`/predictions?date=${dates[1]}`);
      return;
    }
    if (currentIndex < 0 || currentIndex >= dates.length - 1) return;
    router.push(`/predictions?date=${dates[currentIndex + 1]}`);
  };

  const goToNext = () => {
    if (!isArchive || currentIndex <= 0) {
      router.push('/predictions');
      return;
    }
    router.push(`/predictions?date=${dates[currentIndex - 1]}`);
  };

  const onSelectChange = (value: string) => {
    if (value === '__latest__') {
      router.push('/predictions');
    } else {
      router.push(`/predictions?date=${value}`);
    }
  };

  const displayValue = isArchive ? currentDate : '__latest__';

  return (
    <div className="flex items-center gap-2 mb-6">
      <Button
        variant="outline"
        size="icon"
        onClick={goToPrev}
        disabled={isArchive && isOldest}
        title="前の開催日"
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <div className="flex items-center gap-2">
        <Calendar className="h-5 w-5 text-muted-foreground" />
        <select
          value={displayValue}
          onChange={(e) => onSelectChange(e.target.value)}
          className="rounded-md border bg-background px-3 py-2 text-lg font-bold min-w-[220px]"
        >
          <option value="__latest__">最新</option>
          {dates.map(date => (
            <option key={date} value={date}>
              {formatDateDisplay(date)}
            </option>
          ))}
        </select>
      </div>
      <Button
        variant="outline"
        size="icon"
        onClick={goToNext}
        disabled={isLatest}
        title="次の開催日"
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}
