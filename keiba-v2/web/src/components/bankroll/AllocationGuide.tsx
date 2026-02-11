'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react';

interface AllocationItem {
  betType: string;
  percentage: number;
  recoveryRate: number;
  recommendation: string;
  stats: {
    total_bet: number;
    total_payout: number;
    count: number;
    win_count: number;
    recovery_rate: number;
    win_rate: number;
  };
}

export function AllocationGuide({ year, month }: { year: number; month: number }) {
  const [allocation, setAllocation] = useState<AllocationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasData, setHasData] = useState<boolean | null>(null);
  const [fileExists, setFileExists] = useState<boolean | null>(null);

  useEffect(() => {
    const fetchAllocation = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/bankroll/allocation?year=${year}&month=${month}`);
        if (res.ok) {
          const data = await res.json();
          setAllocation(data.allocation || []);
          setHasData(data.has_data ?? null);
          setFileExists(data.file_exists ?? null);
        }
      } catch (error) {
        console.error('資金配分取得エラー:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAllocation();
  }, [year, month]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">【推奨配分】（過去実績ベース）</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  if (!allocation || allocation.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">【推奨配分】（過去実績ベース）</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            {fileExists === false ? (
              <>
                <p className="text-muted-foreground">
                  TARGETデータファイルが見つかりません
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  PD{year}{String(month).padStart(2, '0')}.CSV が存在しません
                </p>
              </>
            ) : (
              <>
                <p className="text-muted-foreground">
                  データがありません
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  過去実績データがないため、推奨配分を計算できません
                </p>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  const getRecommendationIcon = (recommendation: string) => {
    switch (recommendation) {
      case '好調':
        return <TrendingUp className="h-4 w-4 text-green-600 dark:text-green-400" />;
      case '控えめ':
        return <TrendingDown className="h-4 w-4 text-red-600 dark:text-red-400" />;
      default:
        return <Minus className="h-4 w-4 text-gray-600 dark:text-gray-400" />;
    }
  };

  const getRecommendationColor = (recommendation: string) => {
    switch (recommendation) {
      case '好調':
        return 'text-green-600 dark:text-green-400';
      case '安定':
        return 'text-blue-600 dark:text-blue-400';
      case '控えめ':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">【推奨配分】（過去実績ベース）</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {allocation.map((item) => (
            <div
              key={item.betType}
              className="flex items-center justify-between p-3 border rounded-lg"
            >
              <div className="flex items-center gap-3">
                <span className="font-medium min-w-[80px]">{item.betType}:</span>
                <span className="text-lg font-bold">{item.percentage}%</span>
                {getRecommendationIcon(item.recommendation)}
                <Badge
                  variant={
                    item.recommendation === '好調'
                      ? 'default'
                      : item.recommendation === '控えめ'
                        ? 'destructive'
                        : 'secondary'
                  }
                  className="text-xs"
                >
                  {item.recommendation}
                </Badge>
              </div>
              <div className="text-right">
                <div className={`text-sm font-medium ${getRecommendationColor(item.recommendation)}`}>
                  回収率{item.recoveryRate.toFixed(1)}%
                </div>
                <div className="text-xs text-muted-foreground">
                  {item.recommendation === '好調'
                    ? '← 回収率が高く好調'
                    : item.recommendation === '控えめ'
                      ? '← 回収率が低いため控えめに'
                      : '← 回収率が安定'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
