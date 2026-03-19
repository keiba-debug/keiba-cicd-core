/**
 * コースバイアスアラート (Session 113)
 *
 * コース特性（内有利度・脚質有利度）× 枠番 × 脚質から
 * 各馬の有利/不利を自動判定してアラートを生成する。
 */

import { ALL_COURSES } from '@/data/course-data';
import type { CourseInfo } from '@/components/course-card';

// =====================================================
// 型定義
// =====================================================

export type BiasLevel = 'strong_plus' | 'plus' | 'neutral' | 'minus' | 'strong_minus';

export interface CourseBiasAlert {
  /** 枠番バイアス: 内有利/外有利コースでの枠番評価 */
  drawBias?: {
    level: BiasLevel;
    label: string;        // "内有利コースで1枠" etc.
    value: number;         // innerAdvantage pt
  };
  /** 脚質バイアス: 先行有利/差し有効コースでの脚質評価 */
  styleBias?: {
    level: BiasLevel;
    label: string;        // "先行天国で逃げ馬" etc.
    value: number;         // styleAdvantage pt
  };
  /** 総合スコア (-2 ~ +2) */
  totalScore: number;
  /** 表示用サマリ */
  summary: string | null;
}

// =====================================================
// コース検索
// =====================================================

/**
 * venue + surface + distance からコースデータを特定
 */
export function findCourse(
  venue: string,
  surface: '芝' | 'ダート' | 'ダ',
  distance: number,
): CourseInfo | undefined {
  const normalizedSurface = surface === 'ダ' ? 'ダート' : surface;
  return ALL_COURSES.find(
    c => c.trackName === venue
      && c.surface === normalizedSurface
      && c.distanceMeters === distance
  );
}

// =====================================================
// バイアス判定ロジック
// =====================================================

/**
 * 枠番(1-8)から枠グループを判定
 * 1-3: inner, 4-5: middle, 6-8: outer
 */
function getDrawGroup(waku: number): 'inner' | 'middle' | 'outer' {
  if (waku <= 3) return 'inner';
  if (waku <= 5) return 'middle';
  return 'outer';
}

/**
 * avg_first_corner_ratio から脚質タイプを推定
 * 0.0-0.25: 逃げ, 0.25-0.45: 先行, 0.45-0.70: 差し, 0.70+: 追込
 */
function getRunningStyleType(ratio: number): '逃げ' | '先行' | '差し' | '追込' {
  if (ratio <= 0.25) return '逃げ';
  if (ratio <= 0.45) return '先行';
  if (ratio <= 0.70) return '差し';
  return '追込';
}

function isFrontRunner(ratio: number): boolean {
  return ratio <= 0.45;
}

function isCloser(ratio: number): boolean {
  return ratio > 0.45;
}

/**
 * コースバイアスアラートを生成
 *
 * @param venue     競馬場名 ("東京", "中山", etc.)
 * @param surface   "芝" | "ダート" | "ダ"
 * @param distance  距離(m)
 * @param waku      枠番 1-8
 * @param avgFirstCornerRatio  平均1角通過位置 (0=最前, 1=最後尾), null=不明
 */
