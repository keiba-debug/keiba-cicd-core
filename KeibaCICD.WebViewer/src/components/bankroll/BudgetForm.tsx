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

export function BudgetForm() {
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

  if (loading) {
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

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">本日の予算設定</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-sm text-muted-foreground mb-1 block">
            総資金
          </label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={formData.total_bankroll}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  total_bankroll: parseInt(e.target.value) || 0,
                })
              }
              className="flex-1"
            />
            <span className="text-sm text-muted-foreground">円</span>
          </div>
        </div>

        <div>
          <label className="text-sm text-muted-foreground mb-1 block">
            1日上限
          </label>
          <div className="flex items-center gap-2">
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
              className="w-24"
            />
            <span className="text-sm text-muted-foreground">%</span>
            <span className="text-sm font-medium ml-auto">
              → {calculateDailyLimit().toLocaleString()}円
            </span>
          </div>
        </div>

        <div>
          <label className="text-sm text-muted-foreground mb-1 block">
            1レース上限
          </label>
          <div className="flex items-center gap-2">
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
              className="w-24"
            />
            <span className="text-sm text-muted-foreground">%</span>
            <span className="text-sm font-medium ml-auto">
              → {calculateRaceLimit().toLocaleString()}円
            </span>
          </div>
        </div>

        <div className="flex gap-2 pt-2">
          <Button onClick={handleSave} disabled={saving} className="flex-1">
            <Save className="h-4 w-4 mr-2" />
            保存
          </Button>
          <Button
            onClick={handleReset}
            variant="outline"
            disabled={saving}
            className="flex-1"
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            リセット
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
