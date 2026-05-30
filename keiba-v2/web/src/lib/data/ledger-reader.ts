/**
 * 自動投票 ledger v2 リーダー (Session 136)
 *
 * data3/userdata/purchase_ledger/{YYYY-MM-DD}.json を読み、
 * 既存の収支管理 UI (DailyPurchaseList 互換) が描画できる形に平坦化する。
 *
 * settle_ledger.py 精算後の ledger は ticket.payout / settled_at を持つので、
 * ここでは DB を引かず JSON を読むだけ (純 TS, Python spawn 不要)。
 *
 * 注意:
 * - ledger の bet_type は英語 (tansho 等)。 表示用に日本語へ変換。
 * - TARGET CSV と違い strategy_name / portfolio_id / 受付番号 / EV を持つ ＝
 *   「戦略別・自動投票専用」 の集計が出せるのがこのソースの価値。
 */

import path from 'path';
import fs from 'fs/promises';
import { AI_DATA_PATH } from '@/lib/config';

export const LEDGER_DIR = path.join(AI_DATA_PATH, 'purchase_ledger');

// ---------------------------------------------------------------------------
// ledger 生スキーマ (14_LEDGER_SCHEMA.md v2)
// ---------------------------------------------------------------------------

export interface LedgerTicket {
  ticket_id: string;
  strategy_name: string;
  formation_type: string;
  pattern_label: string;
  raw_legs: { horses?: number[]; [k: string]: unknown };
  bet_type: string;
  total_amount: number;
  ev_at_decision?: number;
  ipat_receipt_number?: string;
  ipat_receipt_time?: string;
  submitted_at?: string;
  payout?: number;          // settle 後
  settled_at?: string;      // settle 後
  payout_source?: string;   // settle 後: "db" 等 (🔴-2 provenance)
  reconciled?: boolean;     // settle 後: IPAT 突合済か (🔴-1。 現状は常に false=暫定)
}

export interface LedgerPortfolio {
  portfolio_id: string;
  portfolio_strategy: string;
  tickets: LedgerTicket[];
  portfolio_total: number;
  portfolio_pnl?: number;   // settle 後
  portfolio_roi?: number;   // settle 後 (回収率: payout/invest)
  superseded_by_repair?: boolean; // 修復で差し替えられた旧 portfolio (集計対象外, Session 137)
}

export interface LedgerRace {
  race_id: string;
  state: string; // SUBMITTED / SETTLED / ...
  portfolios: LedgerPortfolio[];
}

export interface Ledger {
  version: number;
  date: string;
  races: LedgerRace[];
  events?: Array<{ type: string; race_id?: string | null; payload?: Record<string, unknown> }>;
}

// ---------------------------------------------------------------------------
// 表示用 (DailyPurchaseList 互換 + 戦略フィールド拡張)
// ---------------------------------------------------------------------------

export interface LedgerBetDetail {
  bet_type: string;     // 日本語
  selection: string;    // 馬番 ("13" / "8-13")
  amount: number;
  odds: number;         // payout/amount (的中時) — ledger にオッズは無いので逆算
  is_hit: boolean;
  payout: number;
  strategy_name: string;
  pattern_label: string;
  portfolio_id: string;
  receipt_number?: string;
  ev_at_decision?: number;
  reconciled: boolean;      // IPAT 突合済か (false=暫定)
  payout_source?: string;
}

export interface LedgerRacePurchase {
  race_id: string;
  venue: string;
  race_number: number;
  race_name: string;
  post_time: string;
  distance: string;
  grade?: string;
  state: string;
  total_bet: number;     // 全投資 (pending 含む)
  settled_bet: number;   // 確定済投資
  total_payout: number;  // 確定済払戻
  profit: number;        // total_payout - settled_bet
  recovery_rate: number; // % (確定分のみ)
  hits: string[];
  bets: LedgerBetDetail[];
  confirmed: boolean;  // 全 ticket settle 済か
  reconciled: boolean; // confirmed かつ settle 済 ticket が全て IPAT 突合済か (false=暫定)
}

export interface StrategyStat {
  strategy_name: string;
  bet_count: number;
  settled_count: number;
  pending_count: number;
  hit_count: number;
  invest: number;          // 全投資 (pending 含む = エクスポージャ)
  settled_invest: number;  // 確定済 ticket の投資 (pnl/回収率の分母)
  payout: number;          // 確定済払戻
  pnl: number;             // payout - settled_invest (確定分のみ)
  recovery_rate: number;   // % (payout / settled_invest)
  hit_rate: number;        // % (hit / settled_count)
}

