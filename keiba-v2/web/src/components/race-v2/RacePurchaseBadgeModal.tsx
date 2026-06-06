'use client';

/**
 * レース購入買い目バッジ + モーダル (W3)
 *
 * 購入のある (= purchase_ledger v2 に portfolio が存在する) レースに
 * 「購入あり」バッジを表示し、 クリックでそのレースの買い目
 * (券種 / 馬番 / 金額 / 受付番号 / 払戻) をモーダルで一覧する。
 *
 * データは server 側 (getRacePurchase) で読み込んだ LedgerRacePurchase を
 * props で受け取る。 このコンポーネントは表示専用 (書込なし)。
 */

import { useState } from 'react';
import { Wallet } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { LedgerRacePurchase } from '@/lib/data/ledger-reader';

const yen = (n: number) => `¥${Math.round(n).toLocaleString()}`;

export function RacePurchaseBadgeModal({ purchase }: { purchase: LedgerRacePurchase | null }) {
  const [open, setOpen] = useState(false);

  // 購入が無ければ何も描画しない
  if (!purchase || purchase.bets.length === 0) return null;

  const {
    bets,
    total_bet,
    settled_bet,
    total_payout,
    profit,
    recovery_rate,
    confirmed,
    hits,
    venue,
    race_number,
    race_name,
  } = purchase;

  const hitCount = bets.filter((b) => b.is_hit).length;
  const profitColor = profit > 0 ? 'text-emerald-600' : profit < 0 ? 'text-rose-600' : 'text-foreground';

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="border-emerald-300 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-950/30"
        >
          <Wallet className="w-4 h-4 mr-1" />
          購入あり
          <Badge variant="secondary" className="ml-1.5">{bets.length}点</Badge>
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <Wallet className="w-5 h-5 text-emerald-600" />
            購入買い目
            <Badge variant="outline">{venue}{race_number}R</Badge>
            {race_name && <span className="text-sm font-normal text-muted-foreground">{race_name}</span>}
            {confirmed ? (
              <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">確定</Badge>
            ) : (
              <Badge variant="secondary" className="bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">未確定</Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* サマリー */}
        <div className="flex-shrink-0 grid grid-cols-4 gap-2 text-center text-sm">
          <div className="rounded-lg bg-muted/50 py-2">
            <div className="text-[11px] text-muted-foreground">投資</div>
            <div className="font-bold tabular-nums">{yen(total_bet)}</div>
          </div>
          <div className="rounded-lg bg-muted/50 py-2">
            <div className="text-[11px] text-muted-foreground">払戻{!confirmed && '(確定分)'}</div>
            <div className="font-bold tabular-nums">{yen(total_payout)}</div>
          </div>
          <div className="rounded-lg bg-muted/50 py-2">
            <div className="text-[11px] text-muted-foreground">収支{!confirmed && '(確定分)'}</div>
            <div className={`font-bold tabular-nums ${profitColor}`}>
              {profit > 0 ? '+' : ''}{yen(profit)}
            </div>
          </div>
          <div className="rounded-lg bg-muted/50 py-2">
            <div className="text-[11px] text-muted-foreground">回収率</div>
            <div className="font-bold tabular-nums">
              {settled_bet > 0 ? `${recovery_rate.toFixed(0)}%` : '—'}
            </div>
          </div>
        </div>

        {hits.length > 0 && (
          <div className="flex-shrink-0 flex flex-wrap items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">的中:</span>
            {hits.map((h, i) => (
              <Badge key={i} variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                {h}
              </Badge>
            ))}
            <span className="text-xs text-muted-foreground">({hitCount}/{bets.length})</span>
          </div>
        )}

        {/* 買い目テーブル */}
        <div className="flex-1 overflow-y-auto -mx-1 px-1">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-background">
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 px-2 text-left font-medium">券種</th>
                <th className="py-2 px-2 text-left font-medium">馬番</th>
                <th className="py-2 px-2 text-right font-medium">金額</th>
                <th className="py-2 px-2 text-center font-medium">受付</th>
                <th className="py-2 px-2 text-right font-medium">払戻</th>
                <th className="py-2 px-2 text-center font-medium">結果</th>
              </tr>
            </thead>
            <tbody>
              {bets.map((b, i) => (
                <tr
                  key={`${b.portfolio_id}-${i}`}
                  className={`border-b last:border-0 ${b.is_hit ? 'bg-emerald-50 dark:bg-emerald-950/20' : ''}`}
                >
                  <td className="py-2 px-2 whitespace-nowrap font-medium">{b.bet_type}</td>
                  <td className="py-2 px-2 whitespace-nowrap tabular-nums">{b.selection || '—'}</td>
                  <td className="py-2 px-2 text-right tabular-nums">{yen(b.amount)}</td>
                  <td className="py-2 px-2 text-center tabular-nums text-xs text-muted-foreground">
                    {b.receipt_number || '—'}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums">
                    {b.payout > 0 ? (
                      <span className="font-semibold text-emerald-600">{yen(b.payout)}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="py-2 px-2 text-center">
                    {b.is_hit ? (
                      <span className="text-emerald-600 font-bold">的中</span>
                    ) : b.payout_source ? (
                      // settle 済かつ払戻0 = はずれ (payout_source は精算後にのみ付く)
                      <span className="text-rose-500/70">はずれ</span>
                    ) : (
                      <span className="text-muted-foreground text-xs">未確定</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="flex-shrink-0 text-[11px] text-muted-foreground">
          ※ purchase_ledger v2 の記録 (表示専用)。 戦略: {Array.from(new Set(bets.map((b) => b.strategy_name))).join(', ')}
        </p>
      </DialogContent>
    </Dialog>
  );
}
