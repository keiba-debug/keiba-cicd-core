/**
 * 管理画面用コマンド定義
 * 全コマンドがv2(keiba-v2/)ネイティブ — v1依存なし
 */

export type ActionType =
  | 'schedule'
  | 'basic'
  | 'paddok'
  | 'seiseki'
  | 'babakeikou'
  | 'batch_prepare'
  | 'batch_morning'
  | 'batch_after_race'
  | 'sunpyo_update'
  | 'calc_race_type_standards'   // レース特性基準値算出
  | 'calc_rating_standards'      // レイティング基準値算出
  | 'build_horse_name_index'     // 馬名インデックス作成
  | 'build_trainer_index'        // 調教師インデックス作成
  | 'analyze_trainer_patterns'   // 調教師パターン分析
  | 'analyze_training'           // 調教分析
  | 'rebuild_sire_stats'         // 血統統計再集計
  | 'rebuild_slow_start'         // 出遅れ分析再集計
  | 'v4_build_race'              // JRA-VAN → data3/races/
  | 'v4_predict'                 // ML予測 → races/YYYY/MM/DD/predictions.json
  | 'v4_pipeline'                // 上記を連結実行
  | 'vb_refresh';                // VB/買い目再計算（最新オッズ）

export interface ActionConfig {
  id: ActionType;
  label: string;
  description: string;
  icon: string;
  category: 'fetch' | 'generate' | 'batch' | 'update' | 'analysis';
  requiresDateRange?: boolean;  // 日付範囲が必要なアクション
  noDateRequired?: boolean;  // 日付不要のアクション
}

export interface CommandOptions {
  raceFrom?: number;
  raceTo?: number;
  track?: string;
}

export const ACTIONS: ActionConfig[] = [
  // --- 個別スクレイプ（keibabook）---
  {
    id: 'schedule',
    label: 'スケジュール取得',
    description: '開催日程を取得',
    icon: '📅',
    category: 'fetch',
  },
  {
    id: 'basic',
    label: '基本データ取得',
    description: '出馬表・調教・談話・勝因を取得→kb_ext構築',
    icon: '📋',
    category: 'fetch',
  },
  {
    id: 'paddok',
    label: 'パドック取得',
    description: 'パドック情報を取得→kb_ext更新',
    icon: '🐎',
    category: 'fetch',
  },
  {
    id: 'seiseki',
    label: '成績取得',
    description: 'レース結果を取得→kb_ext更新',
    icon: '🏆',
    category: 'fetch',
  },
  {
    id: 'babakeikou',
    label: '馬場情報取得',
    description: '当日の馬場傾向を取得',
    icon: '🌱',
    category: 'fetch',
  },
  // --- 一括実行 ---
  {
    id: 'batch_prepare',
    label: 'レース前準備',
    description: '日程→出馬表・調教→レースJSON構築（予測なし・前日夜実行）',
    icon: '🌅',
    category: 'batch',
  },
  {
    id: 'batch_morning',
    label: '当日朝予測',
    description: '馬場情報取得→ML予測（VB判定なし・当日朝）',
    icon: '☀️',
    category: 'batch',
  },
  {
    id: 'batch_after_race',
    label: 'レース後更新',
    description: 'パドック→成績→レースJSON更新→ML予測（レース後に実行）',
    icon: '🏁',
    category: 'batch',
  },
  // --- 補助 ---
  {
    id: 'sunpyo_update',
    label: '成績詳細取得',
    description: '寸評・インタビュー・次走メモを取得→kb_ext更新（翌日以降）',
    icon: '📝',
    category: 'update',
  },
  // --- データ分析 ---
  {
    id: 'calc_race_type_standards',
    label: 'レース特性基準値算出',
    description: 'RPCI瞬発戦/持続戦の基準値を算出',
    icon: '📊',
    category: 'analysis',
    noDateRequired: true,
  },
  {
    id: 'calc_rating_standards',
    label: 'レイティング基準値算出',
    description: 'クラス別レイティング統計・レースレベル判定基準を算出',
    icon: '📈',
    category: 'analysis',
    noDateRequired: true,
  },
  // --- インデックス ---
  {
    id: 'build_horse_name_index',
    label: '馬名インデックス構築',
    description: '馬名→血統番号の辞書を再構築（新馬登録時）',
    icon: '📖',
    category: 'generate',
    noDateRequired: true,
  },
  {
    id: 'build_trainer_index',
    label: '調教師インデックス構築',
    description: '調教師コード↔名前の対応辞書を構築',
    icon: '👨‍🏫',
    category: 'generate',
    noDateRequired: true,
  },
  {
    id: 'analyze_trainer_patterns',
    label: '調教師パターン分析(KB)',
    description: 'keibabook調教詳細×着順から調教師別好走パターンを統計分析',
    icon: '🔬',
    category: 'analysis',
    noDateRequired: true,
  },
  {
    id: 'analyze_training',
    label: '調教分析(JRA-VAN)',
    description: 'CK_DATA調教×レース成績の統合分析（全体+調教師別パターン）',
    icon: '🏋️',
    category: 'analysis',
    noDateRequired: true,
  },
  // --- 分析再集計（各分析ページから呼び出し）---
  {
    id: 'rebuild_sire_stats',
    label: '血統統計再集計',
    description: '種牡馬/母馬/母父の産駒成績を全レースから再集計',
    icon: '🧬',
    category: 'analysis',
    noDateRequired: true,
  },
  {
    id: 'rebuild_slow_start',
    label: '出遅れ分析再集計',
    description: '出遅れデータを全レースから再集計',
    icon: '🐌',
    category: 'analysis',
    noDateRequired: true,
  },
  // --- パイプライン・個別ステップ ---
  {
    id: 'v4_build_race',
    label: 'レースJSON構築',
    description: 'JRA-VAN SE/SR→レースJSON再構築',
    icon: '🏗️',
    category: 'generate',
  },
  {
    id: 'v4_predict',
    label: 'ML予測',
    description: 'MLモデルで予測を再生成（predictions更新）',
    icon: '🤖',
    category: 'generate',
  },
  {
    id: 'v4_pipeline',
    label: '再処理パイプライン',
    description: 'レースJSON構築→調教補強→ML予測（スクレイプなし・データ再処理用）',
    icon: '♻️',
    category: 'batch',
  },
  {
    id: 'vb_refresh',
    label: 'VB/買い目抽出',
    description: '最新オッズでValueBet判定・買い目を再生成',
    icon: '💰',
    category: 'generate',
  },
];

