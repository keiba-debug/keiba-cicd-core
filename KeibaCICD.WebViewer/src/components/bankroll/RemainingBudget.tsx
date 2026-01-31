'use client';

import React, { useState, useEffect } from 'react';
import { DollarSign, AlertCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

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
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
    }).format(amount);
  };

  const isLow = remaining < (raceLimit || 0);
  const percentage = dailyLimit ? Math.floor((remaining / dailyLimit) * 100) : 0;

  return (
    <div className="flex items-center gap-2">
      <DollarSign className="h-4 w-4 text-muted-foreground" />
      <span className="text-sm text-muted-foreground">残り予算:</span>
      <Badge
        variant={isLow ? 'destructive' : percentage < 20 ? 'secondary' : 'outline'}
        className="font-mono"
      >
        {formatCurrency(remaining)}
      </Badge>
      {isLow && (
        <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
      )}
    </div>
  );
}
