'use client';

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  ActionButton,
  DateSelector,
  DateRangeSelector,
  LogViewer,
  StatusBadge,
  DataStatusCard,
  ValidationResultsCard,
  SystemHealthCard,
  type LogEntry,
  type ExecutionStatus,
} from '@/components/admin';
import { ACTIONS, type ActionType } from '@/lib/admin/commands';
import { ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

// 簡易UUID生成（crypto.randomUUID が使えない環境用フォールバック）
function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // フォールバック: タイムスタンプ + ランダム文字列
  return `${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 11)}`;
}

// 日付モード
type DateMode = 'single' | 'range';

export default function AdminPage() {
  // 今日の日付をデフォルトに
  const today = new Date();
  const defaultDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  // 日付モード（単一 or 範囲）
  const [dateMode, setDateMode] = useState<DateMode>('single');
  const [selectedDate, setSelectedDate] = useState(defaultDate);
  const [status, setStatus] = useState<ExecutionStatus>('idle');
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [raceFromInput, setRaceFromInput] = useState('');
  const [raceToInput, setRaceToInput] = useState('');

  // 日付範囲
  const getDefaultDateRange = () => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 7); // 1週間前
    return {
      start: `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`,
      end: `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`,
    };
  };
  const defaultRange = getDefaultDateRange();
  const [rangeStartDate, setRangeStartDate] = useState(defaultRange.start);
  const [rangeEndDate, setRangeEndDate] = useState(defaultRange.end);
  
  // インデックス再構築
  const [isRebuildingIndex, setIsRebuildingIndex] = useState(false);

  // 調教サマリー一括生成
  const [isGeneratingTraining, setIsGeneratingTraining] = useState(false);

  // JRDBダウンロード
  const [isDownloadingJrdb, setIsDownloadingJrdb] = useState(false);

  // 特別登録データ生成
  const [isGeneratingRegistration, setIsGeneratingRegistration] = useState(false);

  // データ品質リフレッシュ用
  const [dataQualityRefreshKey, setDataQualityRefreshKey] = useState(0);

  // 折りたたみ状態
  const [isToolsOpen, setIsToolsOpen] = useState(false);
  const [isSystemStatusOpen, setIsSystemStatusOpen] = useState(false);

  const addLog = useCallback((entry: Omit<LogEntry, 'id'>) => {
    setLogs((prev) => [
      ...prev,
      { ...entry, id: generateId() },
    ]);
  }, []);

  const refreshDataQuality = useCallback(() => {
    setDataQualityRefreshKey((prev) => prev + 1);
  }, []);

  // インデックス再構築
  const rebuildIndex = useCallback(async () => {
    setIsRebuildingIndex(true);
    addLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: 'レース日付インデックスを再構築中...',
    });

    try {
      const response = await fetch('/api/admin/rebuild-index', { method: 'POST' });
      const result = await response.json();
      
      if (result.success) {
        addLog({
          timestamp: new Date().toISOString(),
          level: 'success',
          message: result.message,
        });
        refreshDataQuality();
      } else {
        addLog({
          timestamp: new Date().toISOString(),
          level: 'error',
          message: `インデックス再構築エラー: ${result.error || result.details}`,
        });
      }
    } catch (error) {
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `インデックス再構築エラー: ${error}`,
      });
    } finally {
      setIsRebuildingIndex(false);
    }
  }, [addLog, refreshDataQuality]);

  // 調教サマリー一括生成
  const batchGenerateTraining = useCallback(async () => {
    setIsGeneratingTraining(true);
    setStatus('running');
    setCurrentAction('調教サマリー一括生成');
    addLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: '🏋️ 調教サマリー一括生成 開始...',
    });

    try {
      const response = await fetch('/api/admin/batch-training-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}), // 全日付対象
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'start' || data.type === 'log' || data.type === 'progress') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: data.level || 'info',
                  message: data.message,
                });
              } else if (data.type === 'complete') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: 'success',
                  message: data.message,
                });
                setStatus('success');
              } else if (data.type === 'error') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: 'error',
                  message: data.message,
                });
                setStatus('error');
              }
            } catch (e) {
              console.error('SSE parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `調教サマリー一括生成エラー: ${error}`,
      });
      setStatus('error');
    } finally {
      setIsGeneratingTraining(false);
      setCurrentAction(null);
    }
  }, [addLog]);

  // 特別登録データ生成
  const generateRegistration = useCallback(async () => {
    setIsGeneratingRegistration(true);
    setStatus('running');
    setCurrentAction('特別登録データ生成');
    addLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: '特別登録データ生成 開始...',
    });

    try {
      const response = await fetch('/api/admin/generate-registration', {
        method: 'POST',
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'start' || data.type === 'log' || data.type === 'progress') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: data.level || 'info',
                  message: data.message,
                });
              } else if (data.type === 'complete') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: 'success',
                  message: data.message,
                });
                setStatus('success');
              } else if (data.type === 'error') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: 'error',
                  message: data.message,
                });
                setStatus('error');
              }
            } catch (e) {
              console.error('SSE parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `特別登録データ生成エラー: ${error}`,
      });
      setStatus('error');
    } finally {
      setIsGeneratingRegistration(false);
      setCurrentAction(null);
    }
  }, [addLog]);

  // JRDBデータダウンロード＆統合
  const downloadJrdb = useCallback(async () => {
    setIsDownloadingJrdb(true);
    setStatus('running');
    setCurrentAction('JRDB DL＆統合');

    // 対象日: selectedDate + 翌日（週末レース両日対応）
    const d = new Date(selectedDate + 'T00:00:00');
    const d2 = new Date(d);
    d2.setDate(d2.getDate() + 1);
    const fmt = (dt: Date) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
    const dates = [fmt(d), fmt(d2)];

    addLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `JRDB データ統合 開始 (DL → Index → Race JSON ${dates.join(', ')})...`,
    });

    try {
      const response = await fetch('/api/admin/jrdb-download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dates }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'start' || data.type === 'log' || data.type === 'progress') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: data.level || 'info',
                  message: data.message,
                });
              } else if (data.type === 'complete') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: 'success',
                  message: data.message,
                });
                setStatus('success');
              } else if (data.type === 'error') {
                addLog({
                  timestamp: new Date().toISOString(),
                  level: 'error',
                  message: data.message,
                });
                setStatus('error');
              }
            } catch (e) {
              console.error('SSE parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `JRDBダウンロードエラー: ${error}`,
      });
      setStatus('error');
    } finally {
      setIsDownloadingJrdb(false);
      setCurrentAction(null);
    }
  }, [addLog]);

  const executeAction = async (action: ActionType) => {
    const actionConfig = ACTIONS.find((a) => a.id === action);
    if (!actionConfig) return;

    setStatus('running');
    setCurrentAction(actionConfig.label);
    
    // 日付モードに応じたログメッセージ
    const dateInfo = dateMode === 'single' 
      ? `対象: ${selectedDate}` 
      : `対象: ${rangeStartDate} 〜 ${rangeEndDate}`;
    const raceFromRaw = dateMode === 'single' && raceFromInput ? Number(raceFromInput) : undefined;
    const raceToRaw = dateMode === 'single' && raceToInput ? Number(raceToInput) : undefined;
    const raceFrom = raceFromRaw && raceToRaw && raceFromRaw > raceToRaw ? raceToRaw : raceFromRaw;
    const raceTo = raceFromRaw && raceToRaw && raceFromRaw > raceToRaw ? raceFromRaw : raceToRaw;
    const shouldApplyRaceFilter = ['paddok', 'seiseki', 'batch_morning', 'batch_after_race'].includes(action);
    const raceInfo = shouldApplyRaceFilter && (raceFrom || raceTo)
      ? `, ${raceFrom ?? 1}R〜${raceTo ?? 12}R`
      : '';
    
    addLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `${actionConfig.icon} ${actionConfig.label} 開始... (${dateInfo}${raceInfo})`,
    });

    try {
      // 日付モードに応じたリクエストボディ
      const requestBody = dateMode === 'single'
        ? { action, date: selectedDate }
        : { action, startDate: rangeStartDate, endDate: rangeEndDate, isRangeAction: true };

      if ((raceFrom || raceTo) && shouldApplyRaceFilter) {
        Object.assign(requestBody, { raceFrom, raceTo });
      }

      const response = await fetch('/api/admin/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      // SSEストリームを読み取り
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              handleSSEEvent(data, action);
            } catch (e) {
              console.error('SSE parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `エラー: ${errorMessage}`,
      });
      setStatus('error');
    }

    setCurrentAction(null);
  };

  const handleSSEEvent = (
    data: { type: string; [key: string]: unknown },
    actionId: ActionType
  ) => {
    switch (data.type) {
      case 'log':
        addLog({
          timestamp: data.timestamp as string,
          level: data.level as LogEntry['level'],
          message: data.message as string,
        });
        break;

      case 'progress':
        addLog({
          timestamp: new Date().toISOString(),
          level: 'info',
          message: `[${data.current}/${data.total}] ${data.command}`,
        });
        break;

      case 'complete':
        addLog({
          timestamp: new Date().toISOString(),
          level: 'success',
          message: data.message as string,
        });
        setStatus('success');
        if (dataRefreshActions.includes(actionId)) {
          refreshDataQuality();
        }
        break;

      case 'error':
        addLog({
          timestamp: new Date().toISOString(),
          level: 'error',
          message: data.message as string,
        });
        setStatus('error');
        break;
    }
  };

  const clearLogs = () => {
    setLogs([]);
    setStatus('idle');
  };

  const isRunning = status === 'running';

  // カテゴリ別にアクションを分類

  // UIラベル上書き（commands.tsのidはAPIルーティングと連動するため変更しない）
  const labelOverrides: Record<string, { label: string; description: string }> = {
    batch_prepare: { label: '基本情報登録', description: '日程→出馬表・調教→レースJSON構築（前日夜実行）' },
    batch_morning: { label: '直前情報登録', description: 'パドック情報を取得（レース直前に実行）' },
    batch_after_race: { label: '成績情報登録', description: 'レース結果（着順・タイム）を取得' },
    v4_pipeline: { label: 'データ前処理', description: 'レースJSON構築→調教補強（スクレイプなし・データ再処理用）' },
    v4_predict: { label: 'ML予測', description: 'MLモデルで予測を再生成（最新オッズ反映）' },
    vb_refresh: { label: 'VB/買い目抽出', description: '最新オッズでValueBet判定・買い目を再生成' },
  };

  // データ準備セクション
  const dataPrepActions = ACTIONS.filter((a) =>
    ['batch_prepare', 'batch_morning', 'batch_after_race'].includes(a.id)
  );
  const dataPrepSecondary = ACTIONS.filter((a) =>
    ['sunpyo_update'].includes(a.id)
  );

  // AI分析セクション（順序を明示的に制御: 前処理→予測→買い目）
  const aiAnalysisOrder: ActionType[] = ['v4_pipeline', 'v4_predict', 'vb_refresh'];
  const aiAnalysisActions = aiAnalysisOrder
    .map((id) => ACTIONS.find((a) => a.id === id))
    .filter((a): a is NonNullable<typeof a> => a != null);

  const scrapeActions = ACTIONS.filter((a) => a.category === 'fetch');
  const stepActions = ACTIONS.filter((a) =>
    ['v4_build_race', 'v4_predict'].includes(a.id)
  );
  const indexActions = ACTIONS.filter((a) =>
    ['build_horse_name_index', 'build_trainer_index'].includes(a.id)
  );
  const analysisActions = ACTIONS.filter((a) => a.category === 'analysis');
  // データリフレッシュが必要なアクション
  const dataRefreshActions: ActionType[] = [
    'batch_prepare', 'batch_morning', 'batch_after_race',
    'v4_pipeline', 'v4_predict', 'vb_refresh',
  ];

  return (
    <div className="container py-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          📊 データ登録
        </h1>
        <StatusBadge status={status} />
      </div>

      {/* 日付設定（単一/範囲切り替え） */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            📅 日付設定
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* モード切り替えタブ */}
          <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
            <button
              onClick={() => setDateMode('single')}
              disabled={isRunning}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                dateMode === 'single'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              } disabled:opacity-50`}
            >
              📍 単一日付
            </button>
            <button
              onClick={() => setDateMode('range')}
              disabled={isRunning}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                dateMode === 'range'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              } disabled:opacity-50`}
            >
              📆 期間範囲
            </button>
          </div>

          {/* 日付選択UI */}
          {dateMode === 'single' ? (
            <DateSelector
              date={selectedDate}
              onChange={setSelectedDate}
              disabled={isRunning}
            />
          ) : (
            <DateRangeSelector
              startDate={rangeStartDate}
              endDate={rangeEndDate}
              onStartDateChange={setRangeStartDate}
              onEndDateChange={setRangeEndDate}
              disabled={isRunning}
            />
          )}

          {/* 現在の選択表示 */}
          <div className="text-sm text-muted-foreground flex items-center gap-2">
            <span className="text-lg">🎯</span>
            <span>
              {dateMode === 'single' 
                ? `対象日: ${selectedDate}` 
                : `対象期間: ${rangeStartDate} 〜 ${rangeEndDate}`}
            </span>
          </div>

          {/* 当日取得オプション */}
          <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
            <div className="text-sm font-medium flex items-center gap-2">
              ⏱ 当日取得オプション
              <span className="text-xs font-normal text-muted-foreground">（パドック/成績/レース後更新）</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-sm text-muted-foreground">開始レース</label>
              <input
                type="number"
                min={1}
                max={12}
                placeholder="例: 5"
                value={raceFromInput}
                onChange={(event) => setRaceFromInput(event.target.value)}
                disabled={isRunning || dateMode === 'range'}
                className="h-8 w-24 rounded-md border bg-background px-2 text-sm"
              />
              <span className="text-sm text-muted-foreground">R 〜</span>
              <input
                type="number"
                min={1}
                max={12}
                placeholder="例: 12"
                value={raceToInput}
                onChange={(event) => setRaceToInput(event.target.value)}
                disabled={isRunning || dateMode === 'range'}
                className="h-8 w-24 rounded-md border bg-background px-2 text-sm"
              />
              <span className="text-sm text-muted-foreground">R まで</span>
              <button
                type="button"
                onClick={() => {
                  setRaceFromInput('');
                  setRaceToInput('');
                }}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                disabled={isRunning || dateMode === 'range'}
              >
                クリア
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              単一日付のみ有効。空欄の場合は全レースを取得します。
            </p>
          </div>
        </CardContent>
      </Card>

      {/* データ準備 */}
      <Card className="mb-6 border-2 border-indigo-200 dark:border-indigo-800 shadow-lg">
        <CardHeader className="pb-3 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950 dark:to-purple-950">
          <CardTitle className="text-xl flex items-center gap-2">
            <span className="text-2xl">📋</span>
            <span>データ準備</span>
            <span className="ml-auto text-xs font-normal text-muted-foreground">スクレイプ→JSON構築</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6 space-y-4">
          {/* メインワークフロー */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {dataPrepActions.map((action) => {
              const override = labelOverrides[action.id];
              const label = override?.label || action.label;
              const description = override?.description || action.description;
              return (
                <ActionButton
                  key={action.id}
                  icon={action.icon}
                  label={label}
                  description={description}
                  onClick={() => executeAction(action.id)}
                  disabled={isRunning}
                  loading={isRunning && currentAction === action.label}
                  variant="batch"
                />
              );
            })}
          </div>

          <Separator />

          {/* 補助アクション */}
          <div className="grid grid-cols-1 gap-3">
            {dataPrepSecondary.map((action) => (
              <ActionButton
                key={action.id}
                icon={action.icon}
                label={action.label}
                description={action.description}
                onClick={() => executeAction(action.id)}
                disabled={isRunning}
                loading={isRunning && currentAction === action.label}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* AI分析 */}
      <Card className="mb-6 border-2 border-emerald-200 dark:border-emerald-800 shadow-lg">
        <CardHeader className="pb-3 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950">
          <CardTitle className="text-xl flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <span>AI分析</span>
            <span className="ml-auto text-xs font-normal text-muted-foreground">前処理→予測→買い目</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {aiAnalysisActions.map((action) => {
              const override = labelOverrides[action.id];
              const label = override?.label || action.label;
              const description = override?.description || action.description;
              return (
                <ActionButton
                  key={action.id}
                  icon={action.icon}
                  label={label}
                  description={description}
                  onClick={() => executeAction(action.id)}
                  disabled={isRunning}
                  loading={isRunning && currentAction === action.label}
                  variant="batch"
                />
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* ツール・システム - 折りたたみ可能 */}
      <div className="space-y-4">
        {/* ツール（個別実行・メンテナンス） */}
        <Collapsible open={isToolsOpen} onOpenChange={setIsToolsOpen}>
          <Card className="border-muted">
            <CollapsibleTrigger asChild>
              <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
                <CardTitle className="text-lg flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    🔧 ツール
                    <span className="text-xs font-normal text-muted-foreground">（個別実行・メンテナンス）</span>
                  </span>
                  {isToolsOpen ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <div className="space-y-6">
                  {/* 個別スクレイプ */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-3">
                      個別スクレイプ（keibabook）
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {scrapeActions.map((action) => (
                        <ActionButton
                          key={action.id}
                          icon={action.icon}
                          label={action.label}
                          description={action.description}
                          onClick={() => executeAction(action.id)}
                          disabled={isRunning}
                          loading={isRunning && currentAction === action.label}
                        />
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* 個別ステップ */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-3">
                      個別ステップ（部分再実行用）
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {stepActions.map((action) => (
                        <ActionButton
                          key={action.id}
                          icon={action.icon}
                          label={action.label}
                          description={action.description}
                          onClick={() => executeAction(action.id)}
                          disabled={isRunning}
                          loading={isRunning && currentAction === action.label}
                        />
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* インデックス管理 */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-3">
                      インデックス管理
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {indexActions.map((action) => (
                        <ActionButton
                          key={action.id}
                          icon={action.icon}
                          label={action.label}
                          description={action.description}
                          onClick={() => executeAction(action.id)}
                          disabled={isRunning}
                          loading={isRunning && currentAction === action.label}
                        />
                      ))}
                      {/* レース日付インデックス再構築 */}
                      <Button
                        variant="outline"
                        className="h-auto py-3 px-4 flex flex-col items-start text-left bg-background hover:bg-muted border"
                        onClick={rebuildIndex}
                        disabled={isRebuildingIndex || isRunning}
                      >
                        <div className="flex items-center gap-2 w-full">
                          <RefreshCw className={`w-5 h-5 ${isRebuildingIndex ? 'animate-spin' : ''}`} />
                          <span className="font-semibold text-sm">
                            {isRebuildingIndex ? 'レース日付インデックス再構築中...' : 'レース日付インデックス再構築'}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground mt-1">
                          新しい日程データを登録した後に実行
                        </span>
                      </Button>
                    </div>
                  </div>

                  <Separator />

                  {/* JRDBデータ */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-3">
                      JRDB データ
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button
                        variant="outline"
                        className="h-auto py-3 px-4 flex flex-col items-start text-left bg-background hover:bg-muted border"
                        onClick={downloadJrdb}
                        disabled={isDownloadingJrdb || isRunning}
                      >
                        <div className="flex items-center gap-2 w-full">
                          <span className={`text-lg ${isDownloadingJrdb ? 'animate-pulse' : ''}`}>📡</span>
                          <span className="font-semibold text-sm">
                            {isDownloadingJrdb ? 'JRDB統合中...' : 'JRDB DL＆統合'}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground mt-1">
                          DL → Index再構築 → 選択日+翌日のRace JSONにJRDB指標付与
                        </span>
                      </Button>
                    </div>
                  </div>

                  <Separator />

                  {/* 特別登録データ */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-3">
                      特別登録データ
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button
                        variant="outline"
                        className="h-auto py-3 px-4 flex flex-col items-start text-left bg-background hover:bg-muted border"
                        onClick={generateRegistration}
                        disabled={isGeneratingRegistration || isRunning}
                      >
                        <div className="flex items-center gap-2 w-full">
                          <span className={`text-lg ${isGeneratingRegistration ? 'animate-pulse' : ''}`}>📝</span>
                          <span className="font-semibold text-sm">
                            {isGeneratingRegistration ? '特別登録データ生成中...' : '特別登録データ生成'}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground mt-1">
                          MyKeibaDBから今週の特別登録馬データを取得・JSON生成
                        </span>
                      </Button>
                    </div>
                  </div>

                  <Separator />

                  {/* 調教サマリー一括生成 */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-3">
                      調教データ
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button
                        variant="outline"
                        className="h-auto py-3 px-4 flex flex-col items-start text-left bg-background hover:bg-muted border"
                        onClick={batchGenerateTraining}
                        disabled={isGeneratingTraining || isRunning}
                      >
                        <div className="flex items-center gap-2 w-full">
                          <span className={`text-lg ${isGeneratingTraining ? 'animate-pulse' : ''}`}>🏋️</span>
                          <span className="font-semibold text-sm">
                            {isGeneratingTraining ? '調教サマリー生成中...' : '調教サマリー一括生成'}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground mt-1">
                          全レース日付のtraining_summary.jsonを一括生成（前走調教表示に必要）
                        </span>
                      </Button>
                    </div>
                  </div>

                  <Separator />

                  {/* データ分析 */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-3">
                      データ分析（基準値算出・統計分析）
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {analysisActions.map((action) => (
                        <ActionButton
                          key={action.id}
                          icon={action.icon}
                          label={action.label}
                          description={action.description}
                          onClick={() => executeAction(action.id)}
                          disabled={isRunning}
                          loading={isRunning && currentAction === action.label}
                          variant="default"
                        />
                      ))}
                    </div>
                    {/* 分析結果へのリンク */}
                    <div className="mt-4 pt-4 border-t flex flex-wrap gap-4">
                      <a
                        href="/analysis/rpci"
                        className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        📊 RPCI分析 →
                      </a>
                      <a
                        href="/analysis/rating"
                        className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        📈 レイティング分析 →
                      </a>
                      <a
                        href="/analysis/idm"
                        className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        🎯 IDM分析 →
                      </a>
                      <a
                        href="/analysis/pedigree"
                        className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        🧬 血統分析 →
                      </a>
                      <a
                        href="/analysis/slow-start"
                        className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        🐌 出遅れ分析 →
                      </a>
                      <a
                        href="/analysis/ml"
                        className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        🤖 ML分析 →
                      </a>
                    </div>
                  </div>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* システム状態（データ品質・ヘルスチェック） */}
        <Collapsible open={isSystemStatusOpen} onOpenChange={setIsSystemStatusOpen}>
          <Card className="border-muted">
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer pb-3 transition-colors hover:bg-muted/50">
                <CardTitle className="flex items-center justify-between text-lg">
                  <span className="flex items-center gap-2">
                    💚 システム状態
                    <span className="text-xs font-normal text-muted-foreground">
                      （データ品質・ヘルスチェック）
                    </span>
                  </span>
                  {isSystemStatusOpen ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <div className="space-y-4">
                  <DataStatusCard
                    selectedDate={selectedDate}
                    refreshKey={dataQualityRefreshKey}
                  />
                  <Separator />
                  <ValidationResultsCard
                    selectedDate={selectedDate}
                    refreshKey={dataQualityRefreshKey}
                  />
                  <Separator />
                  <SystemHealthCard />
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      </div>

      <Separator className="my-6" />

      {/* 実行ログ */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              📋 実行ログ
            </CardTitle>
            <button
              onClick={clearLogs}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              disabled={isRunning}
            >
              クリア
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <LogViewer logs={logs} maxHeight="400px" />
        </CardContent>
      </Card>

      {/* 現在実行中の表示 */}
      {isRunning && currentAction && (
        <div className="fixed bottom-4 right-4 bg-blue-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
          <span className="animate-spin">⏳</span>
          <span>{currentAction} 実行中...</span>
        </div>
      )}
    </div>
  );
}
