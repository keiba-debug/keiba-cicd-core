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
  type LogEntry,
  type ExecutionStatus,
} from '@/components/admin';
import { ACTIONS, type ActionType } from '@/lib/admin/commands';
import { ChevronDown, ChevronUp, ClipboardCopy, Download, Activity, Save } from 'lucide-react';

// 調教サマリーの型
interface TrainingSummary {
  horseName: string;
  kettoNum: string;
  trainerName: string;
  lapRank: string;
  timeRank: string;
  detail: string;
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

  const addLog = useCallback((entry: Omit<LogEntry, 'id'>) => {
    setLogs((prev) => [
      ...prev,
      { ...entry, id: crypto.randomUUID() },
    ]);
  }, []);

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
              handleSSEEvent(data);
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

  const handleSSEEvent = (data: { type: string; [key: string]: unknown }) => {
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

  // 折りたたみ状態
  const [isFetchOpen, setIsFetchOpen] = useState(false);
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [isTrainingOpen, setIsTrainingOpen] = useState(true);

  // 調教データ管理
  const [trainingDate, setTrainingDate] = useState(defaultDate);
  const [trainingSummaries, setTrainingSummaries] = useState<TrainingSummary[]>([]);
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [trainingRanges, setTrainingRanges] = useState<{
    finalStart: string;
    finalEnd: string;
    weekAgoStart: string;
    weekAgoEnd: string;
  } | null>(null);

  // 調教サマリー取得
  const fetchTrainingSummary = async () => {
    setTrainingLoading(true);
    setTrainingError(null);
    setTrainingSummaries([]);
    setTrainingRanges(null);

    try {
      const dateStr = trainingDate.replace(/-/g, '');
      const response = await fetch(`/api/training/summary?date=${dateStr}`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setTrainingSummaries(data.summaries || []);
      setTrainingRanges(data.ranges || null);
      
      addLog({
        timestamp: new Date().toISOString(),
        level: 'success',
        message: `調教サマリー取得完了: ${data.count}件`,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      setTrainingError(errorMessage);
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `調教サマリー取得エラー: ${errorMessage}`,
      });
    } finally {
      setTrainingLoading(false);
    }
  };

  // クリップボードにコピー
  const copyToClipboard = async (type: 'lap' | 'time' | 'detail') => {
    if (trainingSummaries.length === 0) return;

    let text = '';
    switch (type) {
      case 'lap':
        text = trainingSummaries
          .filter(s => s.lapRank)
          .map(s => `${s.horseName}\t${s.lapRank}`)
          .join('\n');
        break;
      case 'time':
        text = trainingSummaries
          .filter(s => s.timeRank)
          .map(s => `${s.horseName}\t${s.timeRank}`)
          .join('\n');
        break;
      case 'detail':
        text = trainingSummaries
          .filter(s => s.detail)
          .map(s => `${s.horseName}\t${s.detail}`)
          .join('\n');
        break;
    }

    try {
      await navigator.clipboard.writeText(text);
      addLog({
        timestamp: new Date().toISOString(),
        level: 'success',
        message: `クリップボードにコピーしました（${type}）`,
      });
    } catch (error) {
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `クリップボードへのコピーに失敗しました`,
      });
    }
  };

  // TSVダウンロード
  const downloadTsv = () => {
    if (trainingSummaries.length === 0) return;

    const header = '馬名\t調教師\t調教ラップ\t調教タイム\t調教詳細';
    const rows = trainingSummaries.map(s => 
      `${s.horseName}\t${s.trainerName}\t${s.lapRank}\t${s.timeRank}\t${s.detail}`
    );
    const tsv = [header, ...rows].join('\r\n');
    
    const blob = new Blob([tsv], { type: 'text/tab-separated-values; charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `training_${trainingDate.replace(/-/g, '')}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    addLog({
      timestamp: new Date().toISOString(),
      level: 'success',
      message: `TSVファイルをダウンロードしました`,
    });
  };

