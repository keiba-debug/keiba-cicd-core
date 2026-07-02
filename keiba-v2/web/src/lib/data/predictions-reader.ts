/**
 * 予測データリーダー
 * races/YYYY/MM/DD/predictions.json を読み込む
 * + レース結果読み込み（着順・確定オッズ）
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import { getDbRaceInfoByDate, trackTypeToJapanese } from './db-race';

// --- 型定義 ---

export interface PredictionEntry {
  umaban: number;
  horse_name: string;
  odds: number;
  popularity: number;
  // Place predictions (is_top3) — Place model (P)
  pred_proba_p: number;       // P(top3) Place model
  pred_proba_p_raw?: number;  // P(top3) raw (non-normalized, for Kelly)
  rank_p: number;
  odds_rank: number;
  vb_gap: number;
  is_value_bet: boolean;
  // Win predictions (is_win) — Win model (W)
  pred_proba_w?: number;      // P(win) Win model (raw normalized, NOT calibrated)
  pred_proba_w_cal?: number;  // P(win) calibrated (IsotonicRegression, use for EV calculation)
  rank_w?: number;
  win_vb_gap?: number;
  // Place odds from DB
  place_odds_min?: number;
  place_odds_max?: number;
  // EV (期待値)
  win_ev?: number;     // P(win) × 単勝オッズ
  place_ev?: number;   // P(top3) × 複勝オッズ最低値
  // AR: Aura Rating (v5.19)
  predicted_margin?: number | null;  // AR — グレード補正済みの絶対能力指数 (高い=強い)
  ar_deviation?: number | null;      // AR偏差値 — レース内相対評価 (mean=50, std=10)
  dev_gap?: number;                  // 偏差値gap — z-score(model) - z-score(market)
  // JRDB IDM (Session 90)
  jrdb_idm?: number;          // JRDB 事前IDM（今回レースのJRDB予測値）
  // keibabook
  kb_mark: string;
  kb_mark_point: number;
  kb_training_arrow: string;
  kb_rating: number;
  kb_comment: string;
  // 降格ローテ (v5.1)
  koukaku_rote_count?: number;
  is_koukaku_venue?: number;
  is_koukaku_female?: number;
  is_koukaku_season?: number;
  is_koukaku_distance?: number;
  is_koukaku_turf_to_dirt?: number;
  is_koukaku_handicap?: number;
  // コメントNLPスコア (v5.3)
  comment_stable_condition?: number;   // 厩舎談話 仕上がり度 (-3〜+3)
  comment_stable_confidence?: number;  // 厩舎談話 自信度 (-3〜+3)
  comment_stable_mark?: number;        // 厩舎談話 印 (0-4: ◎=4,○=3,△=1)
  comment_memo_condition?: number;     // 次走メモ 仕上がり度 (-3〜+3)
  comment_memo_trouble_score?: number; // 次走メモ トラブル/ポジティブ (-3〜+3)
  comment_has_stable?: number;         // 厩舎談話 データ有無 (0/1)
  comment_has_interview?: number;      // インタビュー データ有無 (0/1)
  // 基準オッズ比較 (Session 92)
  base_odds?: number;                  // JRDB基準オッズ（朝オッズ推定）
  odds_move?: number;                  // 実オッズ/基準オッズ (>1=人気落ち, <1=人気上昇)
  market_signal?: string;              // 市場シグナル (鉄板/軸向き/妙味/想定通り/人気しすぎ/穴注目)
  // 未知数度 (Session 119)
  novelty_score?: number;              // 0-6 合計スコア
  novelty_career_short?: number;       // キャリア3走以下 (0/1)
  novelty_first_surface?: number;      // 初芝 or 初ダート (0/1)
  novelty_first_distance?: number;     // 初距離帯 ±200m経験なし (0/1)
  novelty_first_venue?: number;        // 初コース (0/1)
  novelty_long_layoff?: number;        // 長期休養 140日+ (0/1)
  novelty_jockey_change?: number;      // 騎手乗替 (0/1)
  ar_deviation_adj?: number | null;    // AR偏差値の未知数度補正版
  // E-005 理由タグ（接戦◎/出遅れ注意/低信頼）— 表示専用・買い目には影響しない
  reason_tags?: ReasonTag[];
  // vega-niigata1000 overlay (Phase 3d)
  niigata1000?: NiigataOverlay;
  // Regulus 脚質・能力プロファイル (Session 178・表示専用オーバーレイ)
  legProfile?: LegProfile;
  // Regulus 専用モデル 第二意見 (Session 182・3歳上芝OP+のみ・表示専用)
  regulus?: RegulusScore;
}

/** Regulus 専用モデル (ml/nova/predict_regulus.py が regulus_scores.json に出力) の第二意見。
 *  3歳上×芝×OP以上のみ対象。payoutエッジは狙わない — polaris(汎用)との見解差を示す表示専用シグナル。 */
