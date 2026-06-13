/**
 * RT_DATA オッズの型定義とユーティリティ（クライアント互換）
 *
 * fs/path を使わない純粋な関数のみ。rt-data-reader の fs 依存を
 * クライアントコンポーネントから分離するため。
 */

const TRACK_CODES: Record<string, string> = {
  '01': '札幌',
  '02': '函館',
  '03': '福島',
  '04': '新潟',
  '05': '東京',
  '06': '中山',
  '07': '中京',
  '08': '京都',
  '09': '阪神',
  '10': '小倉',
};

export interface HorseOdds {
  umaban: string;
  winOdds: number | null;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
  ninki: number | null;
  /** 馬名（races データから取得できる場合） */
  horseName?: string;
  /** 枠番（races データから取得できる場合） */
  waku?: string;
  /** 本紙印（◎○▲△×など） */
  honshiMark?: string;
  /** 騎手名 */
  jockey?: string;
  /** AI指数 */
  aiIndex?: number;
  /** レイティング */
  rating?: number;
  /** 前走着順 */
  lastResult?: string;
  /** 時系列変動トレンド */
  oddsTrend?: 'up' | 'down' | 'stable' | 'unknown';
  /** オッズ変動量（現在 - 朝一） */
  oddsChange?: number | null;
  /** オッズ変動率（%） */
  oddsChangePercent?: number | null;
  /** 朝一オッズ */
  firstOdds?: number | null;
  /** 確定着順（結果が出ている場合） */
  finishPosition?: string | null;
  /** 確定タイム */
  finishTime?: string | null;
  /** 確定単勝オッズ */
  finalOdds?: number | null;
  /** 確定単勝人気 */
  finalNinki?: number | null;
}

/** レース条件情報 */
export interface RaceCondition {
  raceCondition?: string;  // "3歳未勝利 牝" など
  track?: string;          // "芝" | "ダ" | "ダート"
  distance?: number;
}

/** オッズ分析コメント */
export interface OddsAnalysis {
  pattern: 'ikkyou' | 'sankyou' | 'jyouikikkoh' | 'daikon' | 'normal';
  label: string;
  description: string;
}

export interface RaceOdds {
  raceId: string;
  source: 'RT_DATA';
  horses: HorseOdds[];
  /** レース詳細ページ用（races-v2 の URL id に使用） */
  keibabookRaceId?: string;
  /** レース条件 */
  raceCondition?: RaceCondition;
  /** オッズ分析コメント */
  analysis?: OddsAnalysis;
  /** O1レコードの発表時刻 (MMDDHHmm) — 表示中オッズの as-of */
  happyoTime?: string;
  /** 表示中オッズの鮮度（as-of）。/api/odds/race が付与 */
  oddsFreshness?: OddsFreshness;
}

/**
 * 表示中オッズの鮮度（as-of）情報。
 * EV>1.0 判定の土台が「いつ時点のオッズか」を画面に出すための共通型。
 */
export interface OddsFreshness {
  /** as-of の epoch ms（正確な発表/取得時刻が分かる場合のみ）。不明なら null */
  asOf: number | null;
  /** 表示用ラベル "HH:MM"（不明なら null） */
  label: string | null;
  /** asOf が実際の発表時刻として信頼できるか。false=速報等で正確な分単位は不明 */
  exact: boolean;
  /** どの経路のオッズか（デバッグ/表示分岐用） */
  kind: 'RT' | 'DB_TS' | 'DB_FINAL';
}

/**
 * 発表時刻 (MMDDHHmm) + raceId(先頭4桁=年) から epoch ms を構築する純粋関数。
 * サーバー(JST)で実行して絶対時刻(ms)に変換し、クライアントは Date.now() と比較する。
 * 不正値は null（鮮度表示をスキップ）。
 */
export function happyoTimeToMs(raceId: string, mmddhhmm: string | null | undefined): number | null {
  if (!raceId || raceId.length < 4) return null;
  const s = (mmddhhmm ?? '').trim();
  if (!/^\d{8}$/.test(s)) return null;
  const year = parseInt(raceId.substring(0, 4), 10);
  const mm = parseInt(s.substring(0, 2), 10);
  const dd = parseInt(s.substring(2, 4), 10);
  const hh = parseInt(s.substring(4, 6), 10);
  const mi = parseInt(s.substring(6, 8), 10);
  if (!year || mm < 1 || mm > 12 || dd < 1 || dd > 31 || hh > 23 || mi > 59) return null;
  const t = new Date(year, mm - 1, dd, hh, mi, 0, 0).getTime();
  return Number.isFinite(t) ? t : null;
}

