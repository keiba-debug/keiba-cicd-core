'use client';

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type ExecutionStatus = 'idle' | 'running' | 'success' | 'error';

interface StatusBadgeProps {
  status: ExecutionStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const getStatusConfig = (status: ExecutionStatus) => {
    switch (status) {
      case 'running':
        return {
          label: '実行中',
          icon: '⏳',
          variant: 'default' as const,
          className: 'bg-blue-500 hover:bg-blue-500',
        };
      case 'success':
        return {
          label: '完了',
          icon: '✅',
          variant: 'default' as const,
          className: 'bg-green-500 hover:bg-green-500',
        };
      case 'error':
        return {
          label: 'エラー',
          icon: '❌',
          variant: 'destructive' as const,
          className: '',
        };
      default:
        return {
          label: '待機中',
          icon: '💤',
          variant: 'secondary' as const,
          className: '',
        };
    }
  };

  const config = getStatusConfig(status);

  return (
    <Badge
      variant={config.variant}
      className={cn(config.className, className)}
    >
      <span className="mr-1">{config.icon}</span>
      {config.label}
    </Badge>
  );
}
