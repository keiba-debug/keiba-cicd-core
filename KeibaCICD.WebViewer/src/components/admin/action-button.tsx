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
}

export function ActionButton({
  icon,
  label,
  description,
  onClick,
  disabled = false,
  loading = false,
  variant = 'default',
}: ActionButtonProps) {
  const baseStyles = 'h-auto py-3 px-4 flex flex-col items-start text-left transition-all';
  
  const variantStyles = {
    default: 'bg-background hover:bg-muted border',
    primary: 'bg-blue-50 hover:bg-blue-100 border-blue-200 dark:bg-blue-950 dark:hover:bg-blue-900 dark:border-blue-800',
    batch: 'bg-gradient-to-r from-indigo-50 to-purple-50 hover:from-indigo-100 hover:to-purple-100 border-indigo-200 dark:from-indigo-950 dark:to-purple-950 dark:hover:from-indigo-900 dark:hover:to-purple-900',
  };

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
      </div>
      <span className="text-xs text-muted-foreground mt-1">{description}</span>
    </Button>
  );
}
