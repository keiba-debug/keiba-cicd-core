/**
 * 馬場コンディションの解釈ラベル（JRA資料に基づく目安）
 * クッション値・含水率から「硬め/標準/軟らかめ」「良/稍重/重/不良」の参考表示用
 */

import type { Surface } from './baba-reader';

/**
 * クッション値 → クッション性ラベル（芝馬場の基準）
 */
export function getCushionLabel(value: number): string {
  if (value >= 12) return '硬め';
  if (value >= 10) return 'やや硬め';
  if (value >= 8) return '標準';
  if (value >= 7) return 'やや軟らかめ';
  return '軟らかめ';
}

/**
 * 芝コース: 競馬場別の含水率～馬場状態の目安（%）
 * 良・稍重・重・不良の範囲（競馬場ごとに異なる）
 */
const TURF_MOISTURE_RANGES: Record<
  string,
  { good: number; yielding: [number, number]; heavy: [number, number]; bad: number }
> = {
  札幌: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  函館: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  福島: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  新潟: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  中山: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  東京: { good: 19, yielding: [17, 21], heavy: [18, 23], bad: 20 },
  中京: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  京都: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  阪神: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
  小倉: { good: 13, yielding: [11, 15], heavy: [14, 18], bad: 17 },
};

/**
 * ダート: 全場共通の含水率～馬場状態の目安（%）
 * 良 9%以下、稍重 7～13%、重 11～16%、不良 14%以上
 */
function getDirtMoistureConditionLabel(p: number): string {
  if (p <= 9) return '良';
  if (p < 11) return '稍重';
  if (p <= 16) return '重';
  return '不良';
}

/**
 * 芝: 競馬場別の含水率～馬場状態の目安
 */
function getTurfMoistureConditionLabel(venue: string, p: number): string {
  const r = TURF_MOISTURE_RANGES[venue] ?? TURF_MOISTURE_RANGES['中山'];
  if (p <= r.good) return '良';
  if (p >= r.bad) return '不良';
  if (p >= r.heavy[0] && p <= r.heavy[1]) return '重';
  if (p >= r.yielding[0] && p <= r.yielding[1]) return '稍重';
  if (p <= r.yielding[1]) return '稍重';
  return '重';
}

/**
 * 含水率（%）から馬場状態の目安ラベルを返す
 * 「馬場状態は含水率だけで決まるものではない」ため参考表示用
 */
export function getMoistureConditionLabel(
  venue: string,
  surface: Surface,
  moisturePercent: number
): string {
  if (surface === 'dirt') {
    return getDirtMoistureConditionLabel(moisturePercent);
  }
  return getTurfMoistureConditionLabel(venue, moisturePercent);
}

/**
 * 馬場状態ラベルに応じたバッジ用クラス（色）
 * @deprecated 新しい getConditionBadgeClassBySurface を使用してください
 */
export function getConditionBadgeClass(condition: string): string {
  switch (condition) {
    case '良':
      return 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200';
    case '稍重':
      return 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200';
    case '重':
      return 'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200';
    case '不良':
      return 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200';
    default:
      return 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200';
  }
}

/**
 * 芝/ダート別の馬場状態バッジ用クラス（色）
 * 芝: 緑系（良→高速、重→水を含んでパワー必要）
 * ダート: 茶/オレンジ系（良→軽い砂、重→パワー必要で時計がかかる）
 */
