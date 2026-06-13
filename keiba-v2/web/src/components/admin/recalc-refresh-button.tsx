'use client';

import { useRouter } from 'next/navigation';
import { RecalcButton } from '@/components/admin/recalc-button';
import type { ActionType } from '@/lib/admin/commands';

/**
 * サーバーコンポーネントの分析ページ用 再集計ボタン。
 * RecalcButton（クライアント）を router.refresh() でラップし、
 * 再集計完了後にサーバーデータを再取得して表示を更新する。
 */
export function RecalcRefreshButton({ actionId, label }: { actionId: ActionType; label?: string }) {
  const router = useRouter();
  return <RecalcButton actionId={actionId} label={label} onComplete={() => router.refresh()} />;
}
