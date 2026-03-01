/**
 * Centralized display name constants for ML models and concepts.
 * Only display labels used in the web frontend are defined here.
 */

// --- Model Display Names ---

export const MODEL_NAMES = {
  place:  { full: '好走(P)', short: 'P', letter: 'P', target: '3着内', desc: '市場系除外で3着内を予測 → VB: P%, Gap, 頭%' },
  win:    { full: '勝利(W)', short: 'W', letter: 'W', target: '1着', desc: '市場系除外で1着を予測 → VB: W%, EV, 頭%' },
  aura:   { full: '能力(AR)', short: 'AR', letter: 'AR', target: '着差', desc: '着差回帰（市場系除外）→ VB: AR, ARd, 複EV' },
} as const;

export type ModelKey = keyof typeof MODEL_NAMES;

// --- Model Groups ---

export const MODEL_GROUPS = {
  place: { label: '好走モデル (3着内)', color: 'blue' },
  win:   { label: '勝利モデル (1着)', color: 'emerald' },
  aura:  { label: 'AR: Aura Rating (着差回帰)', color: 'amber' },
} as const;

// --- Concept Names (tooltips for PR, Gap etc.) ---

export const CONCEPT_TIPS = {
  pr:    'Placeランク — Placeモデル(P)によるレース内順位（1=最も能力が高い）',
  gap:   '乖離度 — 人気順位 - PR(Placeランク)。大きいほど市場が過小評価している馬',
  ar:    'AR (Aura Rating) — ARモデル(回帰)による絶対能力指数。グレード補正済み',
  ard:   'ARd (AR偏差値) — レース内相対評価（mean=50, std=10）。50=レース平均',
  vb:    'Value Bet — EV≥1.0 かつ ARd≥50。期待値プラスかつレース平均以上の能力',
  winEv: '単勝EV — Winモデル(W)の勝率 × 単勝オッズ。1.0超えで期待値プラス',
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
