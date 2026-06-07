/**
 * 出走表ヘッダー用 — レース単位の購入表示型
 * 自動投票 (purchase_ledger) と TARGET 手動を分けて扱う
 */

export type PurchaseSource = 'auto' | 'target';

export interface RaceBetDisplay {
  bet_type: string;
  selection: string;
  amount: number;
  odds: number;
  is_hit: boolean;
  payout: number;
  receipt_number?: string;
  strategy_name?: string;
  payout_source?: string;
  source: PurchaseSource;
}

export interface RacePurchaseSection {
  source: PurchaseSource;
  label: string;
  total_bet: number;
  settled_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  confirmed: boolean;
  hits: string[];
  bets: RaceBetDisplay[];
}

export interface RacePurchasesCombined {
  race_id: string;
  venue: string;
  race_number: number;
  race_name: string;
  sections: RacePurchaseSection[];
  total_bet: number;
  settled_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  confirmed: boolean;
  bet_count: number;
  has_any: boolean;
}