export interface RegulusScore {
  proba_p: number;             // 3着内確率 (calibrated, Regulus lean_plus モデル)
  proba_w?: number;            // 勝率 (calibrated)
  rank_p: number;              // Regulus内での順位 (対象レース内)
  rank_w?: number;
  rank_blend?: number;         // P/W合成本命順位 (rankavg・S183検証で重賞Top1最良の本命シグナル)
  blend_score?: number;        // 0.5*proba_p + 0.5*proba_w
  polaris_rank_p?: number;     // polaris(汎用)のP順位 — 比較用
  polaris_rank_w?: number;
  delta_rank_p?: number;       // polaris順位 - Regulus順位 (正=Regulusがより強気)
  delta_rank_w?: number;
}

/** JRDB展開予想の1コマ (KYI 第6版・当日朝公表=リークフリー)。
 *  diff=先頭からの累積差(半馬身単位)・inout=1(最内)〜5(大外)。
 *  道中→残り3F→ゴールの3コマ = 隊列アニメーションのキーフレーム。 */
export interface JrdbTenkaiFrame {
  order: number;                // 予想順位 (1=先頭)
  diff: number | null;          // 先頭からの差 (半馬身単位・先頭=0)
  inout: number | null;         // 内外 1(最内)〜5(大外)
}

/** JRDB展開予想オーバーレイ (leg_profiles.json の jrdb キー・Session 186)。
 *  ⚠ pred系指数は負値中心(mean≈-13・range -50〜+37)。>0 を有効値扱いすると94%消える。 */
export interface JrdbTenkaiPred {
  pace?: string | null;         // JRDB予想ペース H/M/S
  ten_idx?: number | null;      // テン指数 (前半スピード)
  agari_idx?: number | null;    // 上がり指数
  position_idx?: number | null; // 位置指数
  dochu?: JrdbTenkaiFrame;      // 道中
  f3?: JrdbTenkaiFrame;         // 残り3F
  goal?: JrdbTenkaiFrame;       // ゴール
}

/** Regulus 脚質・能力プロファイル (ml/nova/leg_profile.py が leg_profiles.json に出力)。
 *  上がり3軸=JRDB指数ベース(テン/上がり/持続 偏差値・平均50)。印/解説用・買い目には影響しない。 */
export interface LegProfile {
  kyakushitsu: string;          // 逃げ/先行/差し/追込 (n=0 のとき "—")
  ten: number | null;           // テン力 偏差値 (前半スピード/先行力)
  agari: number | null;         // 上がり力 偏差値 (瞬発/末脚)
  sustain: number | null;       // 持続力 偏差値 (後半垂れない=スタミナ)
  ten_grade: string;            // S/A/B/C/D
  agari_grade: string;
  sustain_grade: string;
  tags: string[];               // 言語化タグ (末脚一閃型/先行押し切り型/バテない持続型/上昇気配 等)
  n: number;                    // 集計に使った過去走数 (0=過去走なし・JRDB展開のみの馬)
  jrdb?: JrdbTenkaiPred;        // JRDB展開予想 (統合隊列図用・Session 186)
}

/** E-005 理由タグ（表示専用）。Python ml/strategies/reason_tags.py が生成。 */
export interface ReasonTag {
  type: 'close_finish' | 'slow_start' | 'low_confidence';
  label: string;                 // 表示ラベル（接戦◎/出遅れ注意/低信頼）
  level: 'good' | 'caution' | 'warn';
  detail: string;                // ツールチップ用の根拠説明
  low_confidence: boolean;       // 根拠データが小標本か
}

