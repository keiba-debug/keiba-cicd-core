'use client';

import React, { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useBankrollAlerts } from '@/hooks/useBankrollAlerts';
import { Button } from '@/components/ui/button';

interface RefreshButtonProps {
  onRefresh?: () => void;
}

export function RefreshButton({ onRefresh }: RefreshButtonProps) {
  const { mutate, isLoading } = useBankrollAlerts();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await mutate(); // SWRキャッシュを無効化して再取得
      onRefresh?.(); // 日別データ等の再取得をトリガー
    } finally {
      // アニメーションのために少し遅延
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  return (
    <Button
      onClick={handleRefresh}
      disabled={isLoading || isRefreshing}
      variant="outline"
      size="sm"
      className="gap-2"
    >
      <RefreshCw
        className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`}
      />
      {isRefreshing ? '更新中...' : '最新データ取得'}
    </Button>
  );
}
