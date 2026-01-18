'use client';

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import {
  ActionButton,
  DateSelector,
  LogViewer,
  StatusBadge,
  type LogEntry,
  type ExecutionStatus,
} from '@/components/admin';
import { ACTIONS, type ActionType } from '@/lib/admin/commands';

export default function AdminPage() {
  // 今日の日付をデフォルトに
  const today = new Date();
  const defaultDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const [selectedDate, setSelectedDate] = useState(defaultDate);
  const [status, setStatus] = useState<ExecutionStatus>('idle');
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);

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
    
    addLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `${actionConfig.icon} ${actionConfig.label} 開始...`,
    });

    try {
      const response = await fetch('/api/admin/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, date: selectedDate }),
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
        message: `❌ エラー: ${errorMessage}`,
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

  // カテゴリ別にアクションを分類
  const fetchActions = ACTIONS.filter((a) => a.category === 'fetch');
  const generateActions = ACTIONS.filter((a) => a.category === 'generate');
  const batchActions = ACTIONS.filter((a) => a.category === 'batch');

  return (
    <div className="container py-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          📊 管理画面
        </h1>
        <StatusBadge status={status} />
      </div>

      {/* 日付選択 */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <DateSelector
            date={selectedDate}
            onChange={setSelectedDate}
            disabled={isRunning}
          />
        </CardContent>
      </Card>

      {/* データ取得 */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            📥 データ取得
          </CardTitle>
        </CardHeader>
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
      </Card>

      {/* データ統合・生成 */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            📝 データ統合・生成
          </CardTitle>
        </CardHeader>
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
      </Card>

      {/* 一括実行 */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            🚀 一括実行
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