export function getConditionBadgeClassBySurface(
  condition: string,
  surface: Surface
): { bgClass: string; textClass: string; borderClass: string } {
  if (surface === 'turf') {
    // 芝: 緑系のグラデーション
    switch (condition) {
      case '良':
        // 高速馬場 - 明るい緑
        return {
          bgClass: 'bg-emerald-100 dark:bg-emerald-900/40',
          textClass: 'text-emerald-700 dark:text-emerald-300',
          borderClass: 'border-emerald-300 dark:border-emerald-700',
        };
      case '稍重':
        // やや水分あり - 緑がかった黄
        return {
          bgClass: 'bg-lime-100 dark:bg-lime-900/40',
          textClass: 'text-lime-700 dark:text-lime-300',
          borderClass: 'border-lime-300 dark:border-lime-700',
        };
      case '重':
        // 水を含む - 青緑
        return {
          bgClass: 'bg-teal-100 dark:bg-teal-900/40',
          textClass: 'text-teal-700 dark:text-teal-300',
          borderClass: 'border-teal-300 dark:border-teal-700',
        };
      case '不良':
        // 水浸し - 濃い青
        return {
          bgClass: 'bg-cyan-200 dark:bg-cyan-900/50',
          textClass: 'text-cyan-800 dark:text-cyan-200',
          borderClass: 'border-cyan-400 dark:border-cyan-600',
        };
      default:
        return {
          bgClass: 'bg-gray-100 dark:bg-gray-800',
          textClass: 'text-gray-700 dark:text-gray-300',
          borderClass: 'border-gray-300 dark:border-gray-600',
        };
    }
  } else {
    // ダート: 茶/オレンジ系のグラデーション
    switch (condition) {
      case '良':
        // 軽い砂 - ベージュ/薄い茶
        return {
          bgClass: 'bg-amber-50 dark:bg-amber-900/30',
          textClass: 'text-amber-700 dark:text-amber-300',
          borderClass: 'border-amber-200 dark:border-amber-700',
        };
      case '稍重':
        // やや重い - オレンジ
        return {
          bgClass: 'bg-orange-100 dark:bg-orange-900/40',
          textClass: 'text-orange-700 dark:text-orange-300',
          borderClass: 'border-orange-300 dark:border-orange-700',
        };
      case '重':
        // パワー必要 - 濃いオレンジ/赤寄り
        return {
          bgClass: 'bg-orange-200 dark:bg-orange-800/50',
          textClass: 'text-orange-800 dark:text-orange-200',
          borderClass: 'border-orange-400 dark:border-orange-600',
        };
      case '不良':
        // かなり重い（時計かかる） - 赤茶
        return {
          bgClass: 'bg-red-200 dark:bg-red-900/50',
          textClass: 'text-red-800 dark:text-red-200',
          borderClass: 'border-red-400 dark:border-red-600',
        };
      default:
        return {
          bgClass: 'bg-gray-100 dark:bg-gray-800',
          textClass: 'text-gray-700 dark:text-gray-300',
          borderClass: 'border-gray-300 dark:border-gray-600',
        };
    }
  }
}

/**
 * 芝/ダートのアイコン・ラベル用情報
 */
export function getSurfaceInfo(surface: Surface): {
  label: string;
  emoji: string;
  colorClass: string;
} {
  if (surface === 'turf') {
    return {
      label: '芝',
      emoji: '🌿',
      colorClass: 'text-green-600 dark:text-green-400',
    };
  }
  return {
    label: 'ダ',
    emoji: '🏜️',
    colorClass: 'text-amber-600 dark:text-amber-400',
  };
}

/**
 * 天候文字列 → アイコン
 */
export function getWeatherIcon(weather: string): string {
  switch (weather) {
    case '晴': return '☀';
    case '曇': return '☁';
    case '雨': return '🌧';
    case '小雨': return '🌦';
    case '雪': return '❄';
    case '小雪': return '🌨';
    default: return '';
  }
}

/**
 * JRDB天候コード → 天候文字列
 */
export function getWeatherFromCode(code: number): string {
  switch (code) {
    case 1: return '晴';
    case 2: return '曇';
    case 3: return '雨';
    case 4: return '小雨';
    case 5: return '雪';
    case 6: return '小雪';
    default: return '';
  }
}

/**
 * JRDB差値からバイアスラベルを取得
 * マイナス=内有利、プラス=外有利
 */
export function getBiasLabel(sa: number): { label: string; level: 'inner' | 'outer' | 'flat' } {
  if (sa <= -10) return { label: '内有利', level: 'inner' };
  if (sa <= -5) return { label: 'やや内', level: 'inner' };
  if (sa >= 10) return { label: '外有利', level: 'outer' };
  if (sa >= 5) return { label: 'やや外', level: 'outer' };
  return { label: 'フラット', level: 'flat' };
}