export function getCourseBiasAlert(
  venue: string,
  surface: '芝' | 'ダート' | 'ダ',
  distance: number,
  waku: number,
  avgFirstCornerRatio: number | null | undefined,
): CourseBiasAlert {
  const course = findCourse(venue, surface, distance);
  const baba = course?.babaAnalysis;

  if (!baba) {
    return { totalScore: 0, summary: null };
  }

  const result: CourseBiasAlert = { totalScore: 0, summary: null };
  const drawGroup = getDrawGroup(waku);
  const innerAdv = baba.innerAdvantage;

  // --- 枠番バイアス判定 ---
  // innerAdvantage > 0 = 内有利, < 0 = 外有利
  // 閾値: ±3pt で有利/不利、±6pt で強い有利/不利
  if (Math.abs(innerAdv) >= 3) {
    const isInnerFavored = innerAdv > 0;

    if (drawGroup === 'inner' && isInnerFavored) {
      // 内枠 × 内有利コース = プラス
      const level: BiasLevel = innerAdv >= 6 ? 'strong_plus' : 'plus';
      result.drawBias = {
        level,
        label: `内有利${innerAdv >= 6 ? '(強)' : ''}で${waku}枠`,
        value: innerAdv,
      };
      result.totalScore += level === 'strong_plus' ? 2 : 1;
    } else if (drawGroup === 'outer' && isInnerFavored) {
      // 外枠 × 内有利コース = マイナス
      const level: BiasLevel = innerAdv >= 6 ? 'strong_minus' : 'minus';
      result.drawBias = {
        level,
        label: `内有利${innerAdv >= 6 ? '(強)' : ''}で${waku}枠`,
        value: innerAdv,
      };
      result.totalScore += level === 'strong_minus' ? -2 : -1;
    } else if (drawGroup === 'outer' && !isInnerFavored) {
      // 外枠 × 外有利コース = プラス
      const level: BiasLevel = innerAdv <= -6 ? 'strong_plus' : 'plus';
      result.drawBias = {
        level,
        label: `外有利${innerAdv <= -6 ? '(強)' : ''}で${waku}枠`,
        value: innerAdv,
      };
      result.totalScore += level === 'strong_plus' ? 2 : 1;
    } else if (drawGroup === 'inner' && !isInnerFavored) {
      // 内枠 × 外有利コース = マイナス
      const level: BiasLevel = innerAdv <= -6 ? 'strong_minus' : 'minus';
      result.drawBias = {
        level,
        label: `外有利${innerAdv <= -6 ? '(強)' : ''}で${waku}枠`,
        value: innerAdv,
      };
      result.totalScore += level === 'strong_minus' ? -2 : -1;
    }
  }

  // --- 脚質バイアス判定 ---
  // styleAdvantage: 負の値 = 先行有利 (e.g., -25 = 先行圧倒)
  // 閾値: <= -20 先行圧倒, <= -15 先行有利, >= -10 差し有効
  if (avgFirstCornerRatio != null) {
    const styleAdv = baba.styleAdvantage;
    const style = getRunningStyleType(avgFirstCornerRatio);
    const front = isFrontRunner(avgFirstCornerRatio);
    const closer = isCloser(avgFirstCornerRatio);

    if (styleAdv <= -20) {
      // 先行圧倒コース
      if (front) {
        result.styleBias = {
          level: 'strong_plus',
          label: `先行天国で${style}`,
          value: styleAdv,
        };
        result.totalScore += 2;
      } else if (closer) {
        result.styleBias = {
          level: 'strong_minus',
          label: `先行天国で${style}`,
          value: styleAdv,
        };
        result.totalScore -= 2;
      }
    } else if (styleAdv <= -15) {
      // 先行有利コース
      if (front) {
        result.styleBias = {
          level: 'plus',
          label: `先行有利で${style}`,
          value: styleAdv,
        };
        result.totalScore += 1;
      } else if (avgFirstCornerRatio > 0.60) {
        result.styleBias = {
          level: 'minus',
          label: `先行有利で${style}`,
          value: styleAdv,
        };
        result.totalScore -= 1;
      }
    } else if (styleAdv >= -10) {
      // 差し有効コース
      if (closer) {
        result.styleBias = {
          level: 'plus',
          label: `差し有効で${style}`,
          value: styleAdv,
        };
        result.totalScore += 1;
      } else if (front && avgFirstCornerRatio <= 0.25) {
        // 逃げ馬が差し有効コースで少し不利
        result.styleBias = {
          level: 'minus',
          label: `差し有効で${style}`,
          value: styleAdv,
        };
        result.totalScore -= 1;
      }
    }
  }

  // --- サマリ生成 ---
  if (result.totalScore >= 2) {
    result.summary = 'コース適性◎';
  } else if (result.totalScore >= 1) {
    result.summary = 'コース有利';
  } else if (result.totalScore <= -2) {
    result.summary = 'コース不利◎';
  } else if (result.totalScore <= -1) {
    result.summary = 'コース不利';
  }

  return result;
}

/**
 * BiasLevelに基づくスタイルクラスを返す
 */
export function getBiasColorClass(level: BiasLevel): string {
  switch (level) {
    case 'strong_plus': return 'text-blue-700 bg-blue-50';
    case 'plus': return 'text-blue-600 bg-blue-50/50';
    case 'neutral': return 'text-gray-500';
    case 'minus': return 'text-orange-600 bg-orange-50/50';
    case 'strong_minus': return 'text-red-600 bg-red-50';
  }
}
