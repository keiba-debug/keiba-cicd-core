/**
 * レース結果表示の共通ユーティリティ (Session 187)
 *
 * 従来 RaceResultSection / MarginVisualization / RaceProgressVisualization /
 * EarlyPositionComparison / PositionGainIndicator に重複実装されていた
 * 「着差→秒換算」「通過順位パース」「タイム→秒変換」を一本化する。
 *
 * 換算基準: 1馬身 ≒ 0.16秒 (CourseReplay エンジンの半馬身0.08秒と整合)
 */

/** 1馬身 ≒ 0.16秒 */
export const SEC_PER_BASHIN = 0.16;
/** 半馬身 ≒ 0.08秒 */
export const SEC_PER_HALF_BASHIN = SEC_PER_BASHIN / 2;

// 着差の特殊表記 → 馬身数
const SPECIAL_MARGIN_BASHIN: Record<string, number> = {
  '同着': 0,
  'ハナ': 0.1,
  'はな': 0.1,
  'アタマ': 0.2,
  'あたま': 0.2,
  'クビ': 0.3,
  'くび': 0.3,
  '大差': 12,
  '大': 12,
};

/**
 * 着差表記 → 馬身数
 * 対応形式: "ハナ" / "クビ" / "1/2" / "3/4" / "1.1/2" / "1・3/4" / "1 3/4" / "2" / "大差"
 * @returns 馬身数。パース不能は null
 */
export function marginToBashin(margin: string | undefined | null): number | null {
  if (!margin) return null;
  const trimmed = margin.trim();
  if (!trimmed || trimmed === '-') return null;

  // 特殊表記（完全一致）
  if (SPECIAL_MARGIN_BASHIN[trimmed] !== undefined) {
    return SPECIAL_MARGIN_BASHIN[trimmed];
  }

  // 分数付き表記: "1.1/2" "1・3/4" "1 3/4" "3/4" "1/2"
  // ※ includes マッチだと "1.1/2" が "1/2" に先に化けるので、必ず全体マッチで解釈する
  const fractionMatch = trimmed.match(/^(?:(\d+)[\s.・])?(\d+)\/(\d+)$/);
  if (fractionMatch) {
    const whole = parseInt(fractionMatch[1] || '0', 10);
    const numerator = parseInt(fractionMatch[2], 10);
    const denominator = parseInt(fractionMatch[3], 10);
    if (denominator > 0) return whole + numerator / denominator;
  }

  // 数値のみ（馬身数）: "2" "10" "1.5"
  const numMatch = trimmed.match(/^\d+(?:\.\d+)?$/);
  if (numMatch) {
    return parseFloat(trimmed);
  }

  return null;
}

/**
 * 着差表記 → 秒換算（1馬身 ≒ 0.16秒）
 * パース不能は 0
 */
export function marginToSeconds(margin: string | undefined | null): number {
  const bashin = marginToBashin(margin);
  return bashin != null ? bashin * SEC_PER_BASHIN : 0;
}

/** 着差の接戦度分類（表記ベース。タイム0.1秒粒度より細かい判定ができる） */
export type MarginType = 'photo' | 'close' | 'normal' | 'big';

export function classifyMargin(margin: string | undefined | null): MarginType {
  const bashin = marginToBashin(margin);
  if (bashin == null) return 'normal';
  if (bashin <= 0.2) return 'photo';   // 同着/ハナ/アタマ
  if (bashin <= 0.5) return 'close';   // クビ/1/2
  if (bashin >= 8) return 'big';       // 8馬身以上/大差
  return 'normal';
}

// 丸数字 → 数値（通過順位パース用）
const CIRCLE_NUM_MAP: Record<string, number> = {
  '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
  '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
  '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
  '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20,
};

/**
 * 通過順位文字列をパースして数値配列に変換
 * @param raw - 通過順位の生文字列 (例: "3-2-3-1", "5555", "⑫1213")
 * @param totalHorses - 出走頭数（区切り無し文字列の2桁判定に使用）
 */
export function parsePassingOrders(raw: string | undefined | null, totalHorses: number = 18): number[] {
  if (!raw) return [];

  // ハイフン区切り
  if (raw.includes('-')) {
    return raw.split('-').map(p => parseInt(p.trim(), 10)).filter(n => !isNaN(n) && n > 0);
  }

  const positions: number[] = [];
  let remaining = raw;
  const hasTwoDigitNumbers = totalHorses >= 10;

  while (remaining.length > 0) {
    let matched = false;

    // 丸数字
    for (const [circle, num] of Object.entries(CIRCLE_NUM_MAP)) {
      if (remaining.startsWith(circle)) {
        positions.push(num);
        remaining = remaining.slice(circle.length);
        matched = true;
        break;
      }
    }
    if (matched) continue;

    // 2桁数字（10頭以上のレースのみ。10〜頭数の範囲なら2桁として解釈）
    if (hasTwoDigitNumbers && remaining.length >= 2) {
      const twoDigitNum = parseInt(remaining.slice(0, 2), 10);
      if (!isNaN(twoDigitNum) && twoDigitNum >= 10 && twoDigitNum <= Math.max(totalHorses, 18)) {
        positions.push(twoDigitNum);
        remaining = remaining.slice(2);
        continue;
      }
    }

    // 1桁数字
    const oneDigitNum = parseInt(remaining.slice(0, 1), 10);
    if (!isNaN(oneDigitNum) && oneDigitNum > 0) {
      positions.push(oneDigitNum);
      remaining = remaining.slice(1);
      continue;
    }

    // マッチしない文字はスキップ
    remaining = remaining.slice(1);
  }

  return positions;
}

/** 通過順位をハイフン区切りにフォーマット（パース不能は "-"） */
export function formatPassingOrders(raw: string | undefined | null, totalHorses: number = 18): string {
  const positions = parsePassingOrders(raw, totalHorses);
  return positions.length > 0 ? positions.join('-') : '-';
}

/**
 * 走破タイム文字列 → 秒
 * 対応形式: "1:45.0" / "1.45.0" / "45.0"
 * @returns 秒。パース不能は null
 */
export function timeToSeconds(t: string | undefined | null): number | null {
  if (!t) return null;
  const s = t.trim().replace(':', '.');
  const parts = s.split('.');
  if (parts.length === 3) {
    const m = parseInt(parts[0], 10), sec = parseInt(parts[1], 10), tenth = parseInt(parts[2], 10);
    if ([m, sec, tenth].some(isNaN)) return null;
    return m * 60 + sec + tenth / 10;
  }
  if (parts.length === 2) {
    const sec = parseInt(parts[0], 10), tenth = parseInt(parts[1], 10);
    if ([sec, tenth].some(isNaN)) return null;
    return sec + tenth / 10;
  }
  const num = parseFloat(s);
  return isNaN(num) ? null : num;
}
