'use client';

import React, { useState, useEffect } from 'react';
import { Wallet, AlertTriangle } from 'lucide-react';

export function RemainingBudget() {
  const [remaining, setRemaining] = useState<number | null>(null);
  const [dailyLimit, setDailyLimit] = useState<number | null>(null);
  const [raceLimit, setRaceLimit] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBudget = async () => {
      try {
        const res = await fetch('/api/bankroll/alerts');
        if (res.ok) {
          const data = await res.json();
          setRemaining(data.remaining || 0);
          setDailyLimit(data.dailyLimit || 0);
          setRaceLimit(data.raceLimit || 0);
        }
      } catch (error) {
        console.error('予算取得エラー:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchBudget();
    const interval = setInterval(fetchBudget, 30000); // 30秒ごとに更新

    return () => clearInterval(interval);
  }, []);

  if (loading || remaining === null) {
    return null;
  }

  const formatCurrency = (amount: number) => {
    return `¥${amount.toLocaleString()}`;
  };

  const isLow = remaining < (raceLimit || 0);
  const percentage = dailyLimit ? Math.floor((remaining / dailyLimit) * 100) : 0;
  const isWarning = percentage < 30 && percentage >= 0;

  // 状態に応じた背景色とテキスト色
  const getBgClass = () => {
    if (isLow) return 'bg-red-100 dark:bg-red-900/40 border-red-300 dark:border-red-700';
    if (isWarning) return 'bg-amber-50 dark:bg-amber-900/30 border-amber-300 dark:border-amber-700';
    return 'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-300 dark:border-emerald-700';
  };

  const getTextClass = () => {
    if (isLow) return 'text-red-700 dark:text-red-300';
    if (isWarning) return 'text-amber-700 dark:text-amber-300';
    return 'text-emerald-700 dark:text-emerald-300';
  };

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${getBgClass()}`}>
      <Wallet className={`h-4 w-4 ${getTextClass()}`} />
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground font-medium hidden sm:inline">
          残り予算
        </span>
        <span className={`text-base font-bold tabular-nums ${getTextClass()}`}>
          {formatCurrency(remaining)}
        </span>
      </div>
      {isLow && (
        <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400 animate-pulse" />
      )}
    </div>
  );
}
