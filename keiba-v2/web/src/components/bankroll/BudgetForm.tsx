'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Save, RotateCcw, TrendingDown, TrendingUp, AlertTriangle, Wallet } from 'lucide-react';

interface Config {
  settings: {
    total_bankroll: number;
    daily_start_balance_yen?: number; // 本日のスタート額(入金額)=日次上限の最優先源
    daily_limit_percent: number;
    race_limit_percent: number;
    use_current_balance?: boolean; // 現在資金ベースか投資枠ベースか
  };
  calculated: {
    dailyLimit: number;
    raceLimit: number;
  };
}

interface BudgetFormProps {
  isModal?: boolean;
}

export function BudgetForm({ isModal = false }: BudgetFormProps) {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentBalance, setCurrentBalance] = useState<number | null>(null);
  const [totalProfit, setTotalProfit] = useState<number>(0);
  const [formData, setFormData] = useState({
    total_bankroll: 100000,
    daily_start_balance_yen: 30000, // 本日のスタート額(入金額)=日次上限
    daily_limit_percent: 5.0,
    race_limit_percent: 2.0,
    use_current_balance: true, // デフォルトは現在資金ベース
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        // 設定を取得
        const configRes = await fetch('/api/bankroll/config');
        if (configRes.ok) {
          const data = await configRes.json();
          setConfig(data);
          setFormData({
            total_bankroll: data.settings?.total_bankroll || 100000,
            daily_start_balance_yen: data.settings?.daily_start_balance_yen ?? 30000,
            daily_limit_percent: data.settings?.daily_limit_percent || 5.0,
            race_limit_percent: data.settings?.race_limit_percent || 2.0,
            use_current_balance: data.settings?.use_current_balance ?? true,
          });
        }
        
        // 現在資金を取得
        const fundRes = await fetch('/api/bankroll/fund');
        if (fundRes.ok) {
          const fundData = await fundRes.json();
          setCurrentBalance(fundData.current_balance);
          setTotalProfit(fundData.total_profit || 0);
        }
      } catch (error) {
        console.error('データ取得エラー:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch('/api/bankroll/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        alert('設定を保存しました');
      } else {
        throw new Error('保存に失敗しました');
      }
    } catch (error) {
      alert('設定の保存に失敗しました');
      console.error('保存エラー:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (config) {
      setFormData({
        total_bankroll: config.settings.total_bankroll,
        daily_start_balance_yen: config.settings.daily_start_balance_yen ?? 30000,
        daily_limit_percent: config.settings.daily_limit_percent,
        race_limit_percent: config.settings.race_limit_percent,
        use_current_balance: config.settings.use_current_balance ?? true,
      });
    }
  };

  // 計算の基準となる金額
  const getBaseAmount = () => {
    if (formData.use_current_balance && currentBalance !== null) {
      return currentBalance;
    }
    return formData.total_bankroll;
  };

  const calculateDailyLimit = () => {
    return Math.floor(getBaseAmount() * (formData.daily_limit_percent / 100));
  };

  const calculateRaceLimit = () => {
    return Math.floor(getBaseAmount() * (formData.race_limit_percent / 100));
  };

  // フォームコンテンツ
  const formContent = (
    <div className="space-y-5">
      {/* ★本日のスタート額 (入金額) = 自動投票の日次上限 = 最大負け額 (Session145) */}
      <div className="p-4 rounded-lg border-2 border-primary/40 bg-primary/5">
        <label className="text-sm font-semibold flex items-center gap-2 mb-1">
          <Wallet className="h-4 w-4 text-primary" />
          本日のスタート額（入金額）
        </label>
        <p className="text-xs text-muted-foreground mb-3">
          原則この額を IPAT に入金してください。<strong>1日に賭ける総額の上限＝最大負け額</strong>になります
          （自動投票は当日朝にこの額を凍結して使用。午前の払戻で口座が増えても上限は動きません）。
        </p>
        <div className="flex items-center gap-3">
          <Input
            type="number"
            step="1000"
            value={formData.daily_start_balance_yen}
            onChange={(e) =>
              setFormData({
                ...formData,
                daily_start_balance_yen: parseInt(e.target.value) || 0,
              })
            }
            className="flex-1 text-right text-2xl font-bold h-14"
          />
          <span className="text-base text-muted-foreground w-8">円</span>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          リスクを下げたい週は、この設定を下げて → その額だけ入金する、という運用にしてください。
        </p>
      </div>

      {/* 現在資金の表示 */}
      {currentBalance !== null && (
        <div className="p-4 rounded-lg bg-muted/50 border">
          <div className="flex items-center gap-2 mb-2">
            <Wallet className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">現在資金（実績）</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold">
              ¥{currentBalance.toLocaleString()}
            </span>
            <Badge 
              variant={totalProfit >= 0 ? 'default' : 'destructive'}
              className="flex items-center gap-1"
            >
              {totalProfit >= 0 ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {totalProfit >= 0 ? '+' : ''}¥{totalProfit.toLocaleString()}
            </Badge>
          </div>
        </div>
      )}

      {/* 計算基準の選択 */}
      <div className="space-y-2">
        <label className="text-sm text-muted-foreground block">
          1日上限の計算基準
        </label>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={formData.use_current_balance ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFormData({ ...formData, use_current_balance: true })}
            className="flex-1"
          >
            現在資金ベース
          </Button>
          <Button
            type="button"
            variant={!formData.use_current_balance ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFormData({ ...formData, use_current_balance: false })}
            className="flex-1"
          >
            投資枠ベース
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {formData.use_current_balance 
            ? '💡 負けると1日上限も減少します（抑止効果あり）' 
            : '📌 投資枠は固定で、現在資金に関係なく一定です'}
        </p>
      </div>

      {/* 投資枠（use_current_balance=falseの時のみ編集可能） */}
      <div className={formData.use_current_balance ? 'opacity-50' : ''}>
        <label className="text-sm text-muted-foreground mb-2 block">
          投資枠
        </label>
        <div className="flex items-center gap-3">
          <Input
            type="number"
            value={formData.total_bankroll}
            onChange={(e) =>
              setFormData({
                ...formData,
                total_bankroll: parseInt(e.target.value) || 0,
              })
            }
            disabled={formData.use_current_balance}
            className="flex-1 text-right text-lg font-bold h-12"
          />
          <span className="text-base text-muted-foreground w-8">円</span>
        </div>
        {formData.use_current_balance && (
          <p className="text-xs text-muted-foreground mt-1">
            ※ 現在資金ベースのため使用されません
          </p>
        )}
      </div>

      {/* 計算基準の表示 */}
      <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
        <div className="text-sm text-muted-foreground mb-1">計算基準</div>
        <div className="text-xl font-bold text-primary">
          ¥{getBaseAmount().toLocaleString()}
        </div>
      </div>

      <div>
        <label className="text-sm text-muted-foreground mb-2 block">
          1日上限
        </label>
        <div className="flex items-center gap-3">
          <Input
            type="number"
            step="0.1"
            value={formData.daily_limit_percent}
            onChange={(e) =>
              setFormData({
                ...formData,
                daily_limit_percent: parseFloat(e.target.value) || 0,
              })
            }
            className="w-24 text-right text-lg font-bold h-12"
          />
          <span className="text-base text-muted-foreground">%</span>
          <span className="text-lg font-bold text-primary ml-auto">
            → ¥{calculateDailyLimit().toLocaleString()}
          </span>
        </div>
      </div>

      <div>
        <label className="text-sm text-muted-foreground mb-2 block">
          1レース上限
        </label>
        <div className="flex items-center gap-3">
          <Input
            type="number"
            step="0.1"
            value={formData.race_limit_percent}
            onChange={(e) =>
              setFormData({
                ...formData,
                race_limit_percent: parseFloat(e.target.value) || 0,
              })
            }
            className="w-24 text-right text-lg font-bold h-12"
          />
          <span className="text-base text-muted-foreground">%</span>
          <span className="text-lg font-bold text-primary ml-auto">
            → ¥{calculateRaceLimit().toLocaleString()}
          </span>
        </div>
      </div>

      <div className="flex gap-3 pt-4">
        <Button onClick={handleSave} disabled={saving} className="flex-1 h-11">
          <Save className="h-4 w-4 mr-2" />
          保存
        </Button>
        <Button
          onClick={handleReset}
          variant="outline"
          disabled={saving}
          className="flex-1 h-11"
        >
          <RotateCcw className="h-4 w-4 mr-2" />
          リセット
        </Button>
      </div>
    </div>
  );

  if (loading) {
    if (isModal) {
      return <p className="text-muted-foreground py-4">読み込み中...</p>;
    }
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">本日の予算設定</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  // モーダル表示の場合はカードなし
  if (isModal) {
    return formContent;
  }

  // 通常表示の場合はカードでラップ
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">本日の予算設定</CardTitle>
      </CardHeader>
      <CardContent>{formContent}</CardContent>
    </Card>
  );
}
