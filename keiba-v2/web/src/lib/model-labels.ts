/**
 * Centralized display name constants for ML models and concepts.
 * Internal keys (model_a, pred_proba_v, etc.) and JSON field names stay unchanged.
 * Only display labels used in the web frontend are defined here.
 */

// --- Model Display Names ---

export const MODEL_NAMES = {
  accuracy:     { full: '好走 市場', short: '市場', letter: 'A', target: '3着内', desc: '全特徴量で3着内を予測（オッズ・人気含む）' },
  value:        { full: '好走 独自', short: '独自', letter: 'V', target: '3着内', desc: '市場系除外で3着内を予測（独自能力評価）' },
  win_accuracy: { full: '勝利 市場', short: 'W市場', letter: 'W', target: '1着', desc: '全特徴量で1着を予測（オッズ・人気含む）' },
  win_value:    { full: '勝利 独自', short: 'W独自', letter: 'WV', target: '1着', desc: '市場系除外で1着を予測（独自能力評価）' },
  regression:   { full: 'チャクラ', short: 'チャクラ', letter: 'CK', target: '着差', desc: '能力予測モデル（市場系除外・着差回帰）' },
} as const;

export type ModelKey = keyof typeof MODEL_NAMES;

// --- Model Groups ---

export const MODEL_GROUPS = {
  place:      { label: '好走モデル (3着内)', color: 'blue' },
  win:        { label: '勝利モデル (1着)', color: 'emerald' },
  regression: { label: '能力予測モデル (着差)', color: 'amber' },
} as const;

// --- Concept Names (tooltips for VR, Gap etc.) ---

export const CONCEPT_TIPS = {
  vr:    '独自ランク — 好走 独自モデルによるレース内順位（1=最も能力が高い）',
  gap:   '乖離度 — 人気順位 - VR。大きいほど市場が過小評価している馬',
  margin: 'チャクラ — 能力予測(秒)。勝ち馬とのタイム差予測。低いほど勝ちに近い',
  vb:    'Value Bet — VR≤3 かつ Gap≥3 の馬。独自モデル上位評価だが人気薄',
  winEv: '単勝EV — P(win) × 単勝オッズ。1.0超えで期待値プラス',
  placeEv: '複勝EV — P(top3) × 複勝最低オッズ。1.0超えで期待値プラス',
} as const;

// --- Preset Labels ---

export const PRESET_LABELS: Record<string, string> = {
  win_only: '単勝のみ',
  conservative: '堅実',
  standard: '標準',
  aggressive: '攻め',
};
