/**
 * 管理画面用コマンド定義
 */

export type ActionType =
  | 'schedule'
  | 'basic'
  | 'paddok'
  | 'seiseki'
  | 'babakeikou'
  | 'integrate'
  | 'markdown'
  | 'horse_profile'
  | 'batch_prepare'
  | 'batch_after_race'
  | 'sunpyo_update'
  | 'calc_race_type_standards'   // レース特性基準値算出
  | 'calc_rating_standards'      // レイティング基準値算出
  | 'training_summary'           // 調教サマリ生成
  | 'build_horse_name_index'     // 馬名インデックス作成
  | 'build_trainer_index'        // 調教師インデックス作成
  | 'analyze_trainer_patterns'   // 調教師パターン分析
  | 'v4_build_race'              // v4 JRA-VAN → data3/races/
  | 'v4_build_kbext'             // v4 data2 integrated → data3/keibabook/
  | 'v4_predict'                 // v4 ML v3予測 → data3/ml/predictions_live.json
  | 'v4_pipeline';               // v4 上記3つを連結実行

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

const RACE_INFO_UPDATE_SCRIPT = '../KeibaCICD.TARGET/scripts/parse_jv_race_data.py';

function buildRaceInfoUpdateArgs(date: string): string[] {
  return [
    RACE_INFO_UPDATE_SCRIPT,
    '--date',
    date,
    '--update-race-info',
  ];
}

function getDateRangeList(startDate: string, endDate: string): string[] {
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);

  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return [];
  }

  const dates: string[] = [];
  const current = new Date(start);

  while (current <= end) {
    const year = current.getFullYear();
    const month = String(current.getMonth() + 1).padStart(2, '0');
    const day = String(current.getDate()).padStart(2, '0');
    dates.push(`${year}-${month}-${day}`);
    current.setDate(current.getDate() + 1);
  }

  return dates;
}

