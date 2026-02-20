'use client';

import { useRouter } from 'next/navigation';
import { getDayOfWeek, getDayColor } from '../lib/helpers';

interface DateNavProps {
  dates: string[];
  currentDate: string;
  isArchive: boolean;
}

export function DateNav({ dates, currentDate, isArchive }: DateNavProps) {
  const router = useRouter();

  if (dates.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 items-center mb-6">
      <button
        onClick={() => router.push('/predictions')}
        className={`px-3 py-2 rounded border text-sm transition-colors ${
          !isArchive
            ? 'bg-primary text-primary-foreground shadow-md'
            : 'bg-background hover:bg-muted/50'
        }`}
      >
        最新
      </button>
      <span className="text-muted-foreground text-xs mx-1">|</span>
      {dates.map(date => {
        const [, , day] = date.split('-');
        const isActive = isArchive && date === currentDate;
        return (
          <button
            key={date}
            onClick={() => router.push(`/predictions?date=${date}`)}
            className={`px-3 py-2 rounded border text-sm transition-colors flex flex-col items-center min-w-[3.5rem] ${
              isActive
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'bg-background hover:bg-muted/50'
            }`}
          >
            <span className="font-bold leading-none">{parseInt(day)}</span>
            <span className={`text-[10px] mt-0.5 ${isActive ? 'text-primary-foreground/80' : getDayColor(date)}`}>
              {getDayOfWeek(date)}
            </span>
          </button>
        );
      })}
    </div>
  );
}
