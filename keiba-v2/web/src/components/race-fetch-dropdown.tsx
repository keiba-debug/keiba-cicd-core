'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Download, Loader2, ChevronDown } from 'lucide-react';

type ActionType = 'paddok' | 'seiseki';

const ACTIONS: Array<{ id: ActionType; label: string }> = [
  { id: 'paddok', label: 'パドック情報を取得' },
  { id: 'seiseki', label: '成績情報を取得' },
];

interface RaceFetchDropdownProps {
  date: string;
  raceNumber: number;
}

export function RaceFetchDropdown({ date, raceNumber }: RaceFetchDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [runningAction, setRunningAction] = useState<ActionType | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 外部クリックで閉じる
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const execute = async (action: ActionType) => {
    setIsOpen(false);
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

      // 3秒後にステータスをクリア
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatusMessage(`エラー: ${message}`);
      setTimeout(() => setStatusMessage(null), 5000);
    } finally {
      setRunningAction(null);
    }
  };

  const isRunning = runningAction !== null;

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        disabled={isRunning}
        className="rounded-lg"
      >
        {isRunning ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <Download className="w-4 h-4 mr-2" />
        )}
        {statusMessage || 'データ取得'}
        <ChevronDown className="w-4 h-4 ml-1" />
      </Button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-card rounded-lg border shadow-lg z-50">
          {ACTIONS.map((action) => (
            <button
              key={action.id}
              onClick={() => execute(action.id)}
              className="w-full px-4 py-2 text-left text-sm hover:bg-muted transition-colors first:rounded-t-lg last:rounded-b-lg"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