/**
 * オッズからレースパターンを分析
 */
export function analyzeOddsPattern(horses: HorseOdds[]): OddsAnalysis {
  // 単勝オッズでソート（オッズがある馬のみ）
  const sorted = horses
    .filter((h) => h.winOdds != null && h.winOdds > 0)
    .sort((a, b) => (a.winOdds ?? 999) - (b.winOdds ?? 999));

  if (sorted.length < 3) {
    return { pattern: 'normal', label: '-', description: '' };
  }

  const first = sorted[0].winOdds ?? 999;
  const second = sorted[1].winOdds ?? 999;
  const third = sorted[2].winOdds ?? 999;
  const fourth = sorted[3]?.winOdds ?? 999;

  // 1強オッズ: 1番人気が2倍未満 && 2番人気との差が大きい（3倍以上差）
  if (first < 2.0 && second >= first * 2.5) {
    return {
      pattern: 'ikkyou',
      label: '1強',
      description: `${sorted[0].horseName || sorted[0].umaban}が断然人気`,
    };
  }

  // 3強対決: 上位3頭が10倍未満 && 4番人気以下との差が大きい
  if (first < 5.0 && second < 8.0 && third < 10.0 && fourth >= third * 1.8) {
    return {
      pattern: 'sankyou',
      label: '3強',
      description: '上位3頭の争い',
    };
  }

  // 上位拮抗: 上位4頭以上が15倍未満で混戦
  const under15 = sorted.filter((h) => (h.winOdds ?? 999) < 15).length;
  if (under15 >= 4 && first >= 2.5 && second < first * 2) {
    return {
      pattern: 'jyouikikkoh',
      label: '混戦',
      description: `${under15}頭が拮抗`,
    };
  }

  // 大混戦: 1番人気が5倍以上
  if (first >= 5.0) {
    return {
      pattern: 'daikon',
      label: '大混戦',
      description: '本命不在',
    };
  }

  return { pattern: 'normal', label: '-', description: '' };
}

export function getTrackNameFromRaceId(raceId: string): string {
  if (raceId.length < 10) return '';
  const code = raceId.substring(8, 10);
  return TRACK_CODES[code] || code;
}

/** 時系列オッズの変動情報（クライアント用） */
export interface OddsChangeInfo {
  umaban: string;
  firstOdds: number | null;
  lastOdds: number | null;
  change: number | null;
  changePercent: number | null;
  trend: 'up' | 'down' | 'stable' | 'unknown';
}

/**
 * 変動トレンドに応じた表示クラスを取得
 */
export function getTrendClass(trend: OddsChangeInfo['trend']): string {
  switch (trend) {
    case 'up':
      return 'text-blue-600 dark:text-blue-400'; // オッズ上昇 = 人気低下
    case 'down':
      return 'text-red-600 dark:text-red-400'; // オッズ下落 = 人気上昇（注目）
    case 'stable':
      return 'text-gray-500';
    default:
      return '';
  }
}

/**
 * 変動トレンドに応じたアイコン文字を取得
 */
export function getTrendIcon(trend: OddsChangeInfo['trend']): string {
  switch (trend) {
    case 'up':
      return '↑';
    case 'down':
      return '↓';
    case 'stable':
      return '→';
    default:
      return '';
  }
}

/** 直前変動情報（クライアント用） */
export interface LastMinuteChange {
  umaban: string;
  beforeOdds: number | null;
  finalOdds: number | null;
  change: number | null;
  changePercent: number | null;
  level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown';
}

/**
 * 直前変動レベルに応じた表示情報を取得
 */
export function getLastMinuteDisplay(level: LastMinuteChange['level']): {
  icon: string;
  label: string;
  className: string;
} {
  switch (level) {
    case 'hot':
      return {
        icon: '🔥',
        label: '急上昇',
        className: 'bg-red-500 text-white font-bold animate-pulse',
      };
    case 'warm':
      return {
        icon: '↗️',
        label: '人気化',
        className: 'bg-orange-400 text-white font-semibold',
      };
    case 'cold':
      return {
        icon: '↘️',
        label: '人気落',
        className: 'bg-blue-400 text-white',
      };
    case 'stable':
      return {
        icon: '',
        label: '',
        className: '',
      };
    default:
      return {
        icon: '',
        label: '',
        className: '',
      };
  }
}
