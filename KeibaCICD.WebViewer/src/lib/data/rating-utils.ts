/**
 * レイティング分析ユーティリティ
 * クライアント/サーバー両方で使用可能
 */

// 統計ヘルパー関数
function mean(arr: number[]): number {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function standardDeviation(arr: number[]): number {
  if (arr.length < 2) return 0;
  const avg = mean(arr);
  const squareDiffs = arr.map(value => Math.pow(value - avg, 2));
  return Math.sqrt(mean(squareDiffs));
}

function median(arr: number[]): number {
  if (arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// 型定義
export interface RatingStats {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
}

export interface CompetitivenessInfo {
  mean_race_stdev: number;
  mean_top3_diff: number;
  description: string;
}

export interface GradeStandard {
  sample_count: number;
  horse_count: number;
  rating: RatingStats;
  competitiveness: CompetitivenessInfo;
  thresholds: {
    high_level: number;
    low_level: number;
  };
}

export interface RatingStandards {
  by_grade: Record<string, GradeStandard>;
  competitiveness_thresholds?: {
    stdev: {
      mean: number;
      thresholds: {
        very_competitive: number;
        competitive: number;
        normal: number;
        clear_difference: number;
      };
    };
  };
}

export interface RaceRatingAnalysis {
  // 基本統計
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
  count: number;
  
  // レベル判定
  levelLabel: string;
  levelDescription: string;
  levelDiff: number; // 基準値からの差
  
  // 混戦度
  competitivenessLabel: string;
  competitivenessDescription: string;
  top3Diff: number; // 上位3頭と4位の差
  
  // 基準データ
  gradeStandard?: GradeStandard;
}

/**
 * レイティング値をパース
 */
export function parseRating(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  
  const s = String(value).trim();
  if (!s || s === '-' || s === '---') return null;
  
  // 全角→半角
  const normalized = s.replace(/[０-９]/g, (c) => 
    String.fromCharCode(c.charCodeAt(0) - 0xfee0)
  );
  
  const num = parseFloat(normalized);
  if (isNaN(num)) return null;
  
  // 妥当な範囲チェック
  if (num < 30 || num > 150) return null;
  
  return num;
}

// 重賞レース名キーワード
const G1_KEYWORDS = [
  'フェブラリーステークス', 'FEBRUARY STAKES',
  '高松宮記念', 'TAKAMATSUNOMIYA KINEN',
  '大阪杯', 'OSAKA HAI',
  '桜花賞', 'OKA SHO',
  '皐月賞', 'SATSUKI SHO',
  '天皇賞', 'TENNO SHO', 'TENNOSHO',
  'NHKマイルカップ', 'NHK MILE CUP',
  'ヴィクトリアマイル', 'VICTORIA MILE',
  'オークス', '優駿牝馬', 'YUSHUN HIMBA',
  '日本ダービー', '東京優駿', 'TOKYO YUSHUN',
  '安田記念', 'YASUDA KINEN',
  '宝塚記念', 'TAKARAZUKA KINEN',
  'スプリンターズステークス', 'SPRINTERS STAKES',
  '秋華賞', 'SHUKA SHO',
  '菊花賞', 'KIKUKA SHO',
  'エリザベス女王杯', 'QUEEN ELIZABETH',
  'マイルチャンピオンシップ', 'MILE CHAMPIONSHIP',
  'ジャパンカップ', 'JAPAN CUP',
  'チャンピオンズカップ', 'CHAMPIONS CUP',
  '阪神ジュベナイルフィリーズ', 'HANSHIN JUVENILE FILLIES',
  '朝日杯フューチュリティ', 'ASAHI HAI FUTURITY',
  '有馬記念', 'ARIMA KINEN',
  'ホープフルステークス', 'HOPEFUL STAKES',
];

const G2_KEYWORDS = [
  '日経新春杯', 'NIKKEI SHINSHUN', 'NIKKEISHINSHUN',
  'アメリカジョッキークラブカップ', 'AMERICAN JOCKEY CLUB', 'AJCC',
  '京都記念', 'KYOTO KINEN',
  '共同通信杯', 'KYODOSHINBUN HAI', 'KYODO NEWS',
  '京王杯スプリングカップ', 'KEIO HAI SPRING',
  'フローラステークス', 'FLORA STAKES',
  '青葉賞', 'AOBA SHO',
  '阪神牝馬ステークス', 'HANSHIN HIMBA',
  '目黒記念', 'MEGURO KINEN',
  '札幌記念', 'SAPPORO KINEN',
  '新潟記念', 'NIIGATA KINEN',
  'オールカマー', 'ALL COMERS',
  '神戸新聞杯', 'KOBE SHIMBUN',
  'セントウルステークス', 'CENTAUR STAKES',
  '府中牝馬ステークス', 'FUCHU HIMBA',
  'ローズステークス', 'ROSE STAKES',
  '毎日王冠', 'MAINICHI OKAN',
  '富士ステークス', 'FUJI STAKES',
  '京都大賞典', 'KYOTO DAISHOTEN',
  'スワンステークス', 'SWAN STAKES',
  'アルゼンチン共和国杯', 'ARGENTINA',
  '京阪杯', 'KEIHAN HAI',
  '阪神カップ', 'HANSHIN CUP',
  '日経賞', 'NIKKEI SHO',
  '金鯱賞', 'KINKO SHO',
  '弥生賞', 'YAYOI SHO',
  'チューリップ賞', 'TULIP SHO',
  'スプリングステークス', 'SPRING STAKES',
  'フィリーズレビュー', 'FILLIES',
  'マーメイドステークス', 'MERMAID',
  'ステイヤーズステークス', 'STAYERS',
  '中日新聞杯', 'CHUNICHI SHIMBUN',
  '中山記念', 'NAKAYAMA KINEN',
  '小倉大賞典', 'KOKURA DAISHOTEN',
  '東京新聞杯', 'TOKYO SHIMBUN',
  '阪急杯', 'HANKYU HAI',
  '平安ステークス', 'HEIAN STAKES',
  '紫苑ステークス', 'SHION STAKES',
  'サウジアラビアロイヤルカップ', 'SAUDI ARABIA',
  '京成杯', 'KEISEI HAI',
];

const G3_KEYWORDS = [
  '中山金杯', 'NAKAYAMA KIMPAI', 'NAKAYAMA KINPAI',
  '京都金杯', 'KYOTO KIMPAI', 'KYOTO KINPAI',
  'シンザン記念', 'SHINZAN KINEN',
  'フェアリーステークス', 'FAIRY STAKES',
  '愛知杯', 'AICHI HAI',
  '東海ステークス', 'TOKAI STAKES',
  'シルクロードステークス', 'SILK ROAD',
  '根岸ステークス', 'NEGISHI STAKES',
  'きさらぎ賞', 'KISARAGI SHO',
  'クイーンカップ', 'QUEEN CUP',
  'ダイヤモンドステークス', 'DIAMOND STAKES',
  'アーリントンカップ', 'ARLINGTON CUP',
  'オーシャンステークス', 'OCEAN STAKES',
  '中京記念', 'CHUKYO KINEN',
  '福島牝馬ステークス', 'FUKUSHIMA HIMBA',
  'アンタレスステークス', 'ANTARES STAKES',
  '新潟大賞典', 'NIIGATA DAISHOTEN',
  'CBC賞', 'CBC SHO',
  'エプソムカップ', 'EPSOM CUP',
  '函館スプリントステークス', 'HAKODATE SPRINT',
  'ユニコーンステークス', 'UNICORN STAKES',
  'ラジオNIKKEI賞', 'RADIO NIKKEI',
  'プロキオンステークス', 'PROCYON STAKES',
  '七夕賞', 'TANABATA SHO',
  '函館2歳ステークス', 'HAKODATE NISAI',
  '函館記念', 'HAKODATE KINEN',
  'アイビスサマーダッシュ', 'IBIS SUMMER',
  '小倉記念', 'KOKURA KINEN',
  '関屋記念', 'SEKIYA KINEN',
  'エルムステークス', 'ELM STAKES',
  '北九州記念', 'KITAKYUSHU KINEN',
  '札幌2歳ステークス', 'SAPPORO NISAI',
  'キーンランドカップ', 'KEENELAND CUP',
  '新潟2歳ステークス', 'NIIGATA NISAI',
  'レパードステークス', 'LEOPARD STAKES',
  '小倉2歳ステークス', 'KOKURA NISAI',
  'シリウスステークス', 'SIRIUS STAKES',
  '京成杯オータムハンデ', 'KEISEI HAI AUTUMN',
  'ファンタジーステークス', 'FANTASY STAKES',
  'デイリー杯', 'DAILY HAI',
  '京都2歳ステークス', 'KYOTO NISAI',
  '武蔵野ステークス', 'MUSASHINO STAKES',
  '東京スポーツ杯', 'TOKYO SPORTS',
  'カペラステークス', 'CAPELLA STAKES',
  'ターコイズステークス', 'TURQUOISE STAKES',
  'みやこステークス', 'MIYAKO STAKES',
  '福島記念', 'FUKUSHIMA KINEN',
];

/**
 * レース名から重賞グレードを判定
 */
function matchGradeByRaceName(raceCondition: string): string {
  const text = raceCondition.toUpperCase();
  
  for (const keyword of G1_KEYWORDS) {
    if (text.includes(keyword.toUpperCase())) return 'G1';
  }
  for (const keyword of G2_KEYWORDS) {
    if (text.includes(keyword.toUpperCase())) return 'G2';
  }
  for (const keyword of G3_KEYWORDS) {
    if (text.includes(keyword.toUpperCase())) return 'G3';
  }
  
  return '';
}

/**
 * race_conditionからグレードを抽出
 */
function extractGradeFromCondition(raceCondition: string | undefined | null): string {
  if (!raceCondition) return '';
  
  const cond = raceCondition.trim();
  
  // まず重賞レース名でマッチング
  const gradeByName = matchGradeByRaceName(cond);
  if (gradeByName) return gradeByName;
  
  // G1/G2/G3の明示的な表記
  if (cond.includes('GI') || cond.includes('G1') || cond.includes('Ｇ１')) return 'G1';
  if (cond.includes('GII') || cond.includes('G2') || cond.includes('Ｇ２')) return 'G2';
  if (cond.includes('GIII') || cond.includes('G3') || cond.includes('Ｇ３')) return 'G3';
  
  // クラス条件
  if (cond.includes('未勝利')) return '未勝利';
  if (cond.includes('新馬')) return '新馬';
  if (cond.includes('1勝クラス') || cond.includes('１勝クラス') || cond.includes('500万')) return '1勝クラス';
  if (cond.includes('2勝クラス') || cond.includes('２勝クラス') || cond.includes('1000万')) return '2勝クラス';
  if (cond.includes('3勝クラス') || cond.includes('３勝クラス') || cond.includes('1600万')) return '3勝クラス';
  if (cond.includes('オープン') || cond.includes('OP')) return 'OP';
  if (cond.includes('リステッド')) return 'OP';
  
  return '';
}

/**
 * グレード名を正規化（race_conditionも参照）
 */
export function normalizeGrade(grade: string | undefined | null, raceCondition?: string | null): string {
  // まずrace_conditionから抽出を試みる
  const extracted = extractGradeFromCondition(raceCondition);
  if (extracted) return extracted;
  
  if (!grade) return '未分類';
  
  const g = grade.trim();
  
  if (g === 'G1' || g === 'GI') return 'G1';
  if (g === 'G2' || g === 'GII') return 'G2';
  if (g === 'G3' || g === 'GIII') return 'G3';
  if (g === 'OP' || g === 'オープン' || g === 'L' || g === 'リステッド') return 'OP';
  if (g.includes('3勝') || g === '1600万') return '3勝クラス';
  if (g.includes('2勝') || g === '1000万') return '2勝クラス';
  if (g.includes('1勝') || g === '500万') return '1勝クラス';
  if (g.includes('新馬')) return '新馬';
  if (g.includes('未勝利')) return '未勝利';
  
  return g;
}

/**
 * レースのレイティング分析を実行
 */
export function analyzeRaceRatings(
  entries: Array<{ rating?: string | number | null; entry_data?: { rating?: string | number | null } }>,
  grade: string | undefined | null,
  standards?: RatingStandards | null,
  raceCondition?: string | null
): RaceRatingAnalysis | null {
  // レイティング値を収集
  const ratings: number[] = [];
  for (const entry of entries) {
    // entry_dataの中にratingがある場合と、直接ratingがある場合に対応
    const ratingValue = entry.entry_data?.rating ?? entry.rating;
    const r = parseRating(ratingValue);
    if (r !== null) {
      ratings.push(r);
    }
  }
  
  if (ratings.length < 3) {
    return null;
  }
  
  // 基本統計
  const meanVal = mean(ratings);
  const stdevVal = ratings.length > 1 ? standardDeviation(ratings) : 0;
  const medianVal = median(ratings);
  const minVal = Math.min(...ratings);
  const maxVal = Math.max(...ratings);
  
  // 上位3頭と4位の差
  const sorted = [...ratings].sort((a, b) => b - a);
  const top3Diff = sorted.length >= 4 ? sorted[0] - sorted[3] : 0;
  
  // グレード基準値を取得
  const normalizedGrade = normalizeGrade(grade, raceCondition);
  const gradeStandard = standards?.by_grade?.[normalizedGrade];
  
  // レベル判定
  let levelLabel = '標準';
  let levelDescription = 'クラス平均的なレベル';
  let levelDiff = 0;
  
  if (gradeStandard) {
    const baseMean = gradeStandard.rating.mean;
    levelDiff = meanVal - baseMean;
    
    if (meanVal >= gradeStandard.thresholds.high_level) {
      levelLabel = '高レベル';
      levelDescription = `クラス基準+${levelDiff.toFixed(1)}pt`;
    } else if (meanVal <= gradeStandard.thresholds.low_level) {
      levelLabel = '低レベル';
      levelDescription = `クラス基準${levelDiff.toFixed(1)}pt`;
    } else {
      levelLabel = '標準';
      levelDescription = `クラス基準比 ${levelDiff >= 0 ? '+' : ''}${levelDiff.toFixed(1)}pt`;
    }
  }
  
  // 混戦度判定
  let competitivenessLabel = '標準的';
  let competitivenessDescription = '';
  
  const compThresholds = standards?.competitiveness_thresholds?.stdev?.thresholds;
  if (compThresholds) {
    if (stdevVal < compThresholds.very_competitive) {
      competitivenessLabel = '非常に混戦';
      competitivenessDescription = '実力拮抗、荒れる可能性';
    } else if (stdevVal < compThresholds.competitive) {
      competitivenessLabel = 'やや混戦';
      competitivenessDescription = '上位争いが激しい';
    } else if (stdevVal > compThresholds.clear_difference) {
      competitivenessLabel = '力差明確';
      competitivenessDescription = '上位馬が信頼できる';
    } else {
      competitivenessLabel = '標準的';
      competitivenessDescription = '通常の競争レベル';
    }
  } else {
    // デフォルト閾値
    if (stdevVal < 4) {
      competitivenessLabel = '非常に混戦';
      competitivenessDescription = '実力拮抗';
    } else if (stdevVal < 6) {
      competitivenessLabel = 'やや混戦';
      competitivenessDescription = '上位争い激しい';
    } else if (stdevVal > 8) {
      competitivenessLabel = '力差明確';
      competitivenessDescription = '上位有利';
    } else {
      competitivenessLabel = '標準的';
      competitivenessDescription = '';
    }
  }
  
  return {
    mean: Math.round(meanVal * 10) / 10,
    stdev: Math.round(stdevVal * 10) / 10,
    median: Math.round(medianVal * 10) / 10,
    min: Math.round(minVal * 10) / 10,
    max: Math.round(maxVal * 10) / 10,
    count: ratings.length,
    levelLabel,
    levelDescription,
    levelDiff: Math.round(levelDiff * 10) / 10,
    competitivenessLabel,
    competitivenessDescription,
    top3Diff: Math.round(top3Diff * 10) / 10,
    gradeStandard,
  };
}
