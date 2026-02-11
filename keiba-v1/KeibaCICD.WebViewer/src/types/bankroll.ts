/**
 * 資金管理の型定義
 */

// 資金履歴のエントリタイプ
export type FundEntryType = 'deposit' | 'withdraw' | 'betting_result';

// 資金履歴エントリ
export interface FundEntry {
  id: string;                    // ユニークID（YYYYMMDD-XXX形式）
  date: string;                  // 日付（YYYYMMDD形式）
  type: FundEntryType;           // エントリタイプ
  amount: number;                // 金額（プラス/マイナス）
  balance: number;               // この時点の残高
  description?: string;          // 説明（入金元、出金先など）
  reference_date?: string;       // 競馬収支の場合、対象日付
  betting_detail?: BettingDetail; // 競馬収支の詳細
  created_at: string;            // 作成日時（ISO形式）
}

// 競馬収支の詳細
export interface BettingDetail {
  total_bet: number;             // 購入合計
  total_payout: number;          // 払戻合計
  profit: number;                // 収支
  recovery_rate: number;         // 回収率
  race_count: number;            // レース数
  win_count: number;             // 的中数
}

// 資金管理の設定
export interface FundConfig {
  initial_balance: number;       // 初期資金
  created_at: string;            // 開始日時
  updated_at: string;            // 最終更新日時
}

// 資金履歴全体
export interface FundHistory {
  config: FundConfig;
  entries: FundEntry[];
}

// 的中馬券コレクション
export interface WinningTicket {
  id: string;                    // ユニークID
  date: string;                  // 日付（YYYYMMDD形式）
  venue: string;                 // 競馬場
  race_number: number;           // レース番号
  race_name: string;             // レース名
  bet_type: string;              // 券種
  selection: string;             // 買い目
  amount: number;                // 購入金額
  payout: number;                // 払戻金額
  odds: number;                  // オッズ
  profit: number;                // 利益
}

// コレクション統計
export interface CollectionStats {
  total_wins: number;            // 的中総数
  total_profit: number;          // 総利益
  highest_payout: WinningTicket | null;  // 最高配当
  highest_odds: WinningTicket | null;    // 最高オッズ
  manba_count: number;           // 万馬券数
  consecutive_max: number;       // 最大連続的中
}

// 期間別サマリー
export interface PeriodSummary {
  period: string;                // 期間名（今月、先月、全期間など）
  start_date: string;            // 開始日
  end_date: string;              // 終了日
  total_bet: number;             // 購入合計
  total_payout: number;          // 払戻合計
  profit: number;                // 収支
  recovery_rate: number;         // 回収率
  race_count: number;            // レース数
  win_count: number;             // 的中数
}

// グラフ用データポイント
export interface ChartDataPoint {
  date: string;                  // 日付
  balance: number;               // 残高
  profit?: number;               // その日の収支
}
