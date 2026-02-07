/**
 * プラス（良い）表示用の色クラスを統一
 * レーティング高値・好タイム◎・上がり3F最速・ラップS+/A+・調教↗ などに使用
 */

/** プラス強調のテキスト（好タイム◎、上がり3F最速、調教↗ など） */
export const POSITIVE_TEXT =
  'text-green-600 dark:text-green-400 font-bold';

/** プラス強調の背景＋文字（レーティング高帯、ラップS+/S= など） */
export const POSITIVE_BG =
  'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200';

/** ややプラス（ラップA+/A= など） */
export const POSITIVE_BG_MUTED =
  'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300';

/** レーティング用：最上位帯（G1レベル・65以上）— 最も目立つ */
export const RATING_TOP =
  'bg-green-200 dark:bg-green-800/80 text-green-900 dark:text-green-100 font-bold ring-1 ring-green-400 dark:ring-green-500';

/** レーティング用：上位帯（G2-G3/OPレベル・62以上） */
export const RATING_HIGH =
  'bg-emerald-200 dark:bg-emerald-800/60 text-emerald-900 dark:text-emerald-100 font-bold';

/** レーティング用：中上位（3勝クラス・59以上） */
export const RATING_MID_HIGH = 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 font-medium';

/** レーティング用：中位（2勝クラス・55以上） */
export const RATING_MID = 'bg-green-50 dark:bg-green-900/25 text-green-700 dark:text-green-300';

/**
 * レーティング値に応じた背景・文字色クラスを返す（高レーティングを明確に強調）
 */
export function getRatingColor(rating?: string | number): string {
  if (rating == null || rating === '' || rating === '-') return '';
  const value = typeof rating === 'string' ? parseFloat(rating) : rating;
  if (isNaN(value)) return '';
  if (value >= 65) return RATING_TOP;
  if (value >= 62) return RATING_HIGH;
  if (value >= 59) return RATING_MID_HIGH;
  if (value >= 55) return RATING_MID;
  if (value >= 50) return 'text-muted-foreground';
  return 'text-muted-foreground/50';
}
