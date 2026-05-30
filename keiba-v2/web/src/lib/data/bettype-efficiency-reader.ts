/**
 * 券種効率ビュー reader (Session 138 / bettype-selection-roadmap Phase 2)
 *
 * Python (ml/strategies/bettype_efficiency.py) が書く
 * races/YYYY/MM/DD/bettype_efficiency.json を読み込む。
 *
 * ハーヴィル確率 × 市場オッズ で各券種プランの
 * (的中確率, 合成オッズ, 期待リターン) を保持し、 合成オッズ<単オッズ を可視化する。
 * 計算の Single Source of Truth は Python 側 (テスト済)。 web は読むだけ。
 */
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

/** 1馬の強さ判定 (W/P/ADR 総合 + specialist overlay) */
export interface HorseStrength {
  umaban: number;
  horse_name: string;
  win_prob: number;            // ハーヴィル入力 (正規化済 pred_proba_w_cal)
  odds: number | null;         // 単勝
  place_odds_min: number | null;
  pred_w: number | null;
  pred_p: number | null;       // specialist 適用時は display_score
  ar_deviation: number | null;
  z_w: number | null;
  z_p: number | null;
  z_adr: number | null;
  composite: number;
  p_source: 'model' | 'specialist';
  rank_w: number | null;
  rank_p: number | null;
  rank_adr: number | null;
  rank_composite: number | null;
}

export type BetTypeKey =
  | 'tansho' | 'fukusho' | 'umaren' | 'wide'
  | 'umatan' | 'sanrenpuku' | 'sanrentan';

/** 1プラン (軸からの広げ方) */
export interface EfficiencyPlan {
  bet_type: BetTypeKey;
  label: string;               // "馬連 ◎-相手3"
  legs: number[][];            // 各点の馬番組
  n_points: number;
  hit_prob: number;            // P(プラン内 ≥1点的中)
  sum_p: number;               // Σpₖ (期待的中点数)
  synthetic_odds: number | null;   // 合成オッズ G = 1/Σ(1/oₖ)
  expected_return: number | null;  // 期待リターン EV = Σpₖ/Σ(1/oₖ)
  odds_legs: (number | null)[];
  coverage: number;            // オッズが取れた点の割合
  vs_tansho: 'lt' | 'gt' | null;   // 合成<単='lt'(広げ意味薄) / 'gt'(広げ得) / null(基準)
}

export interface RaceEfficiency {
  race_id: string;
  date: string | null;
  venue_name: string | null;
  race_number: number | null;
  grade: string;
  track_type: string | null;
  distance: number | null;
  num_runners: number | null;
  axis_umaban: number;
  axis_name: string;
  axis_odds: number | null;
  partners: number[];
  weights: number[];           // [W, P, ADR]
  specialist: string | null;   // 'niigata1000' 等
  strengths: HorseStrength[];
  plans: EfficiencyPlan[];
  warnings: string[];
}

export interface BetTypeEfficiencyFile {
  schema_version: string;
  date: string;
  generated_at: string;
  weights: number[];
  n_partners: number;
  n_races: number;
  races: RaceEfficiency[];
}

/** raceId (16桁 YYYYMMDDJJKKNNRR) → date YYYY-MM-DD。 16桁以外は null */
function dateFromRaceId(raceId: string): string | null {
  if (!raceId || raceId.length !== 16 || !/^\d{16}$/.test(raceId)) return null;
  return `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`;
}

/** 日別 artifact を読み込む */
export function getBetTypeEfficiencyByDate(date: string): BetTypeEfficiencyFile | null {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, 'bettype_efficiency.json');
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as BetTypeEfficiencyFile;
  } catch {
    return null;
  }
}

/** 単一レースの券種効率を返す (無ければ null) */
export function getBetTypeEfficiencyByRace(raceId: string): RaceEfficiency | null {
  const date = dateFromRaceId(raceId);
  if (!date) return null;
  const file = getBetTypeEfficiencyByDate(date);
  if (!file) return null;
  return file.races.find((r) => String(r.race_id) === String(raceId)) ?? null;
}
