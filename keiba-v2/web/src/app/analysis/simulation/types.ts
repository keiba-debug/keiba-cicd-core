export interface SimulationHistoryPoint {
  date: string | null;
  bankroll: number;
}

export interface SimulationResult {
  preset: string;
  budget_label: string;
  mode: string;
  label: string;
  final_bankroll: number;
  roi_pct: number;
  flat_roi: number;
  max_dd: number;
  sharpe: number;
  bet_days: number;
  total_bets: number;
  win_days: number;
  lose_days: number;
  max_loss_streak: number;
  max_win_streak: number;
  history: SimulationHistoryPoint[];
}

export interface BudgetConfig {
  label: string;
  pct: number;
}

export interface StrategyConfig {
  mode: string;
  label: string;
}

export interface SimulationData {
  initial_bankroll: number;
  budget_configs: BudgetConfig[];
  strategies: StrategyConfig[];
  presets: string[];
  results: SimulationResult[];
}