export const ACTIONS: ActionConfig[] = [
  // データ取得
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
    description: '出馬表・調教・談話・勝因を取得',
    icon: '📋',
    category: 'fetch',
  },
  {
    id: 'paddok',
    label: 'パドック取得',
    description: 'パドック情報を取得（レース当日用）',
    icon: '🐎',
    category: 'fetch',
  },
  {
    id: 'seiseki',
    label: '成績取得',
    description: 'レース結果を取得（レース後用）',
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
  // データ統合・生成
  {
    id: 'integrate',
    label: 'データ統合',
    description: 'JSONデータを統合',
    icon: '🔗',
    category: 'generate',
  },
  {
    id: 'markdown',
    label: 'MD生成',
    description: 'Markdownファイルを生成',
    icon: '📄',
    category: 'generate',
  },
  {
    id: 'horse_profile',
    label: '馬プロフィール生成',
    description: '馬の詳細プロフィールを生成',
    icon: '🐴',
    category: 'generate',
  },
  // 一括実行
  {
    id: 'batch_prepare',
    label: '前日準備',
    description: 'スケジュール → 基本データ → 統合',
    icon: '🌅',
    category: 'batch',
  },
  {
    id: 'batch_after_race',
    label: 'レース後更新',
    description: 'パドック → 成績 → 統合',
    icon: '🔄',
    category: 'batch',
  },
  // 過去データ更新（日付範囲対応）
  {
    id: 'sunpyo_update',
    label: '寸評更新',
    description: '過去レースの成績を再取得（寸評含む）',
    icon: '📝',
    category: 'update',
    requiresDateRange: true,
  },
  // データ分析
  {
    id: 'calc_race_type_standards',
    label: 'レース特性基準値算出',
    description: 'JRA-VANデータから瞬発戦/持続戦の基準値を算出',
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
    id: 'training_summary',
    label: '調教サマリ生成',
    description: 'CK_DATAから調教サマリJSONを生成',
    icon: '🏋️',
    category: 'generate',
  },
  {
    id: 'build_horse_name_index',
    label: '馬名インデックス作成',
    description: 'UM_DATAから馬名→血統番号の辞書を再構築（新馬対応・年1回推奨）',
    icon: '📖',
    category: 'generate',
    noDateRequired: true,
  },
  {
    id: 'build_trainer_index',
    label: '調教師インデックス作成',
    description: '競馬ブック厩舎IDとJRA-VAN調教師コードの対応辞書を構築',
    icon: '👨‍🏫',
    category: 'generate',
    noDateRequired: true,
  },
  {
    id: 'analyze_trainer_patterns',
    label: '調教師パターン分析',
    description: '過去3年の調教×着順データから調教師別好走パターンを統計分析',
    icon: '🔬',
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
    id: 'v4_build_kbext',
    label: 'v4 KB拡張変換',
    description: 'data2 integrated → data3/keibabook/ 拡張データ変換',
    icon: '📦',
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
    description: 'レース構築 → KB拡張変換 → ML予測 を一括実行',
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
 * アクションIDからコマンド引数を生成
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

export function getCommandArgs(action: ActionType, date: string, options?: CommandOptions): string[][] {
  const formattedDate = formatDateForCli(date);
  const raceInfoUpdateArgs = buildRaceInfoUpdateArgs(date);

  switch (action) {
    case 'schedule':
      return [
        ['-m', 'src.fast_batch_cli', 'schedule', '--start', formattedDate, '--end', formattedDate],
        raceInfoUpdateArgs,
      ];

    case 'basic':
      return [
        [
          '-m',
          'src.fast_batch_cli',
          'full',
          '--start',
          formattedDate,
          '--end',
          formattedDate,
          '--data-types',
          'shutsuba,cyokyo,danwa,syoin',
        ],
      ];

    case 'paddok':
      return [
        appendRaceFilters(
          [
            '-m',
            'src.fast_batch_cli',
            'full',
            '--start',
            formattedDate,
            '--end',
            formattedDate,
            '--data-types',
            'paddok',
          ],
          options
        ),
      ];

    case 'seiseki':
      return [
        appendRaceFilters(
          [
            '-m',
            'src.fast_batch_cli',
            'full',
            '--start',
            formattedDate,
            '--end',
            formattedDate,
            '--data-types',
            'seiseki',
          ],
          options
        ),
      ];

    case 'babakeikou':
      // 馬場情報取得（単一日付）
      return [
        [
          '-m',
          'src.fast_batch_cli',
          'full',
          '--start',
          formattedDate,
          '--end',
          formattedDate,
          '--data-types',
          'babakeikou',
        ],
      ];

    case 'integrate':
      return [['-m', 'src.integrator_cli', 'batch', '--date', formattedDate]];

    case 'markdown':
      return [['-m', 'src.markdown_cli', 'batch', '--date', formattedDate, '--organized']];

    case 'horse_profile':
      return [
        [
          '-m',
          'src.horse_profile_cli',
          '--date',
          formattedDate,
          '--all',
          '--with-history',
          '--with-seiseki-table',
        ],
      ];

    case 'batch_prepare':
      // 前日準備: スケジュール → 基本データ → 統合
      // ※MD生成・馬プロフィールは除外（WebViewer v2では不要）
      return [
        ...getCommandArgs('schedule', date, options),
        ...getCommandArgs('basic', date, options),
        ...getCommandArgs('integrate', date, options),
      ];

    case 'batch_after_race':
      // レース後更新: パドック → 成績 → 統合
      // ※MD生成は除外（WebViewer不要、Obsidian用）
      return [
        ...getCommandArgs('paddok', date, options),
        ...getCommandArgs('seiseki', date, options),
        ...getCommandArgs('integrate', date, options),
      ];

    case 'sunpyo_update':
      // 寸評更新は日付範囲対応版を使用
      return [];

    case 'calc_race_type_standards':
      // レース特性基準値算出（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'calc_rating_standards':
      // レイティング基準値算出（keibabookスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'training_summary':
      // 調教サマリ生成（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'build_horse_name_index':
      // 馬名インデックス作成（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'build_trainer_index':
      // 調教師インデックス作成（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'analyze_trainer_patterns':
      // 調教師パターン分析（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'v4_build_race':
    case 'v4_build_kbext':
    case 'v4_predict':
    case 'v4_pipeline':
      // v4パイプライン: APIルートで特別に処理される
      return [];

    default:
      return [];
  }
}

/**
 * 日付範囲対応アクションのコマンド引数を生成
 * すべてのアクションで日付範囲指定が可能
 */
export function getCommandArgsRange(
  action: ActionType,
  startDate: string,
  endDate: string,
  options?: CommandOptions
): string[][] {
  const formattedStart = formatDateForCli(startDate);
  const formattedEnd = formatDateForCli(endDate);
  const rangeDates = getDateRangeList(startDate, endDate);

  switch (action) {
    case 'schedule':
      return [
        ['-m', 'src.fast_batch_cli', 'schedule', '--start', formattedStart, '--end', formattedEnd],
        ...rangeDates.map((date) => buildRaceInfoUpdateArgs(date)),
      ];

    case 'basic':
      return [
        [
          '-m',
          'src.fast_batch_cli',
          'full',
          '--start',
          formattedStart,
          '--end',
          formattedEnd,
          '--data-types',
          'shutsuba,cyokyo,danwa,syoin',
        ],
      ];

    case 'paddok':
      return [
        appendRaceFilters(
          [
            '-m',
            'src.fast_batch_cli',
            'full',
            '--start',
            formattedStart,
            '--end',
            formattedEnd,
            '--data-types',
            'paddok',
          ],
          options
        ),
      ];

    case 'seiseki':
      return [
        appendRaceFilters(
          [
            '-m',
            'src.fast_batch_cli',
            'full',
            '--start',
            formattedStart,
            '--end',
            formattedEnd,
            '--data-types',
            'seiseki',
          ],
          options
        ),
      ];

    case 'babakeikou':
      return [
        [
          '-m',
          'src.fast_batch_cli',
          'full',
          '--start',
          formattedStart,
          '--end',
          formattedEnd,
          '--data-types',
          'babakeikou',
        ],
      ];

    case 'integrate':
      return [['-m', 'src.integrator_cli', 'batch', '--start', formattedStart, '--end', formattedEnd]];

    case 'markdown':
      return [['-m', 'src.markdown_cli', 'batch', '--start', formattedStart, '--end', formattedEnd, '--organized']];

    case 'horse_profile':
      // 馬プロフィールは範囲全体を処理
      return [
        [
          '-m',
          'src.horse_profile_cli',
          '--start',
          formattedStart,
          '--end',
          formattedEnd,
          '--all',
          '--with-history',
          '--with-seiseki-table',
        ],
      ];

    case 'batch_prepare':
      // 前日準備: スケジュール → 基本データ → 統合
      // ※MD生成・馬プロフィールは除外（WebViewer v2では不要）
      return [
        ...getCommandArgsRange('schedule', startDate, endDate, options),
        ...getCommandArgsRange('basic', startDate, endDate, options),
        ...getCommandArgsRange('integrate', startDate, endDate, options),
      ];

    case 'batch_after_race':
      // レース後更新: パドック → 成績 → 統合
      // ※MD生成は除外（WebViewer不要、Obsidian用）
      return [
        ...getCommandArgsRange('paddok', startDate, endDate, options),
        ...getCommandArgsRange('seiseki', startDate, endDate, options),
        ...getCommandArgsRange('integrate', startDate, endDate, options),
      ];

    case 'sunpyo_update':
      // 過去レースの成績を再取得（寸評含む）→ 統合 → MD生成
      return [
        [
          '-m',
          'src.fast_batch_cli',
          'full',
          '--start',
          formattedStart,
          '--end',
          formattedEnd,
          '--data-types',
          'seiseki',
        ],
        ['-m', 'src.integrator_cli', 'batch', '--start', formattedStart, '--end', formattedEnd],
        ['-m', 'src.markdown_cli', 'batch', '--start', formattedStart, '--end', formattedEnd, '--organized'],
      ];

    case 'training_summary':
      // 調教サマリ生成（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'build_horse_name_index':
      // 馬名インデックス作成（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'build_trainer_index':
      // 調教師インデックス作成（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'analyze_trainer_patterns':
      // 調教師パターン分析（TARGETスクリプト）
      // Note: このアクションはAPIルートで特別に処理される
      return [];

    case 'v4_build_race':
    case 'v4_build_kbext':
    case 'v4_predict':
    case 'v4_pipeline':
      // v4パイプライン: APIルートで特別に処理される
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