export interface LedgerSummary {
  total_bet: number;       // 全投資 (pending 含む)
  settled_bet: number;     // 確定済投資 (profit/recovery の分母)
  total_payout: number;    // 確定済払戻
  profit: number;          // total_payout - settled_bet (確定分のみ)
  recovery_rate: number;   // % (total_payout / settled_bet)
  race_count: number;
  bet_count: number;
  win_count: number;
  settled_count: number;
  pending_count: number;
  reconciled_count: number;   // settle 済かつ突合済 ticket 数
  all_reconciled: boolean;    // settle 済 ticket が全て突合済か (false=暫定値を含む)
}

export interface LedgerDaily {
  date: string;
  races: LedgerRacePurchase[];
  summary: LedgerSummary;
  by_strategy: StrategyStat[];
  has_data: boolean;
}

// ---------------------------------------------------------------------------
// マッピング
// ---------------------------------------------------------------------------

const BET_TYPE_JP: Record<string, string> = {
  tansho: '単勝',
  fukusho: '複勝',
  wakuren: '枠連',
  umaren: '馬連',
  wide: 'ワイド',
  umatan: '馬単',
  sanrenpuku: '3連複',
  sanrentan: '3連単',
  win5: 'WIN5',
};

// race_id[8:10] (JV 場コード) → 場名
const JV_CODE_TO_VENUE: Record<string, string> = {
  '01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
  '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉',
};

// race_info.json の開催名 → 場名 抽出用
const VENUE_NAMES = Object.values(JV_CODE_TO_VENUE);

export function betTypeJp(bt: string): string {
  return BET_TYPE_JP[bt] || bt;
}

export function venueFromRaceId(raceId: string): string {
  return JV_CODE_TO_VENUE[raceId.slice(8, 10)] || '?';
}

export function raceNumberFromRaceId(raceId: string): number {
  return parseInt(raceId.slice(14, 16), 10) || 0;
}

function legsToSelection(raw: LedgerTicket['raw_legs']): string {
  const horses = raw?.horses;
  if (Array.isArray(horses) && horses.length) return horses.join('-');
  return '';
}

// ---------------------------------------------------------------------------
// レースメタ (post_time / race_name / distance) 補完
//   data3/races/Y/M/D/race_info.json + temp/integrated_*.json から
//   "場名-R番号" キーで引く (既存 /api/bankroll/daily と同方式)
// ---------------------------------------------------------------------------

interface RaceMeta { post_time: string; race_name: string; distance: string; grade: string; }

export async function loadRaceMetaMap(dateYmd: string, dataRoot: string): Promise<Map<string, RaceMeta>> {
  const map = new Map<string, RaceMeta>();
  const year = dateYmd.slice(0, 4);
  const month = dateYmd.slice(5, 7);
  const day = dateYmd.slice(8, 10);
  const raceInfoPath = path.join(dataRoot, 'races', year, month, day, 'race_info.json');

  let raceInfoJson: { kaisai_data?: Record<string, Array<{ race_no: string; race_name: string; course?: string; race_id: string }>> };
  try {
    raceInfoJson = JSON.parse(await fs.readFile(raceInfoPath, 'utf-8'));
  } catch {
    return map;
  }

  for (const [kaisaiName, races] of Object.entries(raceInfoJson.kaisai_data || {})) {
    const venue = VENUE_NAMES.find((v) => kaisaiName.includes(v));
    if (!venue) continue;
    for (const race of races) {
      const raceNum = parseInt(String(race.race_no).replace('R', ''), 10);
      const key = `${venue}-${raceNum}`;
      let postTime = '';
      let raceName = race.race_name || '';
      let distance = '';
      let grade = '';
      try {
        const integratedPath = path.join(dataRoot, 'races', year, month, day, 'temp', `integrated_${race.race_id}.json`);
        const integrated = JSON.parse(await fs.readFile(integratedPath, 'utf-8'));
        const ri = integrated.race_info || {};
        postTime = ri.post_time || '';
        raceName = ri.race_name || ri.race_condition || raceName;
        grade = ri.grade || '';
        if (ri.distance) distance = `${ri.track || ''}${ri.distance}m`;
      } catch {
        const courseMatch = race.course?.match(/([芝ダ])[・・]?(\d+)m/);
        if (courseMatch) distance = `${courseMatch[1]}${courseMatch[2]}m`;
      }
      map.set(key, { post_time: postTime, race_name: raceName, distance, grade });
    }
  }
  return map;
}

// ---------------------------------------------------------------------------
// 読み込み + 平坦化
// ---------------------------------------------------------------------------

