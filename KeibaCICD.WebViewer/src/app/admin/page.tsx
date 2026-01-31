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
  const [trackInput, setTrackInput] = useState('');

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

  // データ品質リフレッシュ用
  const [dataQualityRefreshKey, setDataQualityRefreshKey] = useState(0);
  const [isDataQualityOpen, setIsDataQualityOpen] = useState(false);
  const [isSystemHealthOpen, setIsSystemHealthOpen] = useState(false);

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
      type: 'info',
      message: 'レース日付インデックスを再構築中...',
    });

    try {
      const response = await fetch('/api/admin/rebuild-index', { method: 'POST' });
      const result = await response.json();
      
      if (result.success) {
        addLog({
          timestamp: new Date().toISOString(),
          type: 'success',
          message: result.message,
        });
        refreshDataQuality();
      } else {
        addLog({
          timestamp: new Date().toISOString(),
          type: 'error',
          message: `インデックス再構築エラー: ${result.error || result.details}`,
        });
      }
    } catch (error) {
      addLog({
        timestamp: new Date().toISOString(),
        type: 'error',
        message: `インデックス再構築エラー: ${error}`,
      });
    } finally {
      setIsRebuildingIndex(false);
    }
  }, [addLog, refreshDataQuality]);

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
    const track = dateMode === 'single' && trackInput ? trackInput : undefined;
    const shouldApplyRaceFilter = ['paddok', 'seiseki', 'batch_after_race'].includes(action);
    const raceInfo = shouldApplyRaceFilter && (raceFrom || raceTo)
      ? `, ${raceFrom ?? 1}R〜${raceTo ?? 12}R`
      : '';
    const trackInfo = shouldApplyRaceFilter && track ? ` (${track})` : '';
    
    addLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `${actionConfig.icon} ${actionConfig.label} 開始... (${dateInfo}${raceInfo}${trackInfo})`,
    });

    try {
      // 日付モードに応じたリクエストボディ
      const requestBody = dateMode === 'single'
        ? { action, date: selectedDate }
        : { action, startDate: rangeStartDate, endDate: rangeEndDate, isRangeAction: true };

      if ((raceFrom || raceTo || track) && shouldApplyRaceFilter) {
        Object.assign(requestBody, { raceFrom, raceTo, track });
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
        if (
          ['batch_prepare', 'batch_after_race', 'integrate'].includes(actionId)
        ) {
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

  // カテゴリ別にアクションを分類（updateカテゴリは統合されたため除外）
  const fetchActions = ACTIONS.filter((a) => a.category === 'fetch');
  const generateActions = ACTIONS.filter((a) => a.category === 'generate');
  const batchActions = ACTIONS.filter((a) => a.category === 'batch');
  const analysisActions = ACTIONS.filter((a) => a.category === 'analysis');

  // 折りたたみ状態
  const [isFetchOpen, setIsFetchOpen] = useState(false);
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [isAnalysisOpen, setIsAnalysisOpen] = useState(false);

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
              <label className="text-sm text-muted-foreground ml-2">競馬場</label>
              <input
                type="text"
                placeholder="例: 中山"
                value={trackInput}
                onChange={(event) => setTrackInput(event.target.value)}
                disabled={isRunning || dateMode === 'range'}
                list="track-options"
                className="h-8 w-32 rounded-md border bg-background px-2 text-sm"
              />
              <button
                type="button"
                onClick={() => {
                  setRaceFromInput('');
                  setRaceToInput('');
                  setTrackInput('');
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
          <datalist id="track-options">
            <option value="札幌" />
            <option value="函館" />
            <option value="福島" />
            <option value="新潟" />
            <option value="東京" />
            <option value="中山" />
            <option value="中京" />
            <option value="京都" />
            <option value="阪神" />
            <option value="小倉" />
          </datalist>
        </CardContent>
      </Card>

      {/* 一括実行 - 上部に移動、強調表示 */}
      <Card className="mb-6 border-2 border-indigo-200 dark:border-indigo-800 shadow-lg">
        <CardHeader className="pb-3 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950 dark:to-purple-950">
          <CardTitle className="text-xl flex items-center gap-2">
            <span className="text-2xl">🚀</span>
            <span>一括実行</span>
            <span className="ml-auto text-xs font-normal text-muted-foreground">よく使う機能</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {batchActions.map((action) => (
              <ActionButton
                key={action.id}
                icon={action.icon}
                label={action.label}
                description={action.description}
                onClick={() => executeAction(action.id)}
                disabled={isRunning}
                loading={isRunning && currentAction === action.label}
                variant="batch"
              />
            ))}
          </div>
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* 詳細オプション - 折りたたみ可能 */}
      <div className="space-y-4">
        {/* データ取得 */}
        <Collapsible open={isFetchOpen} onOpenChange={setIsFetchOpen}>
          <Card className="border-muted">
            <CollapsibleTrigger asChild>
              <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
                <CardTitle className="text-lg flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    📥 データ取得
                    <span className="text-xs font-normal text-muted-foreground">（個別実行）</span>
                  </span>
                  {isFetchOpen ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {fetchActions.map((action) => (
                    <ActionButton
                      key={action.id}
                      icon={action.icon}
                      label={action.label}
                      description={action.description}
                      onClick={() => executeAction(action.id)}
                      disabled={isRunning}
                      loading={isRunning && currentAction === action.label}
                      variant={action.id === 'paddok' || action.id === 'seiseki' ? 'primary' : 'default'}
                    />
                  ))}
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* データ統合・生成 */}
        <Collapsible open={isGenerateOpen} onOpenChange={setIsGenerateOpen}>
          <Card className="border-muted">
            <CollapsibleTrigger asChild>
              <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
                <CardTitle className="text-lg flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    📝 データ統合・生成
                    <span className="text-xs font-normal text-muted-foreground">（個別実行）</span>
                  </span>
                  {isGenerateOpen ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {generateActions.map((action) => (
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
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* データ分析 */}
        <Collapsible open={isAnalysisOpen} onOpenChange={setIsAnalysisOpen}>
          <Card className="border-muted">
            <CollapsibleTrigger asChild>
              <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
                <CardTitle className="text-lg flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    📊 データ分析
                    <span className="text-xs font-normal text-muted-foreground">（基準値算出・統計分析）</span>
                  </span>
                  {isAnalysisOpen ? (
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
                  <div className="text-sm text-muted-foreground mb-2">
                    JRA-VANデータから統計分析を実行し、基準値を更新します。
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
                      📊 RPCI分析結果 →
                    </a>
                    <a
                      href="/analysis/rating"
                      className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      📈 レイティング分析結果 →
                    </a>
                  </div>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* データ品質セクション */}
        <Collapsible open={isDataQualityOpen} onOpenChange={setIsDataQualityOpen}>
          <Card className="border-muted">
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer pb-3 transition-colors hover:bg-muted/50">
                <CardTitle className="flex items-center justify-between text-lg">
                  <span className="flex items-center gap-2">
                    📊 データ品質
                    <span className="text-xs font-normal text-muted-foreground">
                      （データ状態確認）
                    </span>
                  </span>
                  {isDataQualityOpen ? (
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
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* システム状態セクション */}
        <Collapsible open={isSystemHealthOpen} onOpenChange={setIsSystemHealthOpen}>
          <Card className="border-muted">
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer pb-3 transition-colors hover:bg-muted/50">
                <CardTitle className="flex items-center justify-between text-lg">
                  <span className="flex items-center gap-2">
                    💚 システム状態
                    <span className="text-xs font-normal text-muted-foreground">
                      （ヘルスチェック）
                    </span>
                  </span>
                  {isSystemHealthOpen ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <SystemHealthCard />
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      </div>

      <Separator className="my-6" />

      {/* システム管理 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            ⚙️ システム管理
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={rebuildIndex}
              disabled={isRebuildingIndex || isRunning}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isRebuildingIndex ? 'animate-spin' : ''}`} />
              {isRebuildingIndex ? 'インデックス再構築中...' : 'インデックス再構築'}
            </Button>
            <span className="text-sm text-muted-foreground self-center">
              新しい日程データを登録した後に実行してください
            </span>
          </div>
        </CardContent>
      </Card>

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
