'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type ActionType = 'paddok' | 'seiseki';

const ACTIONS: Array<{ id: ActionType; label: string; short: string; icon: string }> = [
  { id: 'paddok', label: 'パドック取得', short: 'パドック', icon: '🐎' },
  { id: 'seiseki', label: '成績取得', short: '成績', icon: '🏆' },
];

interface RaceFetchActionsProps {
  date: string;
  raceNumber: number;
  compact?: boolean;
  className?: string;
  showStatus?: boolean;
}

export function RaceFetchActions({
  date,
  raceNumber,
  compact = false,
  className,
  showStatus = true,
}: RaceFetchActionsProps) {
  const [runningAction, setRunningAction] = useState<ActionType | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const execute = async (action: ActionType) => {
    setRunningAction(action);
    setStatusMessage('実行中...');

    try {
      const response = await fetch('/api/admin/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          date,
          raceFrom: raceNumber,
          raceTo: raceNumber,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let isCompleted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = JSON.parse(line.slice(6));
          if (data.type === 'complete') {
            setStatusMessage(String(data.message ?? '完了'));
            isCompleted = true;
          }
          if (data.type === 'error') {
            setStatusMessage(String(data.message ?? 'エラー'));
            isCompleted = true;
          }
        }
      }

      if (!isCompleted) {
        setStatusMessage('完了');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatusMessage(`エラー: ${message}`);
    } finally {
      setRunningAction(null);
    }
  };

  const isRunning = runningAction !== null;

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {ACTIONS.map((action) => (
        <Button
          key={action.id}
          variant="outline"
          size={compact ? 'icon-sm' : 'sm'}
          onClick={() => execute(action.id)}
          disabled={isRunning}
          title={action.label}
          className={cn(compact && 'px-0', runningAction === action.id && 'opacity-80')}
        >
          <span className={cn(!compact && 'text-base')}>{runningAction === action.id ? '⏳' : action.icon}</span>
          {!compact && <span>{action.short}</span>}
        </Button>
      ))}
      {showStatus && statusMessage && !compact && (
        <span className="text-xs text-muted-foreground">{statusMessage}</span>
      )}
    </div>
  );
}
