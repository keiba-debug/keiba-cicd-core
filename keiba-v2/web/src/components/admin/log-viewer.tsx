'use client';

import React, { useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

interface LogViewerProps {
  logs: LogEntry[];
  maxHeight?: string;
}

export function LogViewer({ logs, maxHeight = '300px' }: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // 新しいログが追加されたら自動スクロール
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  const getLevelStyles = (level: LogEntry['level']) => {
    switch (level) {
      case 'success':
        return 'text-green-600 dark:text-green-400';
      case 'warning':
        return 'text-yellow-600 dark:text-yellow-400';
      case 'error':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-muted-foreground';
    }
  };

  const getLevelIcon = (level: LogEntry['level']) => {
    switch (level) {
      case 'success':
        return '✅';
      case 'warning':
        return '⚠️';
      case 'error':
        return '❌';
      default:
        return '🔹';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div
      ref={containerRef}
      className="font-mono text-sm bg-gray-950 text-gray-200 rounded-lg p-3 overflow-y-auto"
      style={{ maxHeight }}
    >
      {logs.length === 0 ? (
        <div className="text-gray-500 text-center py-4">
          ログはありません
        </div>
      ) : (
        <div className="space-y-1">
          {logs.map((log) => (
            <div key={log.id} className="flex gap-2 leading-relaxed">
              <span className="text-gray-500 flex-shrink-0">
                [{formatTime(log.timestamp)}]
              </span>
              <span className="flex-shrink-0">{getLevelIcon(log.level)}</span>
              <span className={cn('break-all', getLevelStyles(log.level))}>
                {log.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