/**
 * 日付をYYYY/MM/DD形式に変換
 */
export function formatDateForCli(date: string): string {
  // YYYY-MM-DD → YYYY/MM/DD
  return date.replace(/-/g, '/');
}

/**
 * レースフィルタ引数を追加
 */
function appendRaceFilters(args: string[], options?: CommandOptions): string[] {
  if (!options) return args;

  if (options.raceFrom) {
    args.push('--from-race', String(options.raceFrom));
  }
  if (options.raceTo) {
    args.push('--to-race', String(options.raceTo));
  }
  if (options.track) {
    args.push('--track', options.track);
  }

  return args;
}

/**
 * アクションIDからコマンド引数を生成（全てv2ネイティブ）
 */
export function getCommandArgs(action: ActionType, date: string, options?: CommandOptions): string[][] {
  switch (action) {
    case 'schedule':
      return [
        ['-m', 'keibabook.batch_scraper', '--date', date, '--types', 'nittei'],
      ];

    case 'basic':
      return [
        ['-m', 'keibabook.batch_scraper', '--date', date, '--types', 'basic'],
      ];

    case 'paddok':
      return [
        appendRaceFilters(
          ['-m', 'keibabook.batch_scraper', '--date', date, '--types', 'paddok'],
          options
        ),
      ];

    case 'seiseki':
      return [
        appendRaceFilters(
          ['-m', 'keibabook.batch_scraper', '--date', date, '--types', 'seiseki'],
          options
        ),
      ];

    case 'babakeikou':
      return [
        ['-m', 'keibabook.batch_scraper', '--date', date, '--types', 'babakeikou'],
      ];

    case 'batch_prepare':
    case 'batch_morning':
    case 'batch_after_race':
    case 'sunpyo_update':
      // Note: execute/route.ts で特別に処理される
      return [];

    case 'calc_race_type_standards':
    case 'calc_rating_standards':
    case 'build_horse_name_index':
    case 'build_trainer_index':
    case 'analyze_trainer_patterns':
    case 'analyze_training':
    case 'rebuild_sire_stats':
    case 'rebuild_slow_start':
    case 'v4_build_race':
    case 'v4_predict':
    case 'v4_pipeline':
    case 'vb_refresh':
      // Note: execute/route.ts で特別に処理される
      return [];

    default:
      return [];
  }
}

/**
 * 日付範囲対応アクションのコマンド引数を生成（全てv2ネイティブ）
 */
export function getCommandArgsRange(
  action: ActionType,
  startDate: string,
  endDate: string,
  options?: CommandOptions
): string[][] {
  switch (action) {
    case 'schedule':
      return [
        ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'nittei'],
      ];

    case 'basic':
      return [
        ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'basic'],
      ];

    case 'paddok':
      return [
        appendRaceFilters(
          ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'paddok'],
          options
        ),
      ];

    case 'seiseki':
      return [
        appendRaceFilters(
          ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'seiseki'],
          options
        ),
      ];

    case 'babakeikou':
      return [
        ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'babakeikou'],
      ];

    case 'batch_prepare':
    case 'batch_morning':
    case 'batch_after_race':
    case 'sunpyo_update':
      // Note: execute/route.ts で特別に処理される
      return [];

    case 'build_horse_name_index':
    case 'build_trainer_index':
    case 'analyze_trainer_patterns':
    case 'analyze_training':
    case 'rebuild_sire_stats':
    case 'rebuild_slow_start':
    case 'v4_build_race':
    case 'v4_predict':
    case 'v4_pipeline':
    case 'vb_refresh':
      // Note: execute/route.ts で特別に処理される
      return [];

    default:
      return [];
  }
}

/**
 * アクションの取得
 */
export function getAction(id: ActionType): ActionConfig | undefined {
  return ACTIONS.find((a) => a.id === id);
}

/**
 * カテゴリ別にアクションを取得
 */
export function getActionsByCategory(category: ActionConfig['category']): ActionConfig[] {
  return ACTIONS.filter((a) => a.category === category);
}
