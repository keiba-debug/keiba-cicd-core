'use client';

import { useCallback } from 'react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface DateTabsProps {
  defaultValue: string;
  dates: string[];
  children: React.ReactNode;
}

// 曜日・色はクライアント側で算出（Server→Client間で関数は渡せないため）
function getDayOfWeek(dateStr: string): string {
  const date = new Date(dateStr);
  return ['日', '月', '火', '水', '木', '金', '土'][date.getDay()];
}

function getDayColorClass(dateStr: string): string {
  const day = new Date(dateStr).getDay();
  if (day === 0) return 'text-red-500';
  if (day === 6) return 'text-blue-500';
  return 'text-muted-foreground';
}

/**
 * 日付タブ — タブ切替時にURLの?dateパラメータを更新（リロードなし）
 */
export function DateTabs({ defaultValue, dates, children }: DateTabsProps) {
  const handleValueChange = useCallback((value: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set('date', value);
    window.history.replaceState({}, '', url.toString());
  }, []);

  return (
    <Tabs defaultValue={defaultValue} onValueChange={handleValueChange} className="w-full">
      <TabsList className="mb-6 flex-wrap h-auto gap-2 bg-transparent p-0 justify-start">
        {dates.map((date) => {
          const [, , day] = date.split('-');
          return (
            <TabsTrigger
              key={date}
              value={date}
              className="px-5 py-2.5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md border bg-background hover:bg-muted/50 transition-all flex flex-col items-center min-w-[4.5rem]"
            >
              <span className="text-lg font-bold leading-none">
                {parseInt(day)}
              </span>
              <span className={`text-xs font-bold mt-1 ${getDayColorClass(date)} group-data-[state=active]:text-primary-foreground/90`}>
                {getDayOfWeek(date)}曜
              </span>
            </TabsTrigger>
          );
        })}
      </TabsList>
      {children}
    </Tabs>
  );
}
