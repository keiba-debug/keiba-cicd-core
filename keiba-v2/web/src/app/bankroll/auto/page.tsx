import { ActiveMethodCard } from '@/components/bankroll/ActiveMethodCard';
import { AutoPurchaseHistory } from '@/components/bankroll/AutoPurchaseHistory';
import { AutoPurchaseMonthly } from '@/components/bankroll/AutoPurchaseMonthly';
import { AutoVoteControl } from '@/components/bankroll/AutoVoteControl';
import { BudgetForm } from '@/components/bankroll/BudgetForm';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Settings } from 'lucide-react';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '自動投票',
};

export const dynamic = 'force-dynamic';

export default function AutoPurchasePage() {
  return (
    <div className="container py-6 max-w-7xl">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          🤖 自動投票
        </h1>
        {/* 予算設定 (BudgetForm 共有ダイアログ)。スリーブの有効化/隔離bankroll/比率は
            自動投票の設定なのでこのページから直接開けるようにする (推奨馬券/収支と同じ正本)。 */}
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm">
              <Settings className="h-4 w-4 mr-2" />
              予算設定
            </Button>
          </DialogTrigger>
          <DialogContent className="w-[calc(100vw-2rem)] sm:max-w-[560px] max-h-[90vh] overflow-hidden">
            <DialogHeader>
              <DialogTitle>予算設定</DialogTitle>
            </DialogHeader>
            <BudgetForm isModal />
          </DialogContent>
        </Dialog>
      </div>

      {/* 現在狙っている買い目（方式＝bat+config の実体から） */}
      <div className="mb-6">
        <ActiveMethodCard />
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