/** date は YYYY-MM-DD。 無ければ null。 */
export async function readLedger(dateIso: string): Promise<Ledger | null> {
  const p = path.join(LEDGER_DIR, `${dateIso}.json`);
  try {
    return JSON.parse(await fs.readFile(p, 'utf-8')) as Ledger;
  } catch {
    return null;
  }
}

/** YYYYMMDD または YYYY-MM-DD を YYYY-MM-DD に正規化 */
export function toIsoDate(date: string): string {
  if (/^\d{8}$/.test(date)) return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
  return date;
}

export function flattenLedger(ledger: Ledger, metaMap?: Map<string, RaceMeta>): LedgerDaily {
  const races: LedgerRacePurchase[] = [];
  const strategyAcc = new Map<string, StrategyStat>();

  let sumBet = 0, sumSettledBet = 0, sumPayout = 0, betCount = 0, winCount = 0, settledCount = 0, pendingCount = 0, reconciledCount = 0;

  for (const race of ledger.races || []) {
    const venue = venueFromRaceId(race.race_id);
    const raceNo = raceNumberFromRaceId(race.race_id);
    const meta = metaMap?.get(`${venue}-${raceNo}`);

    const bets: LedgerBetDetail[] = [];
    let raceBet = 0, raceSettledBet = 0, racePayout = 0;
    const hits: string[] = [];
    let raceAllSettled = true;
    let raceAllReconciled = true; // settle 済 ticket が全て突合済か

    for (const pf of race.portfolios || []) {
      if (pf.superseded_by_repair) continue; // 修復で差し替えられた旧 portfolio は集計対象外 (Session 137)
      for (const tk of pf.tickets || []) {
        const amount = tk.total_amount || 0;
        const settled = tk.settled_at != null;
        const reconciled = tk.reconciled === true;
        const payout = settled ? (tk.payout || 0) : 0;
        const isHit = settled && payout > 0;
        const odds = isHit && amount > 0 ? Math.round((payout / amount) * 10) / 10 : 0;
        const betJp = betTypeJp(tk.bet_type);
        const sname = tk.strategy_name || pf.portfolio_strategy || '?';

        bets.push({
          bet_type: betJp,
          selection: legsToSelection(tk.raw_legs),
          amount,
          odds,
          is_hit: isHit,
          payout,
          strategy_name: sname,
          pattern_label: tk.pattern_label || '',
          portfolio_id: pf.portfolio_id,
          receipt_number: tk.ipat_receipt_number,
          ev_at_decision: tk.ev_at_decision,
          reconciled,
          payout_source: tk.payout_source,
        });

        raceBet += amount;
        betCount += 1;
        if (!settled) { raceAllSettled = false; pendingCount += 1; }
        else {
          settledCount += 1;
          raceSettledBet += amount;
          racePayout += payout;
          if (reconciled) reconciledCount += 1; else raceAllReconciled = false;
          if (isHit) { winCount += 1; hits.push(`${betJp}${legsToSelection(tk.raw_legs)}`); }
        }

        // 戦略別集計 — pnl/回収率は確定 (settled) 分のみを分母にする
        const acc = strategyAcc.get(sname) || {
          strategy_name: sname, bet_count: 0, settled_count: 0, pending_count: 0,
          hit_count: 0, invest: 0, settled_invest: 0, payout: 0,
          pnl: 0, recovery_rate: 0, hit_rate: 0,
        };
        acc.bet_count += 1;
        acc.invest += amount;
        if (settled) {
          acc.settled_count += 1;
          acc.settled_invest += amount;
          acc.payout += payout;
          if (isHit) acc.hit_count += 1;
        } else {
          acc.pending_count += 1;
        }
        strategyAcc.set(sname, acc);
      }
    }

    sumBet += raceBet;
    sumSettledBet += raceSettledBet;
    sumPayout += racePayout;

    races.push({
      race_id: race.race_id,
      venue,
      race_number: raceNo,
      race_name: meta?.race_name || '',
      post_time: meta?.post_time || '',
      distance: meta?.distance || '',
      grade: meta?.grade,
      state: race.state,
      total_bet: raceBet,
      settled_bet: raceSettledBet,
      total_payout: racePayout,
      profit: racePayout - raceSettledBet, // 確定分のみ (pending を偽の損失にしない)
      recovery_rate: raceSettledBet > 0 ? (racePayout / raceSettledBet) * 100 : 0,
      hits,
      bets,
      confirmed: raceAllSettled && bets.length > 0,
      reconciled: raceAllSettled && bets.length > 0 && raceAllReconciled,
    });
  }

  // 発走時刻順
  races.sort((a, b) => (a.post_time || '99:99').localeCompare(b.post_time || '99:99'));

  const by_strategy = finalizeStrategyStats(strategyAcc);

  return {
    date: ledger.date,
    races,
    summary: {
      total_bet: sumBet,
      settled_bet: sumSettledBet,
      total_payout: sumPayout,
      profit: sumPayout - sumSettledBet,
      recovery_rate: sumSettledBet > 0 ? (sumPayout / sumSettledBet) * 100 : 0,
      race_count: races.length,
      bet_count: betCount,
      win_count: winCount,
      settled_count: settledCount,
      pending_count: pendingCount,
      reconciled_count: reconciledCount,
      all_reconciled: settledCount > 0 && reconciledCount === settledCount,
    },
    by_strategy,
    has_data: races.length > 0,
  };
}