/** vega-niigata1000 ルールエンジン v0.2 オーバーレイ結果 (千直レースのみ) */
export interface NiigataOverlay {
  display_score: number;            // 補正後の確率 [0,1] (UI表示用、常時値あり)
  selection_score: number | null;   // ランキング用 (除外時は null)
  rule_logit: number;               // STEP B〜E 加減点合計 (logit空間)
  delta_p: number;                  // display_score - polaris_p (確率差)
  is_rejected: boolean;             // STEP F 除外推奨
  fired_rule_ids: string[];         // 発火ルールID
  step_breakdown: Record<string, number>;  // {STEP: logit寄与} 例: {"B": 0.5, "D-2": 0.2}
  explanation: string;              // 整形済み説明文 (改行込み)
  confidence: '高' | '中' | '低';
  wakuban?: number;
  jockey_name?: string;
  trainer_name?: string;
  sex?: string;
  age?: number;
}

export interface PredictionRace {
  race_id: string;
  date: string;
  venue_name: string;
  race_number: number;
  distance: number;
  track_type: string;
  num_runners: number;
  grade?: string;
  race_name?: string;   // レース名 (grade 空のときのクラス判定フォールバック源・逆張り単表示で使用)
  age_class?: string;
  is_handicap?: boolean;
  is_female_only?: boolean;
  closing_race_proba?: number;
  race_confidence?: number;
  p_top1_gap?: number;
  ard_spread?: number;
  entries: PredictionEntry[];
  // vega-niigata1000 (Phase 3d)
  niigata1000_applied?: boolean;
}

// --- Server-side bet recommendations (generated by bet_engine.py) ---

export interface ServerBetRecommendation {
  race_id: string;
  umaban: number;
  horse_name: string;
  bet_type: '単勝' | '複勝' | '単複';
  strength: 'strong' | 'normal';
  win_amount: number;
  place_amount: number;
  gap: number;
  dev_gap?: number;           // 偏差値gap (z-score差)
  vb_score?: number;          // コンポジットVBスコア (0-10)
  win_gap: number;
  predicted_margin: number;
  win_ev: number | null;
  place_ev: number | null;
  kelly_raw: number;
  kelly_capped: number;
  is_danger: boolean;
  danger_score: number;
  odds: number;
  place_odds_min: number | null;
  ar_deviation: number | null;
  adaptive_rule?: string;     // adaptive: マッチしたルール名 (danger_sniper/high_ev_win/relaxed_base)
}

export interface ServerBetPreset {
  params: {
    win_min_ev?: number;
    win_min_gap: number;
    win_min_rating: number;
    win_min_ar_deviation?: number;
    win_max_rank?: number;
    place_min_gap: number;
    place_min_rating: number;
    place_min_ar_deviation?: number;
    place_min_ev: number;
    kelly_fraction: number;
  };
  bets: ServerBetRecommendation[];
  summary: {
    total_bets: number;
    total_amount: number;
    win_bets: number;
    place_bets: number;
    win_amount: number;
    place_amount: number;
    strong_count: number;
    danger_count: number;
  };
}

export type ServerRecommendations = Record<string, ServerBetPreset>;

export interface VbExclusion {
  race_id: string;
  umaban: number;
  horse_name: string;
  gap: number;
  predicted_margin: number;
  exclusion_reason: string;
}

// --- Multi-leg recommendations (generated by simulate_multi_leg.py) ---

export interface MultiLegRecommendation {
  race_id: string;
  venue: string;
  race_number: number;
  strategy: string;       // e.g. "I.VB馬単1点", "G.VB馬単流", "K.危険裏ワイド"
  ticket_type: string;    // "umatan" | "umaren" | "wide" | "sanrenpuku"
  horses: number[];       // 馬番の配列 (馬単は順序あり)
  horse_names: string[];  // 馬名の配列
  cost: number;           // 投資額 (100円単位)
  note: string;           // 補足情報 (ARd/odds)
}

