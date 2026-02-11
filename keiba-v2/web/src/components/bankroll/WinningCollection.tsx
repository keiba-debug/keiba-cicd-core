'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Trophy, Star, Target, Zap } from 'lucide-react';

interface WinningTicket {
  id: string;
  date: string;
  venue: string;
  race_number: number;
  race_name: string;
  bet_type: string;
  selection: string;
  amount: number;
  payout: number;
  odds: number;
  profit: number;
}

interface CollectionStats {
  total_wins: number;
  total_profit: number;
  total_payout: number;
  highest_payout: WinningTicket | null;
  highest_odds: WinningTicket | null;
  manba_count: number;
  high_payout_count: number;
}

interface CollectionData {
  tickets: WinningTicket[];
  stats: CollectionStats;
  recent: WinningTicket[];
}

// 日付を表示用にフォーマット
const formatDate = (dateStr: string): string => {
  if (!dateStr || dateStr.length !== 8) return dateStr;
  const month = parseInt(dateStr.slice(4, 6));
  const day = parseInt(dateStr.slice(6, 8));
  return `${month}/${day}`;
};

// 金額をフォーマット
const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: 0,
  }).format(amount);
};

export function WinningCollection() {
  const [data, setData] = useState<CollectionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch('/api/bankroll/collection');
        if (!res.ok) throw new Error('データの取得に失敗しました');
        const result = await res.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'エラーが発生しました');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Trophy className="h-5 w-5 text-yellow-500" />
            【的中コレクション】
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Trophy className="h-5 w-5 text-yellow-500" />
            【的中コレクション】
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">データがありません</p>
        </CardContent>
      </Card>
    );
  }

  const { stats, recent } = data;

  return (
    <Card className="mb-6 border-2 border-yellow-200 dark:border-yellow-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Trophy className="h-5 w-5 text-yellow-500" />
          【的中コレクション】
          <Badge variant="secondary" className="ml-2">
            直近6ヶ月
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* 統計サマリー */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="text-center p-3 bg-gradient-to-br from-yellow-50 to-yellow-100 dark:from-yellow-900/20 dark:to-yellow-800/20 rounded-lg">
            <Target className="h-5 w-5 mx-auto mb-1 text-yellow-600" />
            <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-400">{stats.total_wins}</div>
            <div className="text-xs text-muted-foreground">的中数</div>
          </div>
          <div className="text-center p-3 bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 rounded-lg">
            <div className="text-xl font-bold text-green-600">
              +{formatCurrency(stats.total_profit)}
            </div>
            <div className="text-xs text-muted-foreground">総利益</div>
          </div>
          <div className="text-center p-3 bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 rounded-lg">
            <Zap className="h-5 w-5 mx-auto mb-1 text-purple-600" />
            <div className="text-2xl font-bold text-purple-700 dark:text-purple-400">{stats.manba_count}</div>
            <div className="text-xs text-muted-foreground">万馬券</div>
          </div>
          <div className="text-center p-3 bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20 rounded-lg">
            <div className="text-xl font-bold text-orange-600">{stats.high_payout_count}</div>
            <div className="text-xs text-muted-foreground">高配当(50倍↑)</div>
          </div>
        </div>

        {/* ハイライト */}
        {(stats.highest_payout || stats.highest_odds) && (
          <div className="grid md:grid-cols-2 gap-3 mb-4">
            {stats.highest_payout && (
              <div className="p-3 border rounded-lg bg-gradient-to-r from-yellow-50 to-transparent dark:from-yellow-900/10">
                <div className="flex items-center gap-2 mb-1">
                  <Star className="h-4 w-4 text-yellow-500" />
                  <span className="text-sm font-medium">最高払戻</span>
                </div>
                <div className="text-xl font-bold text-green-600">
                  {formatCurrency(stats.highest_payout.payout)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate(stats.highest_payout.date)} {stats.highest_payout.venue}{stats.highest_payout.race_number}R {stats.highest_payout.bet_type}
                </div>
              </div>
            )}
            {stats.highest_odds && (
              <div className="p-3 border rounded-lg bg-gradient-to-r from-purple-50 to-transparent dark:from-purple-900/10">
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="h-4 w-4 text-purple-500" />
                  <span className="text-sm font-medium">最高オッズ</span>
                </div>
                <div className="text-xl font-bold text-purple-600">
                  {stats.highest_odds.odds.toFixed(1)}倍
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate(stats.highest_odds.date)} {stats.highest_odds.venue}{stats.highest_odds.race_number}R {stats.highest_odds.bet_type}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 直近の的中 */}
        {recent.length > 0 && (
          <div>
            <h3 className="text-sm font-medium mb-2">🎯 直近の的中</h3>
            <div className="space-y-2">
              {recent.slice(0, 5).map((ticket) => (
                <div 
                  key={ticket.id} 
                  className="flex items-center justify-between p-2 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      {ticket.bet_type}
                    </Badge>
                    <span className="text-sm font-medium">
                      {ticket.venue}{ticket.race_number}R
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {ticket.selection}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({formatDate(ticket.date)})
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground">
                      {ticket.odds.toFixed(1)}倍
                    </span>
                    <span className="font-bold text-green-600">
                      {formatCurrency(ticket.payout)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 的中がない場合 */}
        {stats.total_wins === 0 && (
          <div className="text-center py-6">
            <Trophy className="h-12 w-12 mx-auto mb-2 text-muted-foreground opacity-50" />
            <p className="text-muted-foreground">的中データがありません</p>
            <p className="text-sm text-muted-foreground">馬券を購入して的中すると、ここに表示されます</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
