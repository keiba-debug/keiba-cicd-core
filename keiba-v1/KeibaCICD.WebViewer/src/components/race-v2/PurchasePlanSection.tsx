'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  ShoppingCart,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Check,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';

interface Entry {
  horse_number: number;
  horse_name: string;
  jockey_name?: string;
  odds?: number;
}

interface PurchaseItem {
  id: string;
  race_id: string;
  race_name: string;
  venue: string;
  race_number: number;
  bet_type: string;
  selection: string;
  amount: number;
  odds: number | null;
  expected_value: number | null;
  status: 'planned' | 'purchased' | 'result_win' | 'result_lose';
  payout: number;
  confidence: '高' | '中' | '低';
  reason: string;
  created_at: string;
}

interface PurchasePlanSectionProps {
  raceId: string;
  raceDate: string;
  raceName: string;
  venue: string;
  raceNumber: number;
  entries: Entry[];
}

const BET_TYPES = [
  '単勝',
  '複勝',
  '馬連',
  'ワイド',
  '馬単',
  '三連複',
  '三連単',
];

export function PurchasePlanSection({
  raceId,
  raceDate,
  raceName,
  venue,
  raceNumber,
  entries,
}: PurchasePlanSectionProps) {
  const [items, setItems] = useState<PurchaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [dailyBudget, setDailyBudget] = useState(20000);
  const [raceLimit, setRaceLimit] = useState(2000);
  const [totalPlanned, setTotalPlanned] = useState(0);

  // 購入リストを取得
  const fetchPurchases = useCallback(async () => {
    try {
      const res = await fetch(`/api/purchases/${raceDate}`);
      if (res.ok) {
        const data = await res.json();
        // このレースの購入のみフィルタ
        const raceItems = data.items.filter(
          (item: PurchaseItem) => item.race_id === raceId
        );
        setItems(raceItems);
        setTotalPlanned(data.total_planned + data.total_purchased);
      }
    } catch (error) {
      console.error('購入リスト取得エラー:', error);
    } finally {
      setLoading(false);
    }
  }, [raceDate, raceId]);

  // 設定を取得
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await fetch('/api/bankroll/config');
        if (res.ok) {
          const data = await res.json();
          const totalBankroll = data.settings?.total_bankroll || 100000;
          const dailyLimitPercent = data.settings?.daily_limit_percent || 5;
          const raceLimitPercent = data.settings?.race_limit_percent || 2;
          setDailyBudget(
            Math.floor(totalBankroll * (dailyLimitPercent / 100))
          );
          setRaceLimit(Math.floor(totalBankroll * (raceLimitPercent / 100)));
        }
      } catch (error) {
        console.error('設定取得エラー:', error);
      }
    };
    fetchConfig();
  }, []);

  useEffect(() => {
    fetchPurchases();
  }, [fetchPurchases]);

  // 購入を追加
  const addPurchase = async (data: {
    bet_type: string;
    selection: string;
    amount: number;
    odds?: number;
    confidence: '高' | '中' | '低';
    reason: string;
  }) => {
    try {
      const res = await fetch(`/api/purchases/${raceDate}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          race_id: raceId,
          race_name: raceName,
          venue,
          race_number: raceNumber,
          ...data,
          status: 'planned',
        }),
      });

      if (res.ok) {
        fetchPurchases();
        setShowAddForm(false);
      } else {
        alert('追加に失敗しました');
      }
    } catch (error) {
      console.error('追加エラー:', error);
      alert('追加に失敗しました');
    }
  };

  // ステータスを更新
  const updateStatus = async (
    id: string,
    status: 'planned' | 'purchased' | 'result_win' | 'result_lose',
    payout?: number
  ) => {
    try {
      const res = await fetch(`/api/purchases/${raceDate}?id=${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, payout: payout || 0 }),
      });

      if (res.ok) {
        fetchPurchases();
      }
    } catch (error) {
      console.error('更新エラー:', error);
    }
  };

  // 削除
  const deletePurchase = async (id: string) => {
    if (!confirm('この購入予定を削除しますか？')) return;

    try {
      const res = await fetch(`/api/purchases/${raceDate}?id=${id}`, {
        method: 'DELETE',
      });

      if (res.ok) {
        fetchPurchases();
      }
    } catch (error) {
      console.error('削除エラー:', error);
    }
  };

  // このレースの購入合計
  const raceTotal = items.reduce((sum, item) => sum + item.amount, 0);
  const isOverRaceLimit = raceTotal > raceLimit;
  const isOverDailyLimit = totalPlanned > dailyBudget;

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            購入計画
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            購入計画
            {items.length > 0 && (
              <Badge variant="secondary">{items.length}件</Badge>
            )}
          </CardTitle>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {expanded ? (
          <div className="space-y-4">
            {/* 予算警告 */}
            {(isOverRaceLimit || isOverDailyLimit) && (
              <div className="p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg flex items-center gap-2 text-sm text-yellow-700 dark:text-yellow-400">
                <AlertTriangle className="h-4 w-4" />
                {isOverRaceLimit && (
                  <span>
                    1レース上限({raceLimit.toLocaleString()}円)を超過
                  </span>
                )}
                {isOverDailyLimit && (
                  <span>1日上限({dailyBudget.toLocaleString()}円)を超過</span>
                )}
              </div>
            )}

            {/* 購入リスト */}
            {items.length > 0 ? (
              <div className="space-y-2">
                {items.map((item) => (
                  <PurchaseItemCard
                    key={item.id}
                    item={item}
                    onStatusChange={updateStatus}
                    onDelete={deletePurchase}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-2">
                購入予定なし
              </p>
            )}

            {/* 追加フォーム */}
            {showAddForm ? (
              <AddPurchaseForm
                entries={entries}
                onSubmit={addPurchase}
                onCancel={() => setShowAddForm(false)}
                raceLimit={raceLimit}
                currentTotal={raceTotal}
              />
            ) : (
              <Button
                variant="outline"
                onClick={() => setShowAddForm(true)}
                className="w-full"
              >
                <Plus className="h-4 w-4 mr-2" />
                買い目を追加
              </Button>
            )}

            {/* サマリー */}
            <div className="pt-2 border-t text-sm">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">このレース合計</span>
                <span
                  className={`font-medium ${
                    isOverRaceLimit ? 'text-red-600' : ''
                  }`}
                >
                  {raceTotal.toLocaleString()}円 / {raceLimit.toLocaleString()}
                  円
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">本日合計</span>
                <span
                  className={`font-medium ${
                    isOverDailyLimit ? 'text-red-600' : ''
                  }`}
                >
                  {totalPlanned.toLocaleString()}円 /{' '}
                  {dailyBudget.toLocaleString()}円
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-2">
            {items.length > 0 ? (
              <div className="space-y-1">
                {items.slice(0, 3).map((item) => (
                  <div key={item.id} className="text-sm">
                    <Badge variant="outline" className="mr-1">
                      {item.bet_type}
                    </Badge>
                    <span className="font-mono">{item.selection}</span>
                    <span className="ml-2 text-muted-foreground">
                      {item.amount.toLocaleString()}円
                    </span>
                  </div>
                ))}
                {items.length > 3 && (
                  <p className="text-xs text-muted-foreground">
                    他{items.length - 3}件
                  </p>
                )}
              </div>
            ) : (
              <Button variant="outline" onClick={() => setExpanded(true)}>
                購入計画を追加
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// 購入アイテムカード
function PurchaseItemCard({
  item,
  onStatusChange,
  onDelete,
}: {
  item: PurchaseItem;
  onStatusChange: (
    id: string,
    status: 'planned' | 'purchased' | 'result_win' | 'result_lose',
    payout?: number
  ) => void;
  onDelete: (id: string) => void;
}) {
  const [showResultInput, setShowResultInput] = useState(false);
  const [payout, setPayout] = useState('');

  const handleResult = (result: 'win' | 'lose') => {
    if (result === 'win') {
      onStatusChange(item.id, 'result_win', parseInt(payout) || 0);
    } else {
      onStatusChange(item.id, 'result_lose', 0);
    }
    setShowResultInput(false);
  };

  return (
    <div className="p-3 border rounded-lg space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline">{item.bet_type}</Badge>
          <span className="font-mono text-sm">{item.selection}</span>
          <span className="font-medium text-sm">
            {item.amount.toLocaleString()}円
          </span>
          {item.odds && (
            <span className="text-xs text-muted-foreground">
              @{item.odds}倍
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {item.status === 'planned' && (
            <>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onStatusChange(item.id, 'purchased')}
                title="購入済みにする"
              >
                <Check className="h-4 w-4 text-green-600" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onDelete(item.id)}
              >
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            </>
          )}
          {item.status === 'purchased' && (
            <Badge className="bg-blue-500">購入済</Badge>
          )}
          {item.status === 'result_win' && (
            <Badge className="bg-green-500">
              <TrendingUp className="h-3 w-3 mr-1" />
              的中 +{item.payout.toLocaleString()}円
            </Badge>
          )}
          {item.status === 'result_lose' && (
            <Badge variant="destructive">
              <TrendingDown className="h-3 w-3 mr-1" />
              不的中
            </Badge>
          )}
        </div>
      </div>

      {/* 結果入力 */}
      {item.status === 'purchased' && (
        <div className="pt-2 border-t">
          {showResultInput ? (
            <div className="flex items-center gap-2">
              <Input
                type="number"
                placeholder="払戻額"
                value={payout}
                onChange={(e) => setPayout(e.target.value)}
                className="w-24 h-7 text-xs"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={() => handleResult('win')}
              >
                <TrendingUp className="h-3 w-3 mr-1" />
                的中
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={() => handleResult('lose')}
              >
                <TrendingDown className="h-3 w-3 mr-1" />
                不的中
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs"
                onClick={() => setShowResultInput(false)}
              >
                キャンセル
              </Button>
            </div>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => setShowResultInput(true)}
            >
              結果を入力
            </Button>
          )}
        </div>
      )}

      {item.reason && (
        <p className="text-xs text-muted-foreground">{item.reason}</p>
      )}
    </div>
  );
}

// 購入追加フォーム
function AddPurchaseForm({
  entries,
  onSubmit,
  onCancel,
  raceLimit,
  currentTotal,
}: {
  entries: Entry[];
  onSubmit: (data: {
    bet_type: string;
    selection: string;
    amount: number;
    odds?: number;
    confidence: '高' | '中' | '低';
    reason: string;
  }) => void;
  onCancel: () => void;
  raceLimit: number;
  currentTotal: number;
}) {
  const [betType, setBetType] = useState('馬連');
  const [selection, setSelection] = useState('');
  const [amount, setAmount] = useState('');
  const [odds, setOdds] = useState('');
  const [confidence, setConfidence] = useState<'高' | '中' | '低'>('中');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selection || !amount) {
      alert('買い目と金額を入力してください');
      return;
    }

    setSaving(true);
    await onSubmit({
      bet_type: betType,
      selection,
      amount: parseInt(amount),
      odds: odds ? parseFloat(odds) : undefined,
      confidence,
      reason,
    });
    setSaving(false);
  };

  const remaining = raceLimit - currentTotal;
  const isOverLimit = parseInt(amount) > remaining;

  return (
    <form onSubmit={handleSubmit} className="p-3 border rounded-lg space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-muted-foreground">券種</label>
          <select
            value={betType}
            onChange={(e) => setBetType(e.target.value)}
            className="w-full h-9 rounded-md border bg-background px-2 text-sm"
          >
            {BET_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">買い目</label>
          <Input
            value={selection}
            onChange={(e) => setSelection(e.target.value)}
            placeholder="1-2 or 1-2-3"
            className="h-9"
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs text-muted-foreground">金額</label>
          <Input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="1000"
            className={`h-9 ${isOverLimit ? 'border-red-500' : ''}`}
          />
          {isOverLimit && (
            <p className="text-xs text-red-500 mt-1">
              上限超過 (残り{remaining.toLocaleString()}円)
            </p>
          )}
        </div>
        <div>
          <label className="text-xs text-muted-foreground">オッズ</label>
          <Input
            type="number"
            step="0.1"
            value={odds}
            onChange={(e) => setOdds(e.target.value)}
            placeholder="5.0"
            className="h-9"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">自信度</label>
          <select
            value={confidence}
            onChange={(e) =>
              setConfidence(e.target.value as '高' | '中' | '低')
            }
            className="w-full h-9 rounded-md border bg-background px-2 text-sm"
          >
            <option value="高">高</option>
            <option value="中">中</option>
            <option value="低">低</option>
          </select>
        </div>
      </div>

      <div>
        <label className="text-xs text-muted-foreground">理由メモ</label>
        <Input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="購入理由など"
          className="h-9"
        />
      </div>

      {/* 期待値表示 */}
      {odds && amount && (
        <div className="text-sm">
          <span className="text-muted-foreground">期待値: </span>
          <span
            className={`font-medium ${
              parseFloat(odds) * 100 > parseInt(amount) * 100
                ? 'text-green-600'
                : 'text-red-600'
            }`}
          >
            {((parseFloat(odds) * 100) / parseInt(amount)).toFixed(1)}%
          </span>
        </div>
      )}

      <div className="flex gap-2">
        <Button type="submit" disabled={saving} className="flex-1">
          追加
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          キャンセル
        </Button>
      </div>
    </form>
  );
}
