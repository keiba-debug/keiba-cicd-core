'use client';

import React, { useState, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ActionType } from '@/lib/admin/commands';

interface RecalcButtonProps {
  actionId: ActionType;
  label?: string;
  onComplete?: () => void;
}

/**
 * 分析ページ用の再集計ボタン
 * /api/admin/execute を呼び出してPython分析スクリプトを実行し、
 * 完了後に onComplete コールバックでデータを再読み込みする。
 */
export function RecalcButton({ actionId, label = '再集計', onComplete }: RecalcButtonProps) {
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const execute = useCallback(async () => {
    setRunning(true);
    setStatus('idle');

    try {
      const response = await fetch('/api/admin/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionId }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let success = false;

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
              if (data.type === 'complete') success = true;
              if (data.type === 'error') throw new Error(data.message);
            } catch (e) {
              if (e instanceof Error && e.message !== 'Unexpected end of JSON input') {
                throw e;
              }
            }
          }
        }
      }

      if (success) {
        setStatus('success');
        onComplete?.();
        setTimeout(() => setStatus('idle'), 3000);
      }
    } catch {
      setStatus('error');
      setTimeout(() => setStatus('idle'), 3000);
    } finally {
      setRunning(false);
    }
  }, [actionId, onComplete]);

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={execute}
      disabled={running}
      className={`gap-1.5 ${
        status === 'success'
          ? 'border-green-300 text-green-700 dark:border-green-700 dark:text-green-400'
          : status === 'error'
            ? 'border-red-300 text-red-700 dark:border-red-700 dark:text-red-400'
            : ''
      }`}
    >
      <RefreshCw className={`h-4 w-4 ${running ? 'animate-spin' : ''}`} />
      {running ? '実行中...' : status === 'success' ? '完了' : status === 'error' ? 'エラー' : label}
    </Button>
  );
}
