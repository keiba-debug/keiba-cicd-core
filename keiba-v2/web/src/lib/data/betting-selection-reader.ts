/**
 * 券種選択ビュー reader (Session 140 / bettype-selection-roadmap Phase 3)
 *
 * Python (ml/strategies/bettype_selection.py) が書く
 * races/YYYY/MM/DD/betting_selection.json を読み込む。
 *
 * Phase2 (券種効率) が「各プランの (的中確率, 合成オッズ, 期待リターン)」を並べる判断支援なら、
 * Phase3 はそこから「実際にどの券種を買うか / 降りるか」を決めた結果 (selected/skipped) を持つ。
 *
 * ★誤誘導防止 (シズネ Session 138 置き土産・本モジュールの核心制約):
 *   vs_tansho ('合成<>単') は「広げる相対妙味」であって EV の絶対水準ではない。
 *   fund 判断は EV 絶対水準 (should_fund) のみ。 vs_tansho は参考表示。 「広げ得 ≠ 儲かる」。
 *
 * 計算・選択ロジックの Single Source of Truth は Python 側 (test 31 件)。 web は読むだけ。
 */
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export type BetTypeKey =
  | 'tansho' | 'fukusho' | 'umaren' | 'wide'
  | 'umatan' | 'sanrenpuku' | 'sanrentan';

/** fund 対象に選ばれたプラン */
export interface SelectedPlan {
  bet_type: BetTypeKey;
  label: string;                     // "馬単 ◎→相手3"
  legs: number[][];                  // 各点の馬番組
  hit_prob: number;                  // P(プラン内 ≥1点的中)
  expected_return: number | null;    // EV = Σpₖ/Σ(1/oₖ)。 単勝/複勝(基準)は null になりうる
  synthetic_odds: number | null;     // 合成オッズ G。 単勝は null
  vs_tansho: 'lt' | 'gt' | null;     // 合成<単='lt' / 'gt' / null(基準)。 参考表示のみ
  select_reason: string;             // なぜ fund するか
}

/** 降りた (見送った) プラン */
export interface SkippedPlan {
  bet_type: BetTypeKey;
  label: string;
  expected_return: number | null;
  vs_tansho: 'lt' | 'gt' | null;
  skip_reason: string;               // 「EV<floor」「合成<=単で広げ妙味薄」等
}

export interface BetSelection {
  race_id: string;
  date: string | null;
  venue_name: string | null;
  race_number: number | null;
  grade: string;
  axis_umaban: number;
  axis_name: string;
  axis_odds: number | null;
  strategy: string;                  // 実効戦略 ('skip_all' を含む)
  requested_strategy: string;        // CLI 指定の戦略 (skip_all 自動フォールバック前)
  ev_floor: number;
  taste: string | null;              // 妙味軸モード (hole_seeker 時) or null
  specialist: string | null;         // 'niigata1000' 等
  selected_plans: SelectedPlan[];
  skipped_plans: SkippedPlan[];
  decision_reason: string;           // 「広げ得≠儲かる」を必ず含意
  warnings: string[];
}

export interface BettingSelectionFile {
  strategy: string;                  // selective_loader 互換のため常に 'selective'
  version: string;
  description: string;
  generated_at: string;
  selection_strategy: string;        // concentrate | ev_floor | spread_if_worth | hole_seeker
  ev_floor: number;
  taste: string | null;
  n_races: number;
  n_bets: number;
  selections: BetSelection[];
  bets: unknown[];                   // selective_loader 互換 (本ビューでは未使用)
}

/** 単一レースの結果 + どう生成されたかのメタ */
export interface RaceSelectionResult {
  selection: BetSelection;
  selection_strategy: string;
  ev_floor: number;
  taste: string | null;
  generated_at: string;
}

/** raceId (16桁 YYYYMMDDJJKKNNRR) → date YYYY-MM-DD。 16桁以外は null */
function dateFromRaceId(raceId: string): string | null {
  if (!raceId || raceId.length !== 16 || !/^\d{16}$/.test(raceId)) return null;
  return `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`;
}

/** 日別 artifact を読み込む */
export function getBettingSelectionByDate(date: string): BettingSelectionFile | null {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, 'betting_selection.json');
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as BettingSelectionFile;
  } catch {
    return null;
  }
}

/** 単一レースの券種選択結果 + メタを返す (無ければ null) */
export function getBettingSelectionByRace(raceId: string): RaceSelectionResult | null {
  const date = dateFromRaceId(raceId);
  if (!date) return null;
  const file = getBettingSelectionByDate(date);
  if (!file) return null;
  const selection = file.selections.find((s) => String(s.race_id) === String(raceId));
  if (!selection) return null;
  return {
    selection,
    selection_strategy: file.selection_strategy,
    ev_floor: file.ev_floor,
    taste: file.taste,
    generated_at: file.generated_at,
  };
}
