'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Calculator, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface FundData {
  current_balance: number;
  config: {
    initial_balance: number;
  };
}

const BET_PCTS = [
  { pct: 1, label: '1%', desc: '保守的' },
  { pct: 2, label: '2%', desc: '推奨' },
  { pct: 3, label: '3%', desc: '積極的' },
];

const roundTo100 = (n: number) => Math.max(100, Math.floor(n / 100) * 100);

const formatCurrency = (amount: number): string =>
  new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 }).format(amount);

export function NextBetCalculator() {
  const [fundBalance, setFundBalance] = useState<number | null>(null);
  const [todayPnl, setTodayPnl] = useState<string>('');
  const [loading, setLoading] = useState(true);

  const fetchFund = useCallback(async () => {
    try {
      const res = await fetch('/api/bankroll/fund');
      if (!res.ok) return;
      const data: FundData = await res.json();
      setFundBalance(data.current_balance);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFund();
  }, [fetchFund]);

  // localStorage で当日仮収支を保持
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    const saved = localStorage.getItem(`nextbet_pnl_${today}`);
    if (saved) setTodayPnl(saved);
  }, []);

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    if (todayPnl !== '') {
      localStorage.setItem(`nextbet_pnl_${today}`, todayPnl);
    }
  }, [todayPnl]);

  if (loading || fundBalance == null) {
    return (
      <Card className="mb-6 border-blue-200 dark:border-blue-800">
        <CardContent className="py-4">
          <p className="text-muted-foreground text-sm">残高を読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  const pnlValue = parseInt(todayPnl) || 0;
  const adjustedBalance = fundBalance + pnlValue;

  return (
    <Card className="mb-6 border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-950/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Calculator className="h-5 w-5 text-blue-600" />
          次のベット額
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* 残高情報 */}
        <div className="flex items-center gap-6 mb-4">
          <div>
            <div className="text-xs text-muted-foreground">現在資金</div>
            <div className="text-xl font-bold">{formatCurrency(fundBalance)}</div>
          </div>

          <div className="flex items-center gap-2">
            <Minus className="h-4 w-4 text-muted-foreground" />
            <div>
              <div className="text-xs text-muted-foreground">当日仮収支</div>
              <Input
                type="number"
                value={todayPnl}
                onChange={(e) => setTodayPnl(e.target.value)}
                placeholder="0"
                className="w-28 h-8 text-right text-sm font-bold"
              />
            </div>
          </div>

          {pnlValue !== 0 && (
            <>
              <div className="text-muted-foreground">=</div>
              <div>
                <div className="text-xs text-muted-foreground">調整後資金</div>
                <div className={`text-xl font-bold ${pnlValue >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(adjustedBalance)}
                </div>
              </div>
            </>
          )}
        </div>

        {/* ベット額テーブル */}
        <div className="grid grid-cols-3 gap-3">
          {BET_PCTS.map(({ pct, label, desc }) => {
            const betAmount = roundTo100(adjustedBalance * pct / 100);
            const isRecommended = pct === 2;
            return (
              <div
                key={pct}
                className={`text-center p-3 rounded-lg border ${
                  isRecommended
                    ? 'border-blue-400 bg-blue-100/50 dark:bg-blue-900/30'
                    : 'border-muted bg-muted/20'
                }`}
              >
                <div className="flex items-center justify-center gap-1 mb-1">
                  <span className="text-sm font-medium">{label}</span>
                  {isRecommended && (
                    <Badge variant="default" className="text-[10px] px-1 py-0 bg-blue-500">推奨</Badge>
                  )}
                </div>
                <div className={`text-2xl font-bold ${isRecommended ? 'text-blue-600 dark:text-blue-400' : ''}`}>
                  ¥{betAmount.toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">{desc}</div>
              </div>
            );
          })}
        </div>

        <p className="text-xs text-muted-foreground mt-3">
          Intersection Filter（rank_w=1, gap≥4, EV≥1.3）での単勝ベット額。100円単位切り捨て。
        </p>
      </CardContent>
    </Card>
  );
}