export interface PredictionsLive {
  version: string;
  created_at: string;
  date: string;
  model_version: string;
  odds_source: string;
  db_odds_coverage: string;
  races: PredictionRace[];
  has_closing_model?: boolean;
  closing_model_version?: string;
  recommendations?: ServerRecommendations;
  multi_leg_recommendations?: MultiLegRecommendation[];
  sanrentan_formation?: MultiLegRecommendation[];
  sanrentan_distortion?: MultiLegRecommendation[];
  vb_exclusions?: VbExclusion[];
  summary: {
    total_races: number;
    total_entries: number;
    value_bets: number;
  };
}

/**
 * 日別 predictions.json (races/YYYY/MM/DD/predictions.json) を読み込む
 */
export function getPredictionsByDate(date: string, version?: string | null): PredictionsLive | null {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const fileName = version ? `predictions_${version}.json` : 'predictions.json';
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, fileName);
    if (!fs.existsSync(filePath)) return null;
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content) as PredictionsLive;
  } catch {
    return null;
  }
}

/**
 * 脚質・能力プロファイル (races/YYYY/MM/DD/leg_profiles.json) を読み、
 * predictions の各 entry に legProfile をマージ (race_id + umaban 突合)。
 * ファイルが無ければ無変更 (graceful)。表示専用・買い目には影響しない。
 */
export function enrichPredictionsWithLegProfiles(data: PredictionsLive): PredictionsLive {
  try {
    const [y, m, d] = data.date.split('-');
    if (!y || !m || !d) return data;
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, 'leg_profiles.json');
    if (!fs.existsSync(filePath)) return data;
    const byRace = JSON.parse(fs.readFileSync(filePath, 'utf-8')) as Record<string, Record<string, LegProfile>>;
    let enriched = 0;
    for (const race of data.races) {
      const per = byRace[race.race_id];
      if (!per) continue;
      for (const entry of race.entries) {
        const lp = per[String(entry.umaban)];
        if (lp) { entry.legProfile = lp; enriched++; }
      }
    }
    if (enriched > 0) {
      console.log(`[predictions-reader] leg-profile enrichment: ${enriched} entries`);
    }
  } catch (error) {
    console.error('[predictions-reader] leg-profile enrichment failed (non-fatal):', error);
  }
  return data;
}

/**
 * Regulus 専用モデル(3歳上芝OP+)の第二意見 (races/YYYY/MM/DD/regulus_scores.json) を読み、
 * predictions の各 entry に regulus をマージ (race_id + umaban 突合)。
 * ファイルが無い/対象レースが無ければ無変更 (graceful)。表示専用・買い目には影響しない。
 */
export function enrichPredictionsWithRegulus(data: PredictionsLive): PredictionsLive {
  try {
    const [y, m, d] = data.date.split('-');
    if (!y || !m || !d) return data;
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, 'regulus_scores.json');
    if (!fs.existsSync(filePath)) return data;
    const snap = JSON.parse(fs.readFileSync(filePath, 'utf-8')) as {
      races: Record<string, { entries: Record<string, RegulusScore> }>;
    };
    let enriched = 0;
    for (const race of data.races) {
      const per = snap.races[race.race_id];
      if (!per) continue;
      for (const entry of race.entries) {
        const rs = per.entries[String(entry.umaban)];
        if (rs) { entry.regulus = rs; enriched++; }
      }
    }
    if (enriched > 0) {
      console.log(`[predictions-reader] regulus enrichment: ${enriched} entries`);
    }
  } catch (error) {
    console.error('[predictions-reader] regulus enrichment failed (non-fatal):', error);
  }
  return data;
}

/**
 * 指定日付で利用可能な predictions バージョン一覧を返す
 */
export function getAvailablePredictionVersions(date: string): string[] {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return [];
    const dayDir = path.join(DATA3_ROOT, 'races', y, m, d);
    if (!fs.existsSync(dayDir)) return [];
    const files = fs.readdirSync(dayDir);
    const versions: string[] = [];
    // タイムスタンプ付きアーカイブ除外: predictions_v7.1_20260301T101905.json
    const timestampPattern = /^\d{8}T\d{4,6}$/;
    for (const f of files) {
      const match = f.match(/^predictions_(.+)\.json$/);
      if (match) {
        const ver = match[1];
        const lastPart = ver.split('_').pop() || '';
        if (timestampPattern.test(lastPart)) continue;
        versions.push(ver);
      }
    }
    return versions;
  } catch {
    return [];
  }
}

