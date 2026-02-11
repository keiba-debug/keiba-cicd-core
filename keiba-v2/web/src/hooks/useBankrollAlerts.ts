/**
 * Bankroll Alerts データ取得フック（SWR）
 * 複数コンポーネント間でキャッシュを共有し、不要なAPIリクエストを削減
 */

import useSWR from 'swr';

export interface Alert {
  type: 'warning' | 'error' | 'info';
  message: string;
  severity: 'low' | 'medium' | 'high';
}

export interface BankrollAlertsData {
  alerts: Alert[];
  count: number;
  dailyLimit: number;
  raceLimit: number;
  remaining: number;
  todaySpent: number;
  baseAmount: number;
  currentBalance: number;
  useCurrentBalance: boolean;
}

const fetcher = (url: string) => fetch(url).then(r => r.json());

/**
 * Bankroll Alerts データを取得するカスタムフック
 *
 * 自動ポーリングは無効化（購入は頻繁に行われないため）
 * 手動リフレッシュボタンで必要時に更新
 *
 * @returns SWRレスポンス（data, error, isLoading, mutate）
 */
export function useBankrollAlerts() {
  return useSWR<BankrollAlertsData>('/api/bankroll/alerts', fetcher, {
    refreshInterval: 0,           // 自動更新無効化
    dedupingInterval: 2000,       // 2秒以内の重複リクエストを防ぐ
    revalidateOnFocus: false,     // フォーカス時の再検証を無効化
    revalidateOnReconnect: false, // 再接続時も無効化
  });
}
