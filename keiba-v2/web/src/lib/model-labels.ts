/**
 * Centralized display name constants for ML models and concepts.
 * Internal keys (model_a, pred_proba_v, etc.) and JSON field names stay unchanged.
 * Only display labels used in the web frontend are defined here.
 */

// --- Model Display Names ---

export const MODEL_NAMES = {
  accuracy:     { full: '好走 市場', short: '市場', letter: 'A', target: '3着内', desc: '全特徴量で3着内を予測（オッズ・人気含む）。VB未使用' },
  value:        { full: '好走 独自', short: '独自', letter: 'V', target: '3着内', desc: '市場系除外で3着内を予測 → VB: V%, Gap, 頭%' },
  win_accuracy: { full: '勝利 市場', short: 'W市場', letter: 'W', target: '1着', desc: '全特徴量で1着を予測（オッズ・人気含む）。VB未使用' },
  win_value:    { full: '勝利 独自', short: 'W独自', letter: 'WV', target: '1着', desc: '市場系除外で1着を予測 → VB: WV%, EV, 頭%' },
  regression:   { full: 'Aura Rating', short: 'AR', letter: 'R', target: '着差', desc: '着差回帰（市場系除外）→ VB: AR, ARd, 複EV' },
} as const;

export type ModelKey = keyof typeof MODEL_NAMES;

// --- Model Groups ---

export const MODEL_GROUPS = {
  place:      { label: '好走モデル (3着内)', color: 'blue' },
  win:        { label: '勝利モデル (1着)', color: 'emerald' },
  regression: { label: 'AR: Aura Rating (着差回帰)', color: 'amber' },
} as const;

// --- Concept Names (tooltips for VR, Gap etc.) ---

export const CONCEPT_TIPS = {
  vr:    '独自ランク — 好走 独自モデル(V)によるレース内順位（1=最も能力が高い）',
  gap:   '乖離度 — 人気順位 - VR(好走 独自ランク)。大きいほど市場が過小評価している馬',
  ar:    'AR (Aura Rating) — ARモデル(回帰)による絶対能力指数。グレード補正済み',
  ard:   'ARd (AR偏差値) — レース内相対評価（mean=50, std=10）。50=レース平均',
  vb:    'Value Bet — EV≥1.0 かつ ARd≥50。期待値プラスかつレース平均以上の能力',
  winEv: '単勝EV — 勝利 独自モデル(WV)の勝率 × 単勝オッズ。1.0超えで期待値プラス',
  placeEv: '複勝EV — ARモデル(回帰)の好走確率 × 複勝最低オッズ。1.0超えで期待値プラス',
} as const;

// --- Preset Labels ---

export const PRESET_LABELS: Record<string, string> = {
  win_only: '単勝のみ',
  conservative: '堅実',
  standard: '標準',
  wide: '広め',
  aggressive: '攻め',
};
