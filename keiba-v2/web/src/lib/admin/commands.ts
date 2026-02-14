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
  | 'batch_after_race'
  | 'sunpyo_update'
  | 'calc_race_type_standards'   // レース特性基準値算出
  | 'calc_rating_standards'      // レイティング基準値算出
  | 'build_horse_name_index'     // 馬名インデックス作成
  | 'build_trainer_index'        // 調教師インデックス作成
  | 'analyze_trainer_patterns'   // 調教師パターン分析
  | 'analyze_training'           // 調教分析
  | 'v4_build_race'              // v4 JRA-VAN → data3/races/
  | 'v4_predict'                 // v4 ML v3予測 → data3/ml/predictions_live.json
  | 'v4_pipeline';               // v4 上記を連結実行

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
  // データ取得（v2 batch_scraper経由）
  {
    id: 'schedule',
    label: 'スケジュール取得',
    description: 'keibabook.co.jpから開催日程を取得',
    icon: '📅',
    category: 'fetch',
  },
  {
    id: 'basic',
    label: '基本データ取得',
    description: '出馬表・調教・談話・勝因を取得 → kb_ext直接構築',
    icon: '📋',
    category: 'fetch',
  },
  {
    id: 'paddok',
    label: 'パドック取得',
    description: 'パドック情報を取得 → kb_ext更新（レース当日用）',
    icon: '🐎',
    category: 'fetch',
  },
  {
    id: 'seiseki',
    label: '成績取得',
    description: 'レース結果を取得 → kb_ext更新（レース後用）',
    icon: '🏆',
    category: 'fetch',
  },
  {
    id: 'babakeikou',
    label: '馬場情報取得',
    description: '当日の馬場情報を取得',
    icon: '🌱',
    category: 'fetch',
  },
  // 一括実行
  {
    id: 'batch_prepare',
    label: '基本情報構築',
    description: '日程取得 → 基本データ取得 → kb_ext構築 → v4パイプライン（レース構築・調教補強・ML予測）',
    icon: '🌅',
    category: 'batch',
  },
  {
    id: 'batch_after_race',
    label: '直前情報・結果情報構築',
    description: 'パドック → 成績 → kb_ext更新 → v4パイプライン（調教補強・ML予測）',
    icon: '🔄',
    category: 'batch',
  },
  // 過去データ更新（日付範囲対応）
  {
    id: 'sunpyo_update',
    label: '寸評更新',
    description: '過去レースの成績を再取得（寸評含む）→ kb_ext更新',
    icon: '📝',
    category: 'update',
    requiresDateRange: true,
  },
  // データ分析
  {
    id: 'calc_race_type_standards',
    label: 'レース特性基準値算出',
    description: 'data3/racesからRPCI瞬発戦/持続戦の基準値を算出',
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
  {
    id: 'build_horse_name_index',
    label: '馬名インデックス作成',
    description: 'data3/masters/horsesから馬名→血統番号の辞書を再構築（新馬対応・年1回推奨）',
    icon: '📖',
    category: 'generate',
    noDateRequired: true,
  },
  {
    id: 'build_trainer_index',
    label: '調教師インデックス作成',
    description: 'data3/mastersから調教師コード↔名前の対応辞書を構築',
    icon: '👨‍🏫',
    category: 'generate',
    noDateRequired: true,
  },
  {
    id: 'analyze_trainer_patterns',
    label: '調教師パターン分析(旧)',
    description: 'keibabook調教詳細×着順データから調教師別好走パターンを統計分析',
    icon: '🔬',
    category: 'analysis',
    noDateRequired: true,
  },
  {
    id: 'analyze_training',
    label: '調教分析',
    description: 'CK_DATA調教×レース成績の統合分析（全体+調教師別パターン）',
    icon: '🏋️',
    category: 'analysis',
    noDateRequired: true,
  },
  // v4パイプライン（JRA-VAN基盤）
  {
    id: 'v4_build_race',
    label: 'v4 レース構築',
    description: 'JRA-VAN SE/SR → data3/races/ レースJSON生成',
    icon: '🏗️',
    category: 'generate',
  },
  {
    id: 'v4_predict',
    label: 'v4 ML予測',
    description: 'ML v3モデルで当日レースのValue Bet予測',
    icon: '🤖',
    category: 'generate',
  },
  {
    id: 'v4_pipeline',
    label: 'v4 パイプライン',
    description: 'レース構築 → 調教詳細補強 → ML予測 を一括実行',
    icon: '🚀',
    category: 'batch',
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
    case 'v4_build_race':
    case 'v4_predict':
    case 'v4_pipeline':
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
    case 'batch_after_race':
    case 'sunpyo_update':
      // Note: execute/route.ts で特別に処理される
      return [];

    case 'build_horse_name_index':
    case 'build_trainer_index':
    case 'analyze_trainer_patterns':
    case 'analyze_training':
    case 'v4_build_race':
    case 'v4_predict':
    case 'v4_pipeline':
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
