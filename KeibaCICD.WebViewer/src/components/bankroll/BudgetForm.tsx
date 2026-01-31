'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Save, RotateCcw } from 'lucide-react';

interface Config {
  settings: {
    total_bankroll: number;
    daily_limit_percent: number;
    race_limit_percent: number;
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
  const [formData, setFormData] = useState({
    total_bankroll: 100000,
    daily_limit_percent: 5.0,
    race_limit_percent: 2.0,
  });

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await fetch('/api/bankroll/config');
        if (res.ok) {
          const data = await res.json();
          setConfig(data);
          setFormData({
            total_bankroll: data.settings?.total_bankroll || 100000,
            daily_limit_percent: data.settings?.daily_limit_percent || 5.0,
            race_limit_percent: data.settings?.race_limit_percent || 2.0,
          });
        }
      } catch (error) {
        console.error('設定取得エラー:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchConfig();
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
        daily_limit_percent: config.settings.daily_limit_percent,
        race_limit_percent: config.settings.race_limit_percent,
      });
    }
  };

  const calculateDailyLimit = () => {
    return Math.floor(formData.total_bankroll * (formData.daily_limit_percent / 100));
  };

  const calculateRaceLimit = () => {
    return Math.floor(formData.total_bankroll * (formData.race_limit_percent / 100));
  };

  // フォームコンテンツ
  const formContent = (
    <div className="space-y-5">
      <div>
        <label className="text-sm text-muted-foreground mb-2 block">
          総資金
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
            className="flex-1 text-right text-lg font-bold h-12"
          />
          <span className="text-base text-muted-foreground w-8">円</span>
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
