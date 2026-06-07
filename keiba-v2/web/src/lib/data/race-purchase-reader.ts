/**
 * 出走表 — レース単位の購入データ (自動投票 ledger + TARGET 手動)
 *
 * 重複除外: 現状は betDedupKey (券種+馬番+金額)。
 * 将来宿題: IPAT 受付番号突合 — docs/auto-purchase/backlog_race_purchase_dedup.md
 */

import {
  getRacePurchase,
  venueFromRaceId,
  raceNumberFromRaceId,
  type LedgerRacePurchase,
} from '@/lib/data/ledger-reader';
import { settleLedgerForDate } from '@/lib/bankroll/settle-ledger-runner';
import { readTargetDaily, type TargetDailyRace, type TargetDailyBet } from '@/lib/bankroll/target-reader-runner';
import type {
  RaceBetDisplay,
  RacePurchaseSection,
  RacePurchasesCombined,
} from '@/lib/data/race-purchase-types';

/** ledger=3連複 / TARGET=三連複 など表記ゆれを統一 */
const BET_TYPE_CANONICAL: Record<string, string> = {
  三連複: '3連複',
  三連単: '3連単',
};

export function normalizeBetType(bet_type: string): string {
  return BET_TYPE_CANONICAL[bet_type] ?? bet_type;
}

/** 馬番順が無関係な券種 (ソートして比較) */
const UNORDERED_BET_TYPES = new Set(['枠連', '馬連', 'ワイド', '3連複']);

/** 馬番順序を正規化。3連単・馬単は順序を保持 */
export function normalizeSelection(bet_type: string, selection: string): string {
  const canon = normalizeBetType(bet_type);
  const parts = selection.split('-').map((s) => s.trim()).filter(Boolean);
  if (parts.length > 0 && parts.every((p) => /^\d+$/.test(p))) {
    const nums = parts.map((p) => parseInt(p, 10));
    if (UNORDERED_BET_TYPES.has(canon)) {
      return nums.sort((a, b) => a - b).join('-');
    }
    return nums.join('-');
  }
  return selection.trim();
}

export function betDedupKey(bet_type: string, selection: string, amount: number): string {
  const canon = normalizeBetType(bet_type);
  return `${canon}|${normalizeSelection(canon, selection)}|${amount}`;
}

function ledgerToSection(p: LedgerRacePurchase): RacePurchaseSection {
  const section: RacePurchaseSection = {
    source: 'auto',
    label: '自動投票',
    total_bet: 0,
    settled_bet: 0,
    total_payout: 0,
    profit: 0,
    recovery_rate: 0,
    confirmed: p.confirmed,
    hits: [],
    bets: p.bets.map((b) => ({
      bet_type: b.bet_type,
      selection: b.selection,
      amount: b.amount,
      odds: b.odds,
      is_hit: b.is_hit,
      payout: b.payout,
      receipt_number: b.receipt_number,
      strategy_name: b.strategy_name,
      payout_source: b.payout_source,
      source: 'auto' as const,
    })),
  };
  return recalcSection(section);
}

/** 未確定レースでは CSV の的中フラグを表示に使わない */
function mapTargetBet(b: TargetDailyBet, confirmed: boolean): RaceBetDisplay {
  return {
    bet_type: b.bet_type,
    selection: b.selection,
    amount: b.amount,
    odds: b.odds ?? 0,
    is_hit: confirmed ? b.is_hit : false,
    payout: confirmed ? (b.payout ?? 0) : 0,
    source: 'target' as const,
  };
}

function recalcSection(section: RacePurchaseSection): RacePurchaseSection {
  const hits: string[] = [];
  let total_bet = 0;
  let settled_bet = 0;
  let total_payout = 0;

  for (const b of section.bets) {
    total_bet += b.amount;
    if (section.confirmed) {
      settled_bet += b.amount;
      total_payout += b.payout;
      if (b.is_hit) hits.push(`${b.bet_type}${b.selection}`);
    }
  }

  const profit = total_payout - settled_bet;
  const recovery_rate = settled_bet > 0 ? (total_payout / settled_bet) * 100 : 0;

  return {
    ...section,
    total_bet,
    settled_bet,
    total_payout,
    profit,
    recovery_rate,
    hits,
  };
}

/** ledger に無い TARGET 買い目のみ (= 手動購入)
 *  TODO: receipt 突合 — backlog_race_purchase_dedup.md
 */
function targetManualSection(
  targetRace: TargetDailyRace,
  autoSection: RacePurchaseSection | null,
): RacePurchaseSection | null {
  const autoKeys = new Set(
    (autoSection?.bets ?? []).map((b) => betDedupKey(b.bet_type, b.selection, b.amount)),
  );

  const manualBets = (targetRace.bets || [])
    .filter((b) => !autoKeys.has(betDedupKey(b.bet_type, b.selection, b.amount)))
    .map((b) => mapTargetBet(b, targetRace.confirmed));

  if (manualBets.length === 0) return null;

  return recalcSection({
    source: 'target',
    label: 'TARGET手動',
    total_bet: 0,
    settled_bet: 0,
    total_payout: 0,
    profit: 0,
    recovery_rate: 0,
    confirmed: targetRace.confirmed,
    hits: [],
    bets: manualBets,
  });
}

function combineSections(
  raceId: string,
  raceName: string,
  sections: RacePurchaseSection[],
): RacePurchasesCombined | null {
  const active = sections.filter((s) => s.bets.length > 0);
  if (active.length === 0) return null;

  const venue = venueFromRaceId(raceId);
  const race_number = raceNumberFromRaceId(raceId);

  let total_bet = 0;
  let settled_bet = 0;
  let total_payout = 0;
  let bet_count = 0;
  let allConfirmed = true;

  for (const s of active) {
    total_bet += s.total_bet;
    settled_bet += s.settled_bet;
    total_payout += s.total_payout;
    bet_count += s.bets.length;
    if (!s.confirmed) allConfirmed = false;
  }

  const profit = total_payout - settled_bet;
  const recovery_rate = settled_bet > 0 ? (total_payout / settled_bet) * 100 : 0;

  return {
    race_id: raceId,
    venue,
    race_number,
    race_name: raceName,
    sections: active,
    total_bet,
    settled_bet,
    total_payout,
    profit,
    recovery_rate,
    confirmed: allConfirmed && bet_count > 0,
    bet_count,
    has_any: true,
  };
}

/** 16桁 raceId から自動 + TARGET 手動(重複除外) の購入を取得 */
export async function getRacePurchasesCombined(
  raceId: string,
  raceName = '',
): Promise<RacePurchasesCombined | null> {
  if (!raceId || raceId.length < 8) return null;

  const dateIso = `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`;
  const dateYmd = dateIso.replace(/-/g, '');

  await settleLedgerForDate(dateIso);

  const [ledgerPurchase, targetDaily] = await Promise.all([
    getRacePurchase(raceId),
    readTargetDaily(dateYmd),
  ]);

  const sections: RacePurchaseSection[] = [];

  const autoSection =
    ledgerPurchase && ledgerPurchase.bets.length > 0
      ? ledgerToSection(ledgerPurchase)
      : null;

  if (autoSection) sections.push(autoSection);

  const targetRace = targetDaily?.races?.find((r) => r.race_id === raceId);
  if (targetRace && targetRace.bets?.length > 0) {
    const manual = targetManualSection(targetRace, autoSection);
    if (manual) sections.push(manual);
  }

  const resolvedName = raceName || ledgerPurchase?.race_name || '';

  return combineSections(raceId, resolvedName, sections);
}
