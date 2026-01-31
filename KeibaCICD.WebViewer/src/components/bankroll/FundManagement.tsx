'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { 
  Wallet, 
  TrendingUp, 
  TrendingDown, 
  Plus, 
  Minus, 
  History,
  RefreshCw,
} from 'lucide-react';
import { FundChart } from './FundChart';

interface FundEntry {
  id: string;
  date: string;
  type: 'deposit' | 'withdraw' | 'betting_result';
  amount: number;
  balance: number;
  description?: string;
}

interface ChartDataPoint {
  date: string;
  balance: number;
  profit: number;
}

interface PeriodSummary {
  period: string;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  race_count: number;
  win_count: number;
  total_change: number;
}

interface FundData {
  config: {
    initial_balance: number;
    created_at: string;
    updated_at: string;
  };
  entries: FundEntry[];
  current_balance: number;
  total_profit: number;
  chart_data: ChartDataPoint[];
  period_summaries: PeriodSummary[];
}

// 日付を表示用にフォーマット
const formatDate = (dateStr: string): string => {
  if (dateStr.length !== 8) return dateStr;
  const year = dateStr.slice(0, 4);
  const month = dateStr.slice(4, 6);
  const day = dateStr.slice(6, 8);
  return `${year}/${month}/${day}`;
};

// 金額をフォーマット
const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: 0,
  }).format(amount);
};

// エントリタイプの表示名
const getEntryTypeName = (type: string): string => {
  switch (type) {
    case 'deposit': return '入金';
    case 'withdraw': return '出金';
    case 'betting_result': return '競馬収支';
    default: return type;
  }
};

// エントリタイプのバッジカラー
const getEntryTypeBadge = (type: string) => {
  switch (type) {
    case 'deposit':
      return <Badge className="bg-blue-500">入金</Badge>;
    case 'withdraw':
      return <Badge className="bg-orange-500">出金</Badge>;
    case 'betting_result':
      return <Badge variant="outline">競馬</Badge>;
    default:
      return <Badge variant="secondary">{type}</Badge>;
  }
};

