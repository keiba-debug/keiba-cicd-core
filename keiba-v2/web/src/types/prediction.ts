/**
 * 予想支援ツール関連の型定義
 */

/** 期待値馬データ */
export interface ExpectedValueHorse {
  umaban: string;
  horseName?: string;
  winOdds: number | null;
  estimatedWinRate: number | null;  // 予想勝率 (0-100)
  expectedValue: number | null;      // 期待値（金額）
  expectedValueRate: number | null;  // 期待値率（%）
  kellyFraction: number | null;      // Kelly係数
  recommendedBet: number | null;     // 推奨賭け金（円）
  recommendation: 'strong_buy' | 'buy' | 'neutral' | 'sell' | 'none';
}

/** 期待値計算APIレスポンス */
export interface ExpectedValueResponse {
  raceId: string;
  totalHorses: number;
  profitableCount: number;  // 期待値110%以上の馬数
  horses: ExpectedValueHorse[];
}

/** レーススコア */
export interface RaceScore {
  raceId: string;
  raceName: string;
  venue: string;
  raceNumber: number;
  distance: number;
  track: string;
  horseCount: number;
  dataCompleteness: number;  // データ完全性 (0-1)
  predictability: number;     // 予想しやすさ (0-1)
  confidence: number;         // 信頼度 (0-1)
  totalScore: number;         // 総合スコア (0-100)
  recommendation: '高' | '中' | '低' | '不可';
  reasons: string[];
}

/** レース選定APIレスポンス */
export interface RaceSelectionResponse {
  races: RaceScore[];
}

/** 馬券購入シミュレーション */
export interface BettingSimulation {
  betType: string;
  selectedHorses: string[];
  combinationCount: number;  // combinationsからリネーム
  totalCost: number;
  unitPrice: number;
}

/** ボックス買い */
export interface BoxBetting extends BettingSimulation {
  betType: '3連複' | '3連単' | '馬連' | '馬単' | 'ワイド';
}

/** フォーメーション買い */
export interface FormationBetting extends BettingSimulation {
  betType: '3連複' | '3連単';
  axis: string[];       // 軸馬
  second: string[];     // 2着候補
  third: string[];      // 3着候補
  combinations: string[][];  // 全組み合わせ
}

/** 印：位置評価 */
export type PositionMark = '🥇本命' | '🥈対抗' | '🥉穴' | '📍連下' | '❌消し';

/** 印：信頼度評価 */
export type ConfidenceMark = '★★★堅い' | '★★普通' | '★未知数';

/** 自分の印 */
export interface MyMark {
  position: PositionMark | null;
  confidence: ConfidenceMark | null;
}

/** 印から勝率への変換マップ */
export const WIN_RATE_MAP: Record<string, number> = {
  // 本命系
  '🥇本命-★★★堅い': 50,
  '🥇本命-★★普通': 40,
  '🥇本命-★未知数': 30,

  // 対抗系
  '🥈対抗-★★★堅い': 30,
  '🥈対抗-★★普通': 20,
  '🥈対抗-★未知数': 15,

  // 穴系
  '🥉穴-★★★堅い': 15,
  '🥉穴-★★普通': 10,
  '🥉穴-★未知数': 5,

  // 連下系
  '📍連下-★★★堅い': 8,
  '📍連下-★★普通': 5,
  '📍連下-★未知数': 3,

  // 消し
  '❌消し-★★★堅い': 0,
  '❌消し-★★普通': 0,
  '❌消し-★未知数': 0,
};

/** 印から勝率を計算 */
export function convertMarkToWinRate(mark: MyMark): number | null {
  if (!mark.position || !mark.confidence) return null;
  const key = `${mark.position}-${mark.confidence}`;
  return WIN_RATE_MAP[key] ?? null;
}
