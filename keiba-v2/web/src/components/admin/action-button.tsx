'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ActionButtonProps {
  icon: string;
  label: string;
  description: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'default' | 'primary' | 'batch';
  /** パイプラインステータス（任意） */
  stepStatus?: {
    done: boolean;
    timestamp: string | null;
    detail?: string;
  } | null;
}

/** タイムスタンプを短い表示に変換 (例: "03/08 09:50") */
function formatShortTimestamp(ts: string | null): string | null {
  if (!ts) return null;
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return null;
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    return `${mm}/${dd} ${hh}:${mi}`;
  } catch {
    return null;
  }
}

export function ActionButton({
  icon,
  label,
  description,
  onClick,
  disabled = false,
  loading = false,
  variant = 'default',
  stepStatus,
}: ActionButtonProps) {
  const baseStyles = 'h-auto py-3 px-4 flex flex-col items-start text-left transition-all';

  const variantStyles = {
    default: 'bg-background hover:bg-muted border',
    primary: 'bg-blue-50 hover:bg-blue-100 border-blue-200 dark:bg-blue-950 dark:hover:bg-blue-900 dark:border-blue-800',
    batch: 'bg-gradient-to-r from-indigo-50 to-purple-50 hover:from-indigo-100 hover:to-purple-100 border-indigo-200 dark:from-indigo-950 dark:to-purple-950 dark:hover:from-indigo-900 dark:hover:to-purple-900',
  };

  const shortTs = stepStatus?.timestamp ? formatShortTimestamp(stepStatus.timestamp) : null;

  return (
    <Button
      variant="outline"
      className={cn(baseStyles, variantStyles[variant], disabled && 'opacity-50 cursor-not-allowed')}
      onClick={onClick}
      disabled={disabled || loading}
    >
      <div className="flex items-center gap-2 w-full">
        <span className="text-xl">{loading ? '⏳' : icon}</span>
        <span className="font-semibold">{label}</span>
        {loading && <span className="ml-auto text-xs text-muted-foreground">実行中...</span>}
        {!loading && stepStatus && (
          <span className="ml-auto flex items-center gap-1">
            {stepStatus.done ? (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400">
                OK
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                --
              </span>
            )}
          </span>
        )}
      </div>
      <span className="text-xs text-muted-foreground mt-1">{description}</span>
      {/* ステータス詳細行 */}
      {stepStatus && (shortTs || stepStatus.detail) && (
        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-muted-foreground">
          {shortTs && <span>{shortTs}</span>}
          {shortTs && stepStatus.detail && <span>·</span>}
          {stepStatus.detail && <span>{stepStatus.detail}</span>}
        </div>
      )}
    </Button>
  );
}
