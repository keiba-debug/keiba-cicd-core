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
    per_race_max_yen?: number; // 1レース上限 (per_race_cap・スリーブ1点額もこれで縮小される)
    // gap単勝 本投票 (Session 176) — 隔離口座。combo とは別の自動投票枠。
    gap_enabled?: boolean;
    gap_initial_bankroll_yen?: number;
    gap_bet_pct?: number;
    gap_day_pct?: number;
    // 本命EV単 本投票 (Session 177) — 2本目スリーブ (隔離口座・gap と別建て)。
    tansho_ev_enabled?: boolean;
    tansho_ev_initial_bankroll_yen?: number;
    tansho_ev_bet_pct?: number;
    tansho_ev_day_pct?: number;
    // コメＡ3点セット 本投票 (Session 189) — 3本目スリーブ (隔離口座)。
    comment_a_enabled?: boolean;
    comment_a_initial_bankroll_yen?: number;
    comment_a_bet_pct?: number;
    comment_a_day_pct?: number;
    comment_a_r4_boost?: boolean;
    sleeve_total_day_cap_yen?: number; // スリーブ全体の日次純投資ハード上限 (0=自動=Σ)
    sleeve_per_race_cap_yen?: number; // スリーブのレース合算per_race上限 (案A・per_race_max_yenと連動)
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
    // gap単勝 本投票 (Session 176)。 既定 = 無効・30万・1点1%・日次5%。
    gap_enabled: false,
    gap_initial_bankroll_yen: 300000,
    gap_bet_pct: 1.0,
    gap_day_pct: 5.0,
    // 本命EV単 本投票 (Session 177)。 既定 = 無効・30万・1点2%・日次10%。
    tansho_ev_enabled: false,
    tansho_ev_initial_bankroll_yen: 300000,
    tansho_ev_bet_pct: 2.0,
    tansho_ev_day_pct: 10.0,
    // コメＡ3点セット 本投票 (Session 189)。 既定 = 無効・30万・1単位0.5%・日次10%・R4増額on。
    comment_a_enabled: false,
    comment_a_initial_bankroll_yen: 300000,
    comment_a_bet_pct: 0.5,
    comment_a_day_pct: 10.0,
    comment_a_r4_boost: true,
    sleeve_total_day_cap_yen: 0, // 0=自動(各スリーブ日次capの合計)
    // レース合算per_race上限 (案A・Session 178)。保存時 per_race_max_yen にも連動して書く
    //   (= runner番人と一致必須)。初期は現 per_race_max_yen を引き継ぐ。
    sleeve_per_race_cap_yen: 5200,
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
            gap_enabled: data.settings?.gap_enabled ?? false,
            gap_initial_bankroll_yen: data.settings?.gap_initial_bankroll_yen ?? 300000,
            gap_bet_pct: data.settings?.gap_bet_pct ?? 1.0,
            gap_day_pct: data.settings?.gap_day_pct ?? 5.0,
            tansho_ev_enabled: data.settings?.tansho_ev_enabled ?? false,
            tansho_ev_initial_bankroll_yen: data.settings?.tansho_ev_initial_bankroll_yen ?? 300000,
            tansho_ev_bet_pct: data.settings?.tansho_ev_bet_pct ?? 2.0,
            tansho_ev_day_pct: data.settings?.tansho_ev_day_pct ?? 10.0,
            comment_a_enabled: data.settings?.comment_a_enabled ?? false,
            comment_a_initial_bankroll_yen: data.settings?.comment_a_initial_bankroll_yen ?? 300000,
            comment_a_bet_pct: data.settings?.comment_a_bet_pct ?? 0.5,
            comment_a_day_pct: data.settings?.comment_a_day_pct ?? 10.0,
            comment_a_r4_boost: data.settings?.comment_a_r4_boost ?? true,
            sleeve_total_day_cap_yen: data.settings?.sleeve_total_day_cap_yen ?? 0,
            sleeve_per_race_cap_yen:
              data.settings?.sleeve_per_race_cap_yen ?? data.settings?.per_race_max_yen ?? 5200,
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
      // ★案A 連動 (Session 178)★: レース合算上限は runner の番人 per_race_max_yen と一致必須なので、
      //   保存時に per_race_max_yen も同値で書く (orchestrator は不一致なら投票しない fail-safe)。
      const payload = {
        ...formData,
        per_race_max_yen: formData.sleeve_per_race_cap_yen,
      };
      const res = await fetch('/api/bankroll/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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
        gap_enabled: config.settings.gap_enabled ?? false,
        gap_initial_bankroll_yen: config.settings.gap_initial_bankroll_yen ?? 300000,
        gap_bet_pct: config.settings.gap_bet_pct ?? 1.0,
        gap_day_pct: config.settings.gap_day_pct ?? 5.0,
        tansho_ev_enabled: config.settings.tansho_ev_enabled ?? false,
        tansho_ev_initial_bankroll_yen: config.settings.tansho_ev_initial_bankroll_yen ?? 300000,
        tansho_ev_bet_pct: config.settings.tansho_ev_bet_pct ?? 2.0,
        tansho_ev_day_pct: config.settings.tansho_ev_day_pct ?? 10.0,
        comment_a_enabled: config.settings.comment_a_enabled ?? false,
        comment_a_initial_bankroll_yen: config.settings.comment_a_initial_bankroll_yen ?? 300000,
        comment_a_bet_pct: config.settings.comment_a_bet_pct ?? 0.5,
        comment_a_day_pct: config.settings.comment_a_day_pct ?? 10.0,
        comment_a_r4_boost: config.settings.comment_a_r4_boost ?? true,
        sleeve_total_day_cap_yen: config.settings.sleeve_total_day_cap_yen ?? 0,
        sleeve_per_race_cap_yen:
          config.settings.sleeve_per_race_cap_yen ?? config.settings.per_race_max_yen ?? 5200,
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

  // ★状態バッジは「保存済みの実状態」(config) を断言する（formData=編集中の未保存状態ではない）。
  //   formData が config と食い違うときだけ「未保存」を別バッジで出す＝今動いてるか／これから変える予定かを分離。
  const savedGapEnabled = config?.settings.gap_enabled ?? false;
  const savedTanshoEvEnabled = config?.settings.tansho_ev_enabled ?? false;
  const savedCommentAEnabled = config?.settings.comment_a_enabled ?? false;
  const gapDirty = formData.gap_enabled !== savedGapEnabled;
  const tanshoEvDirty = formData.tansho_ev_enabled !== savedTanshoEvEnabled;
  const commentADirty = formData.comment_a_enabled !== savedCommentAEnabled;
  // コメＡ: 1単位額と1頭あたり額 (複2u+単1u+ワイド1u=4u / R4通過時 5u)
  const commentAUnit =
    Math.floor((formData.comment_a_initial_bankroll_yen * formData.comment_a_bet_pct) / 100 / 100) * 100;

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

      {/* ★gap単勝 本投票 (Session 176) = 隔離口座。combo とは別の自動投票枠★ */}
      <div className="p-4 rounded-lg border-2 border-amber-500/40 bg-amber-500/5">
        <div className="flex items-center justify-between mb-1">
          <label className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-amber-600" />
            逆張り単（gap単勝）自動投票・隔離口座
          </label>
          {/* 現在の状態バッジ＝保存済みの実状態を断言。未保存の変更は別バッジで明示。 */}
          <span className="flex items-center gap-1">
            <span
              className={`text-xs font-bold px-2 py-1 rounded ${
                savedGapEnabled
                  ? 'bg-green-600 text-white'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {savedGapEnabled ? '● 稼働中' : '○ 停止中'}
            </span>
            {gapDirty && (
              <span className="flex items-center gap-1 text-xs font-bold px-2 py-1 rounded bg-orange-100 text-orange-700 border border-orange-300">
                <AlertTriangle className="h-3 w-3" />
                未保存（保存で{formData.gap_enabled ? '稼働' : '停止'}）
              </span>
            )}
          </span>
        </div>
        {/* 2ボタン選択式（選ばれている方がハイライト＝現状態。押した方に切り替わる） */}
        <div className="flex gap-2 mb-2">
          <Button
            type="button"
            size="sm"
            variant={formData.gap_enabled ? 'default' : 'outline'}
            onClick={() => setFormData({ ...formData, gap_enabled: true })}
            className="flex-1"
          >
            有効にする
          </Button>
          <Button
            type="button"
            size="sm"
            variant={!formData.gap_enabled ? 'default' : 'outline'}
            onClick={() => setFormData({ ...formData, gap_enabled: false })}
            className="flex-1"
          >
            無効にする
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          市場較正監査で確定したエッジ「gap≥5単勝×(未勝利/条件/重賞)」を単勝で買う収益源枠。
          <strong>combo（三連単フォメ）とは別口座</strong>で、上の日次上限とも分離されています。
          「有効にする」を選んで<strong>下の「保存」を押すと</strong>、次の開催から稼働します。
        </p>
        <div className={formData.gap_enabled ? 'space-y-3' : 'space-y-3 opacity-50'}>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">初期残高（隔離口座）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="10000"
                value={formData.gap_initial_bankroll_yen}
                disabled={!formData.gap_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, gap_initial_bankroll_yen: parseInt(e.target.value) || 0 })
                }
                className="flex-1 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground w-8">円</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              残高 = 初期 + 実現損益。比例サイジングの素になります。
            </p>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">1点の比率（残高×%）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="0.1"
                value={formData.gap_bet_pct}
                disabled={!formData.gap_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, gap_bet_pct: parseFloat(e.target.value) || 0 })
                }
                className="w-24 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground">%</span>
              <span className="text-lg font-bold text-amber-600 ml-auto">
                → 1点 ¥{(Math.floor((formData.gap_initial_bankroll_yen * formData.gap_bet_pct) / 100 / 100) * 100).toLocaleString()}
              </span>
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">日次上限（残高×%・暴走ガード）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="0.5"
                value={formData.gap_day_pct}
                disabled={!formData.gap_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, gap_day_pct: parseFloat(e.target.value) || 0 })
                }
                className="w-24 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground">%</span>
              <span className="text-lg font-bold text-amber-600 ml-auto">
                → 日次 ¥{(Math.floor((formData.gap_initial_bankroll_yen * formData.gap_day_pct) / 100 / 100) * 100).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ★本命EV単 本投票 (Session 177) = 2本目スリーブ・隔離口座★ */}
      <div className="p-4 rounded-lg border-2 border-sky-500/40 bg-sky-500/5">
        <div className="flex items-center justify-between mb-1">
          <label className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-sky-600" />
            本命EV単 自動投票・隔離口座
          </label>
          <span className="flex items-center gap-1">
            <span
              className={`text-xs font-bold px-2 py-1 rounded ${
                savedTanshoEvEnabled
                  ? 'bg-green-600 text-white'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {savedTanshoEvEnabled ? '● 稼働中' : '○ 停止中'}
            </span>
            {tanshoEvDirty && (
              <span className="flex items-center gap-1 text-xs font-bold px-2 py-1 rounded bg-orange-100 text-orange-700 border border-orange-300">
                <AlertTriangle className="h-3 w-3" />
                未保存（保存で{formData.tansho_ev_enabled ? '稼働' : '停止'}）
              </span>
            )}
          </span>
        </div>
        <div className="flex gap-2 mb-2">
          <Button
            type="button"
            size="sm"
            variant={formData.tansho_ev_enabled ? 'default' : 'outline'}
            onClick={() => setFormData({ ...formData, tansho_ev_enabled: true })}
            className="flex-1"
          >
            有効にする
          </Button>
          <Button
            type="button"
            size="sm"
            variant={!formData.tansho_ev_enabled ? 'default' : 'outline'}
            onClick={() => setFormData({ ...formData, tansho_ev_enabled: false })}
            className="flex-1"
          >
            無効にする
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          AIの本命(勝率1位)を、市場が過小評価していて(gap≥3)・期待値が高く(EV≥1.3)・接戦のときだけ
          単勝1点で買う本命妙味の収益源枠（推奨馬券画面の「本命EV単」と同条件）。
          <strong>逆張り単とは別口座</strong>です。「有効にする」を選んで<strong>保存</strong>すると次の開催から稼働します。
        </p>
        <div className={formData.tansho_ev_enabled ? 'space-y-3' : 'space-y-3 opacity-50'}>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">初期残高（隔離口座）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="10000"
                value={formData.tansho_ev_initial_bankroll_yen}
                disabled={!formData.tansho_ev_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, tansho_ev_initial_bankroll_yen: parseInt(e.target.value) || 0 })
                }
                className="flex-1 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground w-8">円</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              残高 = 初期 + 実現損益。比例サイジングの素になります。
            </p>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">1点の比率（残高×%）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="0.1"
                value={formData.tansho_ev_bet_pct}
                disabled={!formData.tansho_ev_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, tansho_ev_bet_pct: parseFloat(e.target.value) || 0 })
                }
                className="w-24 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground">%</span>
              <span className="text-lg font-bold text-sky-600 ml-auto">
                → 1点 ¥{(Math.floor((formData.tansho_ev_initial_bankroll_yen * formData.tansho_ev_bet_pct) / 100 / 100) * 100).toLocaleString()}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              ※ 案A（二段化）では各スリーブは自分の比率で満額買います。同一レースで両スリーブが重なって
              合算が下の<strong>「レース合算上限」¥{formData.sleeve_per_race_cap_yen.toLocaleString()}</strong>を
              超えるときだけ、低優先（逆張り単）からレース単位で見送ります。
            </p>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">日次上限（残高×%・暴走ガード）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="0.5"
                value={formData.tansho_ev_day_pct}
                disabled={!formData.tansho_ev_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, tansho_ev_day_pct: parseFloat(e.target.value) || 0 })
                }
                className="w-24 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground">%</span>
              <span className="text-lg font-bold text-sky-600 ml-auto">
                → 日次 ¥{(Math.floor((formData.tansho_ev_initial_bankroll_yen * formData.tansho_ev_day_pct) / 100 / 100) * 100).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ★コメＡ3点セット 本投票 (Session 189) = 3本目スリーブ・隔離口座★ */}
      <div className="p-4 rounded-lg border-2 border-violet-500/40 bg-violet-500/5">
        <div className="flex items-center justify-between mb-1">
          <label className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-violet-600" />
            深読み三点（コメＡ3点セット）自動投票・隔離口座
          </label>
          <span className="flex items-center gap-1">
            <span
              className={`text-xs font-bold px-2 py-1 rounded ${
                savedCommentAEnabled
                  ? 'bg-green-600 text-white'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {savedCommentAEnabled ? '● 稼働中' : '○ 停止中'}
            </span>
            {commentADirty && (
              <span className="flex items-center gap-1 text-xs font-bold px-2 py-1 rounded bg-orange-100 text-orange-700 border border-orange-300">
                <AlertTriangle className="h-3 w-3" />
                未保存（保存で{formData.comment_a_enabled ? '稼働' : '停止'}）
              </span>
            )}
          </span>
        </div>
        <div className="flex gap-2 mb-2">
          <Button
            type="button"
            size="sm"
            variant={formData.comment_a_enabled ? 'default' : 'outline'}
            onClick={() => setFormData({ ...formData, comment_a_enabled: true })}
            className="flex-1"
          >
            有効にする
          </Button>
          <Button
            type="button"
            size="sm"
            variant={!formData.comment_a_enabled ? 'default' : 'outline'}
            onClick={() => setFormData({ ...formData, comment_a_enabled: false })}
            className="flex-1"
          >
            無効にする
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          競馬新聞の関係者コメントをAI（ローカルLLM）が行間まで深読みし、高確信で拾った人気薄「Ａ印」を
          <strong>複勝2：単勝1：ワイド(×ML本命)1</strong> の3点セットで買う収益源枠
          （実払戻バックテスト 2026年 ROI 167.6%・約4頭/開催日）。
          <strong>逆張り単・本命EV単とは別口座</strong>です。「有効にする」を選んで<strong>保存</strong>すると次の開催から稼働します。
          残高が初期の<strong>50%を割ると自動停止</strong>します（ハードDDストップ・再開は原因究明後に手動で）。
        </p>
        <div className={formData.comment_a_enabled ? 'space-y-3' : 'space-y-3 opacity-50'}>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">初期残高（隔離口座）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="10000"
                value={formData.comment_a_initial_bankroll_yen}
                disabled={!formData.comment_a_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, comment_a_initial_bankroll_yen: parseInt(e.target.value) || 0 })
                }
                className="flex-1 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground w-8">円</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              残高 = 初期 + 実現損益。比例サイジングの素になります。
            </p>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">1単位の比率（残高×%）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="0.1"
                value={formData.comment_a_bet_pct}
                disabled={!formData.comment_a_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, comment_a_bet_pct: parseFloat(e.target.value) || 0 })
                }
                className="w-24 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground">%</span>
              <span className="text-lg font-bold text-violet-600 ml-auto">
                → 1単位 ¥{commentAUnit.toLocaleString()}（1頭 ¥{(commentAUnit * 4).toLocaleString()}〜{(commentAUnit * 5).toLocaleString()}）
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              1頭あたり = 複勝2単位＋単勝1単位＋ワイド1単位（R4通過時は複勝3単位）。
            </p>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">日次上限（残高×%・暴走ガード）</label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                step="0.5"
                value={formData.comment_a_day_pct}
                disabled={!formData.comment_a_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, comment_a_day_pct: parseFloat(e.target.value) || 0 })
                }
                className="w-24 text-right text-lg font-bold h-12"
              />
              <span className="text-base text-muted-foreground">%</span>
              <span className="text-lg font-bold text-violet-600 ml-auto">
                → 日次 ¥{(Math.floor((formData.comment_a_initial_bankroll_yen * formData.comment_a_day_pct) / 100 / 100) * 100).toLocaleString()}
              </span>
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">
              R4増額（モデルEVゲート通過のＡ印は複勝を2→3単位に増額）
            </label>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant={formData.comment_a_r4_boost ? 'default' : 'outline'}
                disabled={!formData.comment_a_enabled}
                onClick={() => setFormData({ ...formData, comment_a_r4_boost: true })}
                className="flex-1"
              >
                有効（推奨）
              </Button>
              <Button
                type="button"
                size="sm"
                variant={!formData.comment_a_r4_boost ? 'default' : 'outline'}
                disabled={!formData.comment_a_enabled}
                onClick={() => setFormData({ ...formData, comment_a_r4_boost: false })}
                className="flex-1"
              >
                無効（全頭同額）
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* ★レース合算上限 (案A・Session 178) = 1レースに自動投票する最大額(両スリーブ合算)★ */}
      <div className="p-4 rounded-lg border border-border bg-muted/20">
        <label className="text-xs text-muted-foreground block mb-1">
          レース合算上限（1レースの自動投票 最大額・全スリーブ合算 / runner番人と共通）
        </label>
        <div className="flex items-center gap-3">
          <Input
            type="number"
            step="1000"
            value={formData.sleeve_per_race_cap_yen}
            onChange={(e) =>
              setFormData({ ...formData, sleeve_per_race_cap_yen: parseInt(e.target.value) || 0 })
            }
            className="flex-1 text-right text-lg font-bold h-12"
          />
          <span className="text-base text-muted-foreground w-8">円</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          各スリーブは自分の比率で満額を買い、同一レースで重なって合算がこの額を超えるときだけ
          <strong>優先度の低いスリーブ（コメＡ → 逆張り単の順）からレース単位で見送り</strong>ます。
          全部を満額で通すには
          本命EV単 ¥{(Math.floor((formData.tansho_ev_initial_bankroll_yen * formData.tansho_ev_bet_pct) / 100 / 100) * 100).toLocaleString()}
          ＋逆張り単 ¥{(Math.floor((formData.gap_initial_bankroll_yen * formData.gap_bet_pct) / 100 / 100) * 100).toLocaleString()}
          ＋コメＡ ¥{(commentAUnit * 5).toLocaleString()}
          ＝¥{(
            Math.floor((formData.tansho_ev_initial_bankroll_yen * formData.tansho_ev_bet_pct) / 100 / 100) * 100 +
            Math.floor((formData.gap_initial_bankroll_yen * formData.gap_bet_pct) / 100 / 100) * 100 +
            commentAUnit * 5
          ).toLocaleString()} 以上が必要です。
          <strong>保存すると runner の per_race_max_yen にも同じ額が入ります（一致必須）。</strong>
        </p>
      </div>

      {/* ★スリーブ全体の日次純投資ハード上限 (Session 177・複数スリーブ運用時の合算cap)★ */}
      <div className="p-4 rounded-lg border border-border bg-muted/20">
        <label className="text-xs text-muted-foreground block mb-1">
          スリーブ全体の日次上限（逆張り単＋本命EV単の合算ハード上限）
        </label>
        <div className="flex items-center gap-3">
          <Input
            type="number"
            step="10000"
            value={formData.sleeve_total_day_cap_yen}
            onChange={(e) =>
              setFormData({ ...formData, sleeve_total_day_cap_yen: parseInt(e.target.value) || 0 })
            }
            className="flex-1 text-right text-lg font-bold h-12"
          />
          <span className="text-base text-muted-foreground w-8">円</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          <strong>0 = 自動</strong>（各スリーブの日次上限の合計）。複数スリーブの1日の純投資がこの額を超えないよう、
          優先度の低いスリーブ（逆張り単）から脚を落とします。
        </p>
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
    return (
      <div className="max-h-[70vh] overflow-y-auto pr-1">
        {formContent}
      </div>
    );
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