export function FundManagement() {
  const [data, setData] = useState<FundData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 入金/出金ダイアログ
  const [depositAmount, setDepositAmount] = useState('');
  const [depositDescription, setDepositDescription] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [withdrawDescription, setWithdrawDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // データを取得
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/bankroll/fund');
      if (!res.ok) throw new Error('資金データの取得に失敗しました');
      const result = await res.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'エラーが発生しました');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 入金処理
  const handleDeposit = async () => {
    const amount = parseInt(depositAmount);
    if (isNaN(amount) || amount <= 0) {
      alert('有効な金額を入力してください');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch('/api/bankroll/fund', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'deposit',
          amount,
          description: depositDescription || '入金',
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '入金に失敗しました');
      }

      setDepositAmount('');
      setDepositDescription('');
      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'エラーが発生しました');
    } finally {
      setSubmitting(false);
    }
  };

  // 出金処理
  const handleWithdraw = async () => {
    const amount = parseInt(withdrawAmount);
    if (isNaN(amount) || amount <= 0) {
      alert('有効な金額を入力してください');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch('/api/bankroll/fund', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'withdraw',
          amount,
          description: withdrawDescription || '出金',
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '出金に失敗しました');
      }

      setWithdrawAmount('');
      setWithdrawDescription('');
      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'エラーが発生しました');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Wallet className="h-5 w-5" />
            【資金管理】
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
      <Card className="mb-6 border-red-200">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Wallet className="h-5 w-5" />
            【資金管理】
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-red-600">{error || 'データの取得に失敗しました'}</p>
          <Button variant="outline" size="sm" onClick={fetchData} className="mt-2">
            <RefreshCw className="h-4 w-4 mr-2" />
            再読み込み
          </Button>
        </CardContent>
      </Card>
    );
  }

  const profitColor = data.total_profit >= 0 ? 'text-green-600' : 'text-red-600';

  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Wallet className="h-5 w-5" />
            【資金管理】
          </CardTitle>
          <div className="flex items-center gap-2">
            {/* 入金ダイアログ */}
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <Plus className="h-4 w-4 mr-1" />
                  入金
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>入金</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <label className="text-sm text-muted-foreground">金額</label>
                    <Input
                      type="number"
                      placeholder="10000"
                      value={depositAmount}
                      onChange={(e) => setDepositAmount(e.target.value)}
                      className="text-right text-lg font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">メモ（任意）</label>
                    <Input
                      placeholder="給料から"
                      value={depositDescription}
                      onChange={(e) => setDepositDescription(e.target.value)}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline">キャンセル</Button>
                  </DialogClose>
                  <DialogClose asChild>
                    <Button onClick={handleDeposit} disabled={submitting}>
                      入金する
                    </Button>
                  </DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* 出金ダイアログ */}
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <Minus className="h-4 w-4 mr-1" />
                  出金
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>出金</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <label className="text-sm text-muted-foreground">金額</label>
                    <Input
                      type="number"
                      placeholder="10000"
                      value={withdrawAmount}
                      onChange={(e) => setWithdrawAmount(e.target.value)}
                      className="text-right text-lg font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">メモ（任意）</label>
                    <Input
                      placeholder="生活費へ"
                      value={withdrawDescription}
                      onChange={(e) => setWithdrawDescription(e.target.value)}
                    />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    現在の残高: {formatCurrency(data.current_balance)}
                  </p>
                </div>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline">キャンセル</Button>
                  </DialogClose>
                  <DialogClose asChild>
                    <Button onClick={handleWithdraw} disabled={submitting} variant="destructive">
                      出金する
                    </Button>
                  </DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* 現在の残高サマリー */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center p-4 bg-muted/30 rounded-lg">
            <div className="text-sm text-muted-foreground">初期資金</div>
            <div className="text-xl font-bold">{formatCurrency(data.config.initial_balance)}</div>
          </div>
          <div className="text-center p-4 bg-muted/30 rounded-lg">
            <div className="text-sm text-muted-foreground">現在資金</div>
            <div className="text-2xl font-bold">{formatCurrency(data.current_balance)}</div>
          </div>
          <div className="text-center p-4 bg-muted/30 rounded-lg">
            <div className="text-sm text-muted-foreground">総損益</div>
            <div className={`text-xl font-bold flex items-center justify-center gap-1 ${profitColor}`}>
              {data.total_profit >= 0 ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
              {data.total_profit >= 0 ? '+' : ''}{formatCurrency(data.total_profit)}
            </div>
          </div>
        </div>

        {/* グラフ */}
        <div className="mb-6">
          <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
            <History className="h-4 w-4" />
            資金推移
          </h3>
          <FundChart 
            data={data.chart_data} 
            initialBalance={data.config.initial_balance}
            height={180}
          />
        </div>

        {/* 期間別サマリー */}
        {data.period_summaries && data.period_summaries.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-medium mb-2">期間別サマリー</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>期間</TableHead>
                  <TableHead className="text-right">投資</TableHead>
                  <TableHead className="text-right">払戻</TableHead>
                  <TableHead className="text-right">収支</TableHead>
                  <TableHead className="text-right">回収率</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.period_summaries.map((summary, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{summary.period}</TableCell>
                    <TableCell className="text-right">{formatCurrency(summary.total_bet)}</TableCell>
                    <TableCell className="text-right">{formatCurrency(summary.total_payout)}</TableCell>
                    <TableCell className={`text-right font-bold ${summary.profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {summary.profit >= 0 ? '+' : ''}{formatCurrency(summary.profit)}
                    </TableCell>
                    <TableCell className={`text-right ${summary.recovery_rate >= 100 ? 'text-green-600' : 'text-red-600'}`}>
                      {summary.recovery_rate.toFixed(1)}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* 履歴（最新5件） */}
        {data.entries && data.entries.length > 0 && (
          <div>
            <h3 className="text-sm font-medium mb-2">最近の履歴</h3>
            <div className="space-y-2">
              {data.entries.slice(0, 5).map((entry) => (
                <div key={entry.id} className="flex items-center justify-between p-2 bg-muted/20 rounded">
                  <div className="flex items-center gap-2">
                    {getEntryTypeBadge(entry.type)}
                    <span className="text-sm">{formatDate(entry.date)}</span>
                    {entry.description && (
                      <span className="text-sm text-muted-foreground">{entry.description}</span>
                    )}
                  </div>
                  <div className={`font-bold ${entry.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {entry.amount >= 0 ? '+' : ''}{formatCurrency(entry.amount)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
