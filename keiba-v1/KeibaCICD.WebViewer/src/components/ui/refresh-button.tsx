'use client';

/**
 * リフレッシュボタン
 *
 * router.refresh()でServer Componentのデータを再取得する。
 * ページリロードと違い、Reactツリーを維持したままデータだけ更新。
 * → Client Componentのstate（展開状態、タブ選択等）を保持できる。
 */

import { useRouter } from 'next/navigation';
import { useState, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface RefreshButtonProps {
  /** ボタンサイズ */
  size?: 'sm' | 'default' | 'lg' | 'icon';
  /** ラベルテキスト（デフォルト: "データ更新"） */
  label?: string;
  /** ラベルを非表示にしてアイコンのみにする */
  iconOnly?: boolean;
  /** 追加のclassName */
  className?: string;
}

export function RefreshButton({
  size = 'sm',
  label = 'データ更新',
  iconOnly = false,
  className = '',
}: RefreshButtonProps) {
  const router = useRouter();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    router.refresh();
    // router.refresh()は非同期だがPromiseを返さないため、
    // 短いタイマーでスピナーを表示
    setTimeout(() => setIsRefreshing(false), 1500);
  }, [router]);

  return (
    <Button
      variant="outline"
      size={iconOnly ? 'icon' : size}
      onClick={handleRefresh}
      disabled={isRefreshing}
      className={className}
      title={label}
    >
      <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
      {!iconOnly && <span className="ml-1.5">{label}</span>}
    </Button>
  );
}
