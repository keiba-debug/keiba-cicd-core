'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertCircle, CheckCircle, X } from 'lucide-react';

interface BetCheckResult {
  canBet: boolean;
  warnings: string[];
  errors: string[];
  limits: {
    dailyLimit: number;
    raceLimit: number;
    remaining: number;
    todaySpent: number;
  };
  betTypeStats: {
    recovery_rate: number;
    win_rate: number;
  } | null;
}

interface BetCheckDialogProps {
  betType: string;
  amount: number;
  selection: string;
  onConfirm: () => void;
  onCancel: () => void;
  onAmountChange: (amount: number) => void;
}

export function BetCheckDialog({
  betType,
  amount,
  selection,
  onConfirm,
  onCancel,
  onAmountChange,
}: BetCheckDialogProps) {
  const [checkResult, setCheckResult] = useState<BetCheckResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkBet = async () => {
      setLoading(true);
      try {
        const res = await fetch('/api/bankroll/check', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ betType, amount }),
        });

        if (res.ok) {
          const data = await res.json();
          setCheckResult(data);
        }
      } catch (error) {
        console.error('チェックエラー:', error);
      } finally {
        setLoading(false);
      }
    };

    checkBet();
  }, [betType, amount]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
    }).format(amount);
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground">チェック中...</p>
        </CardContent>
      </Card>
    );
  }

  if (!checkResult) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-red-600 dark:text-red-400">
            チェック処理に失敗しました
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center justify-between">
          <span>購入確認</span>
          <button
            onClick={onCancel}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 購入内容 */}
        <div className="p-3 bg-muted rounded-lg">
          <div className="font-medium">
            {betType} {selection}
          </div>
          <div className="text-2xl font-bold mt-1">{formatCurrency(amount)}</div>
        </div>

        {/* エラー */}
        {checkResult.errors.length > 0 && (
          <div className="space-y-2">
            {checkResult.errors.map((error, index) => (
              <div
                key={index}
                className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg"
              >
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-red-700 dark:text-red-400">{error}</span>
              </div>
            ))}
          </div>
        )}

        {/* 警告 */}
        {checkResult.warnings.length > 0 && (
          <div className="space-y-2">
            {checkResult.warnings.map((warning, index) => (
              <div
                key={index}
                className="flex items-start gap-2 p-3 bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 rounded-lg"
              >
                <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-yellow-700 dark:text-yellow-400">
                  {warning}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* 馬券種別統計 */}
        {checkResult.betTypeStats && (
          <div className="p-3 bg-muted rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">過去実績</div>
            <div className="flex items-center justify-between">
              <span className="text-sm">回収率</span>
              <span className="font-medium">
                {checkResult.betTypeStats.recovery_rate.toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-sm">的中率</span>
              <span className="font-medium">
                {checkResult.betTypeStats.win_rate.toFixed(1)}%
              </span>
            </div>
          </div>
        )}

        {/* 残り予算 */}
        <div className="p-3 bg-muted rounded-lg">
          <div className="text-sm text-muted-foreground mb-1">残り予算</div>
          <div className="text-xl font-bold">
            {formatCurrency(checkResult.limits.remaining)}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            本日使用: {formatCurrency(checkResult.limits.todaySpent)} /{' '}
            {formatCurrency(checkResult.limits.dailyLimit)}
          </div>
        </div>

        {/* アクションボタン */}
        <div className="flex gap-2 pt-2">
          {checkResult.canBet ? (
            <>
              <Button onClick={onConfirm} className="flex-1">
                <CheckCircle className="h-4 w-4 mr-2" />
                購入する
              </Button>
              <Button onClick={onCancel} variant="outline" className="flex-1">
                中止
              </Button>
            </>
          ) : (
            <>
              <Button
                onClick={() => {
                  const newAmount = Math.min(
                    amount,
                    checkResult.limits.raceLimit,
                    checkResult.limits.remaining
                  );
                  onAmountChange(newAmount);
                }}
                variant="outline"
                className="flex-1"
              >
                金額を変更
              </Button>
              <Button onClick={onCancel} variant="outline" className="flex-1">
                中止
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