/** StrategyStat の派生値 (pnl/回収率/的中率) を確定分ベースで計算 */
function finalizeStrategyStats(acc: Map<string, StrategyStat>): StrategyStat[] {
  return Array.from(acc.values()).map((s) => ({
    ...s,
    pnl: s.payout - s.settled_invest,
    recovery_rate: s.settled_invest > 0 ? (s.payout / s.settled_invest) * 100 : 0,
    hit_rate: s.settled_count > 0 ? (s.hit_count / s.settled_count) * 100 : 0,
  })).sort((a, b) => b.invest - a.invest);
}

// ---------------------------------------------------------------------------
// 期間集計 (月次 / 任意期間) — 戦略別ROIの本命
// ---------------------------------------------------------------------------

export interface PeriodSummary {
  from: string;
  to: string;
  days: number;
  summary: LedgerSummary;
  by_strategy: StrategyStat[];
  daily: Array<{ date: string; total_bet: number; total_payout: number; profit: number }>;
}

/** purchase_ledger ディレクトリ内の {YYYY-MM-DD}.json を列挙 */
export async function listLedgerDates(): Promise<string[]> {
  try {
    const files = await fs.readdir(LEDGER_DIR);
    return files
      .filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
      .map((f) => f.replace('.json', ''))
      .sort();
  } catch {
    return [];
  }
}

export async function aggregatePeriod(fromIso: string, toIso: string): Promise<PeriodSummary> {
  const dates = (await listLedgerDates()).filter((d) => d >= fromIso && d <= toIso);
  const strategyAcc = new Map<string, StrategyStat>();
  const daily: PeriodSummary['daily'] = [];
  let sumBet = 0, sumSettledBet = 0, sumPayout = 0, betCount = 0, winCount = 0, settledCount = 0, pendingCount = 0, raceCount = 0, reconciledCount = 0;

  for (const d of dates) {
    const ledger = await readLedger(d);
    if (!ledger) continue;
    const flat = flattenLedger(ledger);
    sumBet += flat.summary.total_bet;
    sumSettledBet += flat.summary.settled_bet;
    sumPayout += flat.summary.total_payout;
    betCount += flat.summary.bet_count;
    winCount += flat.summary.win_count;
    settledCount += flat.summary.settled_count;
    pendingCount += flat.summary.pending_count;
    raceCount += flat.summary.race_count;
    reconciledCount += flat.summary.reconciled_count;
    daily.push({ date: d, total_bet: flat.summary.total_bet, total_payout: flat.summary.total_payout, profit: flat.summary.profit });
    for (const s of flat.by_strategy) {
      const acc = strategyAcc.get(s.strategy_name) || {
        strategy_name: s.strategy_name, bet_count: 0, settled_count: 0, pending_count: 0,
        hit_count: 0, invest: 0, settled_invest: 0, payout: 0,
        pnl: 0, recovery_rate: 0, hit_rate: 0,
      };
      acc.bet_count += s.bet_count;
      acc.settled_count += s.settled_count;
      acc.pending_count += s.pending_count;
      acc.hit_count += s.hit_count;
      acc.invest += s.invest;
      acc.settled_invest += s.settled_invest;
      acc.payout += s.payout;
      strategyAcc.set(s.strategy_name, acc);
    }
  }

  const by_strategy = finalizeStrategyStats(strategyAcc);

  return {
    from: fromIso,
    to: toIso,
    days: daily.length,
    summary: {
      total_bet: sumBet,
      settled_bet: sumSettledBet,
      total_payout: sumPayout,
      profit: sumPayout - sumSettledBet,
      recovery_rate: sumSettledBet > 0 ? (sumPayout / sumSettledBet) * 100 : 0,
      race_count: raceCount,
      bet_count: betCount,
      win_count: winCount,
      settled_count: settledCount,
      pending_count: pendingCount,
      reconciled_count: reconciledCount,
      all_reconciled: settledCount > 0 && reconciledCount === settledCount,
    },
    by_strategy,
    daily,
  };
}
