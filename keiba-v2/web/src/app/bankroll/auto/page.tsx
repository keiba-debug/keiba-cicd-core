import { AutoPurchaseHistory } from '@/components/bankroll/AutoPurchaseHistory';
import { AutoPurchaseMonthly } from '@/components/bankroll/AutoPurchaseMonthly';
import { AutoVoteControl } from '@/components/bankroll/AutoVoteControl';

export const dynamic = 'force-dynamic';

export default function AutoPurchasePage() {
  return (
    <div className="container py-6 max-w-7xl">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          🤖 自動投票
        </h1>
      </div>

      {/* 当日コントロールパネル（開始/dry-run/停止 + 投票状況の監視） */}
      <div className="mb-6">
        <AutoVoteControl />
      </div>

      {/* 月次サマリー（当月・戦略別ROI + 日次推移） */}
      <div className="mb-6">
        <AutoPurchaseMonthly />
      </div>

      {/* 日次の自動投票履歴 */}
      <AutoPurchaseHistory />
    </div>
  );
}
