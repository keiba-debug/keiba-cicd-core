'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Plus,
  Check,
  X,
  Trash2,
  Clock,
  TrendingUp,
  TrendingDown,
  ShoppingCart,
  Target,
} from 'lucide-react';

interface PurchasePlan {
  id: string;
  race_id: string;
  race_name: string;
  venue: string;
  race_number: number;
  bet_type: string;
  selection: string;
  amount: number;
  confidence: '高' | '中' | '低';
  reason: string;
  status: 'pending' | 'purchased' | 'skipped';
  result?: 'win' | 'lose' | null;
  payout?: number;
  created_at: string;
  updated_at?: string;
}

interface DailyPlan {
  date: string;
  plans: PurchasePlan[];
  total_planned: number;
  total_purchased: number;
  updated_at: string;
}

interface PurchasePlanSectionProps {
  dailyBudget: number;
}

export function PurchasePlanSection({ dailyBudget }: PurchasePlanSectionProps) {
  const [dailyPlan, setDailyPlan] = useState<DailyPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingResultId, setEditingResultId] = useState<string | null>(null);
  const [payoutInput, setPayoutInput] = useState('');

  // 今日の日付を取得
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');

  // 購入予定を取得
  const fetchPlans = useCallback(async () => {
    try {
      const res = await fetch(`/api/bankroll/plans?date=${today}`);
      if (res.ok) {
        const data = await res.json();
        setDailyPlan(data);
      }
    } catch (error) {
      console.error('購入予定取得エラー:', error);
    } finally {
      setLoading(false);
    }
  }, [today]);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  // ステータスを更新
  const updateStatus = async (
    id: string,
    status: 'pending' | 'purchased' | 'skipped'
  ) => {
    try {
      const res = await fetch('/api/bankroll/plans', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: today, id, status }),
      });
      if (res.ok) {
        fetchPlans();
      }
    } catch (error) {
      console.error('ステータス更新エラー:', error);
    }
  };

  // 結果を登録
  const updateResult = async (
    id: string,
    result: 'win' | 'lose',
    payout: number = 0
  ) => {
    try {
      const res = await fetch('/api/bankroll/plans', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: today, id, result, payout }),
      });
      if (res.ok) {
        fetchPlans();
        setEditingResultId(null);
        setPayoutInput('');
      }
    } catch (error) {
      console.error('結果更新エラー:', error);
    }
  };

  // 購入予定を削除
  const deletePlan = async (id: string) => {
    if (!confirm('この購入予定を削除しますか？')) return;

    try {
      const res = await fetch(`/api/bankroll/plans?date=${today}&id=${id}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchPlans();
      }
    } catch (error) {
      console.error('削除エラー:', error);
    }
  };

  // 信頼度バッジの色
  const getConfidenceBadge = (confidence: string) => {
    switch (confidence) {
      case '高':
        return <Badge className="bg-green-500">高</Badge>;
      case '中':
        return <Badge className="bg-yellow-500">中</Badge>;
      case '低':
        return <Badge className="bg-gray-500">低</Badge>;
      default:
        return <Badge variant="outline">{confidence}</Badge>;
    }
  };

  // 予定リストのアイテム
  const PlanItem = ({ plan }: { plan: PurchasePlan }) => (
    <div className="flex items-start gap-3 p-3 border rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm">
            {plan.venue}
            {plan.race_number}R
          </span>
          {plan.race_name && (
            <span className="text-xs text-muted-foreground">
              {plan.race_name}
            </span>
          )}
          {getConfidenceBadge(plan.confidence)}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Badge variant="outline">{plan.bet_type}</Badge>
          <span className="font-mono">{plan.selection}</span>
          <span className="font-medium">
            {plan.amount.toLocaleString()}円
          </span>
        </div>
        {plan.reason && (
          <p className="text-xs text-muted-foreground mt-1">{plan.reason}</p>
        )}
      </div>
      <div className="flex items-center gap-1">
        <Button
          size="sm"
          variant="ghost"
          onClick={() => updateStatus(plan.id, 'purchased')}
          title="購入済みにする"
        >
          <ShoppingCart className="h-4 w-4 text-green-600" />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => updateStatus(plan.id, 'skipped')}
          title="スキップ"
        >
          <X className="h-4 w-4 text-gray-500" />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => deletePlan(plan.id)}
          title="削除"
        >
          <Trash2 className="h-4 w-4 text-red-500" />
        </Button>
      </div>
    </div>
  );

  // 購入済みアイテム
  const PurchasedItem = ({ plan }: { plan: PurchasePlan }) => (
    <div className="flex items-start gap-3 p-3 border rounded-lg bg-muted/30">
      <Check className="h-5 w-5 text-green-600 mt-0.5" />
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm">
            {plan.venue}
            {plan.race_number}R
          </span>
          <Badge variant="outline">{plan.bet_type}</Badge>
          <span className="font-mono text-sm">{plan.selection}</span>
          <span className="font-medium text-sm">
            {plan.amount.toLocaleString()}円
          </span>
        </div>

        {plan.result === null || plan.result === undefined ? (
          <div className="flex items-center gap-2 mt-2">
            {editingResultId === plan.id ? (
              <>
                <Input
                  type="number"
                  placeholder="払戻額"
                  value={payoutInput}
                  onChange={(e) => setPayoutInput(e.target.value)}
                  className="w-24 h-7 text-xs"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs"
                  onClick={() =>
                    updateResult(plan.id, 'win', parseInt(payoutInput) || 0)
                  }
                >
                  <TrendingUp className="h-3 w-3 mr-1" />
                  的中
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs"
                  onClick={() => updateResult(plan.id, 'lose', 0)}
                >
                  <TrendingDown className="h-3 w-3 mr-1" />
                  不的中
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => {
                    setEditingResultId(null);
                    setPayoutInput('');
                  }}
                >
                  キャンセル
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={() => setEditingResultId(plan.id)}
              >
                <Clock className="h-3 w-3 mr-1" />
                結果を入力
              </Button>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 mt-1">
            {plan.result === 'win' ? (
              <Badge className="bg-green-500">
                <TrendingUp className="h-3 w-3 mr-1" />
                的中 +{(plan.payout || 0).toLocaleString()}円
              </Badge>
            ) : (
              <Badge variant="destructive">
                <TrendingDown className="h-3 w-3 mr-1" />
                不的中
              </Badge>
            )}
          </div>
        )}
      </div>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => updateStatus(plan.id, 'pending')}
        title="予定に戻す"
      >
        <X className="h-4 w-4 text-gray-500" />
      </Button>
    </div>
  );

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Target className="h-5 w-5" />
            購入管理
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  const pendingPlans =
    dailyPlan?.plans.filter((p) => p.status === 'pending') || [];
  const purchasedPlans =
    dailyPlan?.plans.filter((p) => p.status === 'purchased') || [];
  const skippedPlans =
    dailyPlan?.plans.filter((p) => p.status === 'skipped') || [];

  const remainingBudget =
    dailyBudget - (dailyPlan?.total_planned || 0) - (dailyPlan?.total_purchased || 0);

  return (
    <div className="space-y-6">
      {/* 購入予定セクション */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Target className="h-5 w-5" />
              本日の購入予定
            </CardTitle>
            <Button
              size="sm"
              onClick={() => setShowAddForm(!showAddForm)}
              variant={showAddForm ? 'secondary' : 'default'}
            >
              <Plus className="h-4 w-4 mr-1" />
              追加
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {showAddForm && (
            <AddPlanForm
              date={today}
              onSuccess={() => {
                fetchPlans();
                setShowAddForm(false);
              }}
              onCancel={() => setShowAddForm(false)}
            />
          )}

          {pendingPlans.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              購入予定がありません
            </p>
          ) : (
            <div className="space-y-2">
              {pendingPlans.map((plan) => (
                <PlanItem key={plan.id} plan={plan} />
              ))}
            </div>
          )}

          <div className="flex justify-between items-center pt-3 border-t text-sm">
            <span className="text-muted-foreground">予定合計</span>
            <span className="font-medium">
              {(dailyPlan?.total_planned || 0).toLocaleString()}円
            </span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">残り予算</span>
            <span
              className={`font-medium ${
                remainingBudget < 0
                  ? 'text-red-600'
                  : remainingBudget < dailyBudget * 0.2
                  ? 'text-yellow-600'
                  : 'text-green-600'
              }`}
            >
              {remainingBudget.toLocaleString()}円
            </span>
          </div>
        </CardContent>
      </Card>

      {/* 購入済みセクション */}
      {purchasedPlans.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <ShoppingCart className="h-5 w-5" />
              購入済み
              <Badge variant="secondary">{purchasedPlans.length}件</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {purchasedPlans.map((plan) => (
              <PurchasedItem key={plan.id} plan={plan} />
            ))}
            <div className="flex justify-between items-center pt-3 border-t text-sm">
              <span className="text-muted-foreground">購入合計</span>
              <span className="font-medium">
                {(dailyPlan?.total_purchased || 0).toLocaleString()}円
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* スキップ済みセクション */}
      {skippedPlans.length > 0 && (
        <Card className="opacity-60">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
              <X className="h-4 w-4" />
              スキップ
              <Badge variant="outline">{skippedPlans.length}件</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 text-sm text-muted-foreground">
              {skippedPlans.map((plan) => (
                <div
                  key={plan.id}
                  className="flex items-center justify-between"
                >
                  <span>
                    {plan.venue}
                    {plan.race_number}R {plan.bet_type} {plan.selection}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-xs"
                    onClick={() => updateStatus(plan.id, 'pending')}
                  >
                    戻す
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// 購入予定追加フォーム
interface AddPlanFormProps {
  date: string;
  onSuccess: () => void;
  onCancel: () => void;
}

function AddPlanForm({ date, onSuccess, onCancel }: AddPlanFormProps) {
  const [formData, setFormData] = useState({
    venue: '',
    race_number: '',
    race_name: '',
    bet_type: '馬連',
    selection: '',
    amount: '',
    confidence: '中' as '高' | '中' | '低',
    reason: '',
  });
  const [saving, setSaving] = useState(false);

  const betTypes = [
    '単勝',
    '複勝',
    '馬連',
    'ワイド',
    '馬単',
    '三連複',
    '三連単',
  ];
  const venues = ['東京', '中山', '京都', '阪神', '中京', '小倉', '新潟', '福島', '札幌', '函館'];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.venue || !formData.race_number || !formData.selection || !formData.amount) {
      alert('必須項目を入力してください');
      return;
    }

    setSaving(true);
    try {
      const raceId = `${date}${formData.venue}${formData.race_number.padStart(2, '0')}`;
      
      const res = await fetch('/api/bankroll/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date,
          race_id: raceId,
          race_name: formData.race_name,
          venue: formData.venue,
          race_number: parseInt(formData.race_number),
          bet_type: formData.bet_type,
          selection: formData.selection,
          amount: parseInt(formData.amount),
          confidence: formData.confidence,
          reason: formData.reason,
        }),
      });

      if (res.ok) {
        onSuccess();
      } else {
        const error = await res.json();
        alert(error.error || '追加に失敗しました');
      }
    } catch (error) {
      console.error('追加エラー:', error);
      alert('追加に失敗しました');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-4 border rounded-lg bg-muted/30 space-y-3"
    >
      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs text-muted-foreground">競馬場 *</label>
          <select
            value={formData.venue}
            onChange={(e) => setFormData({ ...formData, venue: e.target.value })}
            className="w-full h-9 rounded-md border bg-background px-2 text-sm"
          >
            <option value="">選択</option>
            {venues.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">R *</label>
          <Input
            type="number"
            min="1"
            max="12"
            value={formData.race_number}
            onChange={(e) =>
              setFormData({ ...formData, race_number: e.target.value })
            }
            placeholder="11"
            className="h-9"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">レース名</label>
          <Input
            value={formData.race_name}
            onChange={(e) =>
              setFormData({ ...formData, race_name: e.target.value })
            }
            placeholder="白富士S"
            className="h-9"
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs text-muted-foreground">券種 *</label>
          <select
            value={formData.bet_type}
            onChange={(e) =>
              setFormData({ ...formData, bet_type: e.target.value })
            }
            className="w-full h-9 rounded-md border bg-background px-2 text-sm"
          >
            {betTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">買い目 *</label>
          <Input
            value={formData.selection}
            onChange={(e) =>
              setFormData({ ...formData, selection: e.target.value })
            }
            placeholder="4-6"
            className="h-9"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">金額 *</label>
          <Input
            type="number"
            value={formData.amount}
            onChange={(e) =>
              setFormData({ ...formData, amount: e.target.value })
            }
            placeholder="1000"
            className="h-9"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-muted-foreground">自信度</label>
          <select
            value={formData.confidence}
            onChange={(e) =>
              setFormData({
                ...formData,
                confidence: e.target.value as '高' | '中' | '低',
              })
            }
            className="w-full h-9 rounded-md border bg-background px-2 text-sm"
          >
            <option value="高">高</option>
            <option value="中">中</option>
            <option value="低">低</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">理由メモ</label>
          <Input
            value={formData.reason}
            onChange={(e) =>
              setFormData({ ...formData, reason: e.target.value })
            }
            placeholder="ダノンとウィクトルの2頭軸"
            className="h-9"
          />
        </div>
      </div>

      <div className="flex gap-2 pt-2">
        <Button type="submit" disabled={saving} className="flex-1">
          {saving ? '追加中...' : '追加'}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          キャンセル
        </Button>
      </div>
    </form>
  );
}
