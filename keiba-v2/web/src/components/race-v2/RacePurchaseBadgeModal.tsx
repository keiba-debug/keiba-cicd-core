'use client';

/**
 * 購入金額表示 + 買い目モーダル
 * variant=compact: レースヘッダー用 / variant=prominent: 出走表ヘッダー中央
 */

import { useState } from 'react';
import { Wallet, Bot, Hand } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { RacePurchaseSection, RacePurchasesCombined } from '@/lib/data/race-purchase-types';

const yen = (n: number) => `¥${Math.round(n).toLocaleString()}`;

const profitColor = (n: number) =>
  n > 0 ? 'text-emerald-600' : n < 0 ? 'text-rose-600' : 'text-foreground';

function betResultLabel(
  section: RacePurchaseSection,
  b: RacePurchaseSection['bets'][number],
): { text: string; className: string } {
  if (!section.confirmed) {
    return { text: '未確定', className: 'text-muted-foreground' };
  }
  if (b.is_hit) {
    return { text: '的中', className: 'text-emerald-600 font-bold' };
  }
  return { text: 'はずれ', className: 'text-rose-500/70' };
}

function SectionSummary({ section }: { section: RacePurchaseSection }) {
  const Icon = section.source === 'auto' ? Bot : Hand;
  const hitCount = section.confirmed ? section.bets.filter((b) => b.is_hit).length : 0;

  return (
    <div className="rounded-lg border bg-muted/20 overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b bg-muted/40">
        <Icon className="w-4 h-4 text-muted-foreground" />
        <span className="font-semibold text-sm">{section.label}</span>
        {section.confirmed ? (
          <Badge variant="secondary" className="text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
            確定
          </Badge>
        ) : (
          <Badge variant="secondary" className="text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            未確定
          </Badge>
        )}
        <span className="text-xs text-muted-foreground ml-auto">{section.bets.length}点</span>
      </div>

      <div className="grid grid-cols-4 gap-1 p-2 text-center text-xs">
        <div>
          <div className="text-[10px] text-muted-foreground">投資</div>
          <div className="font-bold tabular-nums">{yen(section.total_bet)}</div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">払戻</div>
          <div className="font-bold tabular-nums">{yen(section.total_payout)}</div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">収支</div>
          <div className={`font-bold tabular-nums ${profitColor(section.profit)}`}>
            {section.profit > 0 ? '+' : ''}{yen(section.profit)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">回収率</div>
          <div className="font-bold tabular-nums">
            {section.settled_bet > 0 ? `${section.recovery_rate.toFixed(0)}%` : '—'}
          </div>
        </div>
      </div>

      {section.confirmed && section.hits.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 px-3 pb-2 text-xs">
          <span className="text-muted-foreground">的中:</span>
          {section.hits.map((h, i) => (
            <Badge key={i} variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              {h}
            </Badge>
          ))}
          <span className="text-muted-foreground">({hitCount}/{section.bets.length})</span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-y text-[11px] text-muted-foreground bg-background/80">
              <th className="py-1.5 px-2 text-left font-medium">券種</th>
              <th className="py-1.5 px-2 text-left font-medium">馬番</th>
              <th className="py-1.5 px-2 text-right font-medium">金額</th>
              <th className="py-1.5 px-2 text-center font-medium">受付</th>
              <th className="py-1.5 px-2 text-right font-medium">払戻</th>
              <th className="py-1.5 px-2 text-center font-medium">結果</th>
            </tr>
          </thead>
          <tbody>
            {section.bets.map((b, i) => {
              const result = betResultLabel(section, b);
              const rowHit = section.confirmed && b.is_hit;
              return (
                <tr
                  key={`${section.source}-${i}`}
                  className={`border-b last:border-0 ${rowHit ? 'bg-emerald-50 dark:bg-emerald-950/20' : ''}`}
                >
                  <td className="py-1.5 px-2 whitespace-nowrap font-medium">{b.bet_type}</td>
                  <td className="py-1.5 px-2 whitespace-nowrap tabular-nums">{b.selection || '—'}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums">{yen(b.amount)}</td>
                  <td className="py-1.5 px-2 text-center tabular-nums text-[11px] text-muted-foreground">
                    {b.receipt_number || '—'}
                  </td>
                  <td className="py-1.5 px-2 text-right tabular-nums">
                    {section.confirmed && b.payout > 0 ? (
                      <span className="font-semibold text-emerald-600">{yen(b.payout)}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className={`py-1.5 px-2 text-center text-xs ${result.className}`}>
                    {result.text}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PurchaseModalBody({ purchases }: { purchases: RacePurchasesCombined }) {
  const {
    sections,
    total_bet,
    settled_bet,
    total_payout,
    profit,
    recovery_rate,
    confirmed,
    venue,
    race_number,
    race_name,
  } = purchases;

  return (
    <>
      <DialogHeader className="flex-shrink-0">
        <DialogTitle className="flex flex-wrap items-center gap-2 text-base">
          <Wallet className="w-5 h-5 text-emerald-600" />
          購入買い目
          <Badge variant="outline">{venue}{race_number}R</Badge>
          {race_name && (
            <span className="text-sm font-normal text-muted-foreground truncate max-w-[200px]">
              {race_name}
            </span>
          )}
        </DialogTitle>
      </DialogHeader>

      <div className="flex-shrink-0 grid grid-cols-4 gap-2 text-center text-sm">
        <div className="rounded-lg bg-muted/50 py-2">
          <div className="text-[11px] text-muted-foreground">投資合計</div>
          <div className="font-bold tabular-nums">{yen(total_bet)}</div>
        </div>
        <div className="rounded-lg bg-muted/50 py-2">
          <div className="text-[11px] text-muted-foreground">払戻{!confirmed && '(確定分)'}</div>
          <div className="font-bold tabular-nums">{yen(total_payout)}</div>
        </div>
        <div className="rounded-lg bg-muted/50 py-2">
          <div className="text-[11px] text-muted-foreground">収支{!confirmed && '(確定分)'}</div>
          <div className={`font-bold tabular-nums ${profitColor(profit)}`}>
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

      <div className="flex-1 overflow-y-auto space-y-3 -mx-1 px-1">
        {sections.map((section) => (
          <SectionSummary key={section.source} section={section} />
        ))}
      </div>

      <p className="flex-shrink-0 text-[11px] text-muted-foreground">
        ※ 自動投票 = purchase_ledger。 TARGET手動 = PDyyyymm.CSV のうち ledger と重複しない分のみ。
      </p>
    </>
  );
}

export function RacePurchaseBadgeModal({
  purchases,
  variant = 'compact',
}: {
  purchases: RacePurchasesCombined | null;
  variant?: 'compact' | 'prominent';
}) {
  const [open, setOpen] = useState(false);

  if (!purchases?.has_any) return null;

  const {
    sections,
    total_bet,
    profit,
    confirmed,
    bet_count,
  } = purchases;

  const autoSection = sections.find((s) => s.source === 'auto');
  const manualSection = sections.find((s) => s.source === 'target');
  const hasHit = confirmed && sections.some((s) => s.hits.length > 0);
  const allMiss = confirmed && !hasHit;

  const trigger =
    variant === 'prominent' ? (
      <button
        type="button"
        className="group flex flex-col items-center justify-center min-w-[160px] px-6 py-2 rounded-xl border-2 border-emerald-400 bg-gradient-to-b from-emerald-50 to-white hover:from-emerald-100 hover:to-emerald-50 dark:from-emerald-950/40 dark:to-gray-900 dark:border-emerald-700 transition-all shadow-sm hover:shadow-md cursor-pointer"
      >
        <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 tracking-wide">
          購入
        </span>
        <span className="text-3xl font-black tabular-nums text-emerald-800 dark:text-emerald-300 leading-tight">
          {yen(total_bet)}
        </span>
        <span className="text-xs text-muted-foreground mt-0.5">
          {bet_count}点
          {autoSection && manualSection && (
            <span className="ml-1">
              (自動 {yen(autoSection.total_bet)} + 手動 {yen(manualSection.total_bet)})
            </span>
          )}
        </span>
        {!confirmed && (
          <Badge variant="secondary" className="mt-1 text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            未確定
          </Badge>
        )}
        {confirmed && profit > 0 && (
          <Badge variant="secondary" className="mt-1 text-[10px] bg-emerald-100 text-emerald-800">
            +{yen(profit)}
          </Badge>
        )}
        {allMiss && (
          <Badge variant="secondary" className="mt-1 text-[10px]">はずれ</Badge>
        )}
        <span className="text-[10px] text-emerald-600/70 dark:text-emerald-500/70 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
          クリックで買い目詳細
        </span>
      </button>
    ) : (
      <Button
        variant="outline"
        size="sm"
        className="h-8 border-emerald-300 text-emerald-800 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-950/30 shrink-0"
      >
        <Wallet className="w-4 h-4 mr-1 shrink-0" />
        <span className="font-bold tabular-nums">{yen(total_bet)}</span>
        <span className="text-xs text-muted-foreground mx-1">·</span>
        <span className="text-xs">{bet_count}点</span>
        {!confirmed && (
          <Badge variant="secondary" className="ml-1.5 text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            未確定
          </Badge>
        )}
        {confirmed && profit > 0 && (
          <Badge variant="secondary" className="ml-1.5 text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
            +{yen(profit)}
          </Badge>
        )}
        {allMiss && (
          <Badge variant="secondary" className="ml-1.5 text-[10px]">はずれ</Badge>
        )}
      </Button>
    );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col gap-3">
        <PurchaseModalBody purchases={purchases} />
      </DialogContent>
    </Dialog>
  );
}
