export interface CharacterHistoryPoint {
  date: string | null;
  bankroll: number;
}

export interface CharacterMonthly {
  month: string;
  fire: number;
  inv: number;
  ret: number;
  hits: number;
  roi: number;
  pnl: number;
}

export interface CharacterResult {
  key: string;
  name: string;
  templates: string[];
  template_meta: { key: string; label: string }[];
  mark_mode: string;
  ringfenced: boolean;
  odds_dependent: boolean;
  day_fraction: number;
  unit_fraction: number;
  eff_w0: number;
  // 複利 (全期間・後知恵込み表示用)
  final_w: number;
  growth_pct: number;
  max_dd_pct: number;
  sharpe: number;
  ruin_prob_pct: number;
  flat_roi_pct: number;
  tail_day_rate: number;
  bet_days: number;
  // 検証規律 (flat 100円集計)
  roi: number;
  roi_train: number;
  roi_valid: number;
  median_roi: number;
  plus_months: string;
  roi_first_half: number;
  roi_second_half: number;
  hit_rate: number;
  fire: number;
  hits: number;
  monthly: CharacterMonthly[];
  history: CharacterHistoryPoint[];
  note: string;
  warnings: string[];
}

export interface CharacterSimData {
  created_at: string;
  sim_version: string;
  initial_bankroll: number;
  split_date: string;
  data_source: string;
  period_start: string;
  period_end: string;
  total_races: number;
  months: string[];
  characters: CharacterResult[];
}