/**
 * predictions.json が存在する日付一覧を返す（降順）
 */
export function getAvailablePredictionDates(): string[] {
  try {
    const racesDir = path.join(DATA3_ROOT, 'races');
    if (!fs.existsSync(racesDir)) return [];
    const dates: string[] = [];

    const years = fs.readdirSync(racesDir).filter(y => /^\d{4}$/.test(y));
    for (const y of years) {
      const yearDir = path.join(racesDir, y);
      const months = fs.readdirSync(yearDir).filter(m => /^\d{2}$/.test(m));
      for (const m of months) {
        const monthDir = path.join(yearDir, m);
        const days = fs.readdirSync(monthDir).filter(d => /^\d{2}$/.test(d));
        for (const d of days) {
          if (fs.existsSync(path.join(monthDir, d, 'predictions.json'))) {
            dates.push(`${y}-${m}-${d}`);
          }
        }
      }
    }

    return dates.sort().reverse();
  } catch {
    return [];
  }
}

/**
 * predictions の track_type/distance が欠落しているレースをDB (RACE_SHOSAI) で補完
 * Server Component から呼び出す（async）
 */
export async function enrichPredictionsFromDb(data: PredictionsLive): Promise<PredictionsLive> {
  // Check if any races need enrichment
  const needsEnrichment = data.races.some(r => !r.track_type || !r.distance);
  if (!needsEnrichment) return data;

  try {
    const datePrefix = data.date.replace(/-/g, '');
    const dbInfo = await getDbRaceInfoByDate(datePrefix);
    if (dbInfo.size === 0) return data;

    let enriched = 0;
    for (const race of data.races) {
      const info = dbInfo.get(race.race_id);
      if (!info) continue;

      if (!race.track_type && info.trackType) {
        // Use Japanese format for display consistency (芝/ダ instead of turf/dirt)
        race.track_type = trackTypeToJapanese(info.trackType) || info.trackType;
        enriched++;
      }
      if (!race.distance && info.distance > 0) {
        race.distance = info.distance;
      }
    }

    if (enriched > 0) {
      console.log(`[predictions-reader] DB enrichment: ${enriched} races updated with track_type/distance`);
    }
  } catch (error) {
    console.error('[predictions-reader] DB enrichment failed (non-fatal):', error);
  }

  return data;
}

// --- レース結果 ---

export interface RaceResultEntry {
  umaban: number;
  finish_position: number;  // 0 = 未確定/取消
  time: string;
  last_3f: number;
  odds: number;             // 確定単勝オッズ
}

// raceId → umaban → RaceResultEntry
export type RaceResultsMap = Record<string, Record<number, RaceResultEntry>>;

/**
 * 指定日のレース結果を読み込む
 * race_*.json からfinish_position等を抽出
 */
export function getResultsByDate(date: string): RaceResultsMap {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return {};
    const dayPath = path.join(DATA3_ROOT, 'races', y, m, d);
    if (!fs.existsSync(dayPath)) return {};

    const files = fs.readdirSync(dayPath).filter(f => /^race_\d.*\.json$/.test(f));
    const results: RaceResultsMap = {};

    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(dayPath, file), 'utf-8');
        const data = JSON.parse(content);
        const raceId = data.race_id as string;
        if (!raceId || !data.entries) continue;

        const entries: Record<number, RaceResultEntry> = {};
        let hasResults = false;

        for (const e of data.entries) {
          if (e.finish_position > 0) hasResults = true;
          entries[e.umaban] = {
            umaban: e.umaban,
            finish_position: e.finish_position || 0,
            time: e.time || '',
            last_3f: e.last_3f || 0,
            odds: e.odds || 0,
          };
        }

        if (hasResults) {
          results[raceId] = entries;
        }
      } catch {
        continue;
      }
    }

    return results;
  } catch {
    return {};
  }
}