  // 調教サマリーをdataフォルダに保存
  const saveTrainingSummary = async () => {
    if (trainingSummaries.length === 0) {
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: 'サマリーを先に生成してください',
      });
      return;
    }

    try {
      const dateStr = trainingDate.replace(/-/g, '');
      const response = await fetch(`/api/training/save?date=${dateStr}`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      addLog({
        timestamp: new Date().toISOString(),
        level: 'success',
        message: `保存しました: ${data.path} (${data.count}件)`,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: `保存に失敗しました: ${errorMessage}`,
      });
    }
  };

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

      {/* 調教データ管理 */}
      <Collapsible open={isTrainingOpen} onOpenChange={setIsTrainingOpen}>
        <Card className="mb-6 border-2 border-emerald-200 dark:border-emerald-800">
          <CollapsibleTrigger asChild>
            <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950">
              <CardTitle className="text-xl flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Activity className="h-6 w-6" />
                  調教データ管理
                  <span className="text-xs font-normal text-muted-foreground ml-2">TARGETから直接取得</span>
                </span>
                {isTrainingOpen ? (
                  <ChevronUp className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                )}
              </CardTitle>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="pt-4 space-y-4">
              {/* 日付選択 */}
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">レース開催日:</span>
                  <input
                    type="date"
                    value={trainingDate}
                    onChange={(e) => setTrainingDate(e.target.value)}
                    disabled={trainingLoading}
                    aria-label="レース開催日"
                    className="h-9 rounded-md border bg-background px-3 text-sm"
                  />
                </div>
                <button
                  onClick={fetchTrainingSummary}
                  disabled={trainingLoading}
                  className="h-9 px-4 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2 text-sm font-medium transition-colors"
                >
                  {trainingLoading ? (
                    <>
                      <span className="animate-spin">⏳</span>
                      取得中...
                    </>
                  ) : (
                    <>
                      <Activity className="h-4 w-4" />
                      サマリー生成
                    </>
                  )}
                </button>
              </div>

              {/* 日付範囲表示 */}
              {trainingRanges && (
                <div className="text-sm text-muted-foreground bg-muted/50 rounded-lg p-3">
                  <div className="flex flex-wrap gap-4">
                    <span>
                      <strong>最終追い切り:</strong> {trainingRanges.finalStart.slice(4,6)}/{trainingRanges.finalStart.slice(6,8)}〜{trainingRanges.finalEnd.slice(4,6)}/{trainingRanges.finalEnd.slice(6,8)}
                    </span>
                    <span>
                      <strong>一週前:</strong> {trainingRanges.weekAgoStart.slice(4,6)}/{trainingRanges.weekAgoStart.slice(6,8)}〜{trainingRanges.weekAgoEnd.slice(4,6)}/{trainingRanges.weekAgoEnd.slice(6,8)}
                    </span>
                  </div>
                </div>
              )}

              {/* エラー表示 */}
              {trainingError && (
                <div className="text-sm text-red-600 bg-red-50 dark:bg-red-950 rounded-lg p-3">
                  エラー: {trainingError}
                </div>
              )}

              {/* 結果表示 */}
              {trainingSummaries.length > 0 && (
                <>
                  {/* アクションボタン */}
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => copyToClipboard('lap')}
                      className="h-8 px-3 rounded-md border bg-background hover:bg-muted flex items-center gap-2 text-sm transition-colors"
                    >
                      <ClipboardCopy className="h-4 w-4" />
                      馬名・ラップ
                    </button>
                    <button
                      onClick={() => copyToClipboard('time')}
                      className="h-8 px-3 rounded-md border bg-background hover:bg-muted flex items-center gap-2 text-sm transition-colors"
                    >
                      <ClipboardCopy className="h-4 w-4" />
                      馬名・タイム
                    </button>
                    <button
                      onClick={() => copyToClipboard('detail')}
                      className="h-8 px-3 rounded-md border bg-background hover:bg-muted flex items-center gap-2 text-sm transition-colors"
                    >
                      <ClipboardCopy className="h-4 w-4" />
                      馬名・詳細
                    </button>
                    <button
                      onClick={downloadTsv}
                      className="h-8 px-3 rounded-md border bg-background hover:bg-muted flex items-center gap-2 text-sm transition-colors"
                    >
                      <Download className="h-4 w-4" />
                      TSVダウンロード
                    </button>
                    <button
                      onClick={saveTrainingSummary}
                      className="h-8 px-3 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 flex items-center gap-2 text-sm transition-colors"
                    >
                      <Save className="h-4 w-4" />
                      データ保存
                    </button>
                    <span className="text-sm text-muted-foreground self-center ml-2">
                      {trainingSummaries.length}件
                    </span>
                  </div>

                  {/* テーブル */}
                  <div className="border rounded-lg overflow-hidden">
                    <div className="max-h-96 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-muted sticky top-0">
                          <tr>
                            <th className="px-3 py-2 text-left font-medium">馬名</th>
                            <th className="px-3 py-2 text-center font-medium w-16">ラップ</th>
                            <th className="px-3 py-2 text-center font-medium w-16">タイム</th>
                            <th className="px-3 py-2 text-left font-medium">詳細</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {trainingSummaries.slice(0, 100).map((s, i) => (
                            <tr key={i} className="hover:bg-muted/50">
                              <td className="px-3 py-1.5 font-medium">{s.horseName}</td>
                              <td className="px-3 py-1.5 text-center">
                                <span className={`inline-block min-w-[2rem] px-1 rounded ${
                                  s.lapRank.startsWith('SS') ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' :
                                  s.lapRank.startsWith('S') ? 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300' :
                                  s.lapRank.startsWith('A') ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' :
                                  s.lapRank.startsWith('B') ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
                                  ''
                                }`}>
                                  {s.lapRank}
                                </span>
                              </td>
                              <td className="px-3 py-1.5 text-center">{s.timeRank}</td>
                              <td className="px-3 py-1.5 text-muted-foreground text-xs">{s.detail}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {trainingSummaries.length > 100 && (
                      <div className="px-3 py-2 text-sm text-muted-foreground bg-muted/50 border-t">
                        ...他 {trainingSummaries.length - 100}件
                      </div>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

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
