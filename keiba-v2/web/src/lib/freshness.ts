/**
 * E-006 データ鮮度判定（純関数）
 *
 * 分析JSONの coverage.to_date（データが何日まで被覆しているか）を today と比較し、
 * 鮮度レベルを返す。**生成時刻(created_at) ではなく被覆末日(to_date) を見る**のが要点
 * — ML/分析キャッシュ凍結インシデント（jockey 3ヶ月凍結）は created_at が新しくても
 * to_date が古い＝再生成が走っても期間が古いまま、という形で起きたため。
 */

export type FreshnessLevel = 'fresh' | 'aging' | 'stale' | 'unknown';

export interface Freshness {
  level: FreshnessLevel;
  daysBehind: number | null; // to_date から today までの日数（不明時 null）
  label: string;             // 表示ラベル
}

// 競馬データは週末開催ぶんが翌週まで揃うため、~10日は正常な遅延。
const AGING_DAYS = 11; // これ以上で「やや古い」
const STALE_DAYS = 31; // これ以上で「要更新」（凍結インシデントの検知ライン）

/** "YYYY-MM-DD" を UTC 正午の Date に（タイムゾーンずれを避ける）。失敗時 null。 */
function parseDate(s?: string | null): Date | null {
  if (!s) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (!m) return null;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12));
  return isNaN(d.getTime()) ? null : d;
}

/**
 * coverage.to_date と today から鮮度を判定する。
 * @param toDate 分析データの被覆末日 "YYYY-MM-DD"
 * @param now    基準日時（既定: 現在）。テスト用に注入可能。
 */
export function computeFreshness(toDate?: string | null, now: Date = new Date()): Freshness {
  const to = parseDate(toDate);
  if (!to) return { level: 'unknown', daysBehind: null, label: '鮮度不明' };
  const days = Math.floor((now.getTime() - to.getTime()) / 86_400_000);
  if (days < AGING_DAYS) return { level: 'fresh', daysBehind: days, label: '最新' };
  if (days < STALE_DAYS) return { level: 'aging', daysBehind: days, label: 'やや古い' };
  return { level: 'stale', daysBehind: days, label: '要更新' };
}

/** Tailwind カラークラス（バッジ用） */
export function freshnessClass(level: FreshnessLevel): string {
  switch (level) {
    case 'fresh':
      return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 border-green-300';
    case 'aging':
      return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border-amber-300';
    case 'stale':
      return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border-red-400';
    default:
      return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 border-gray-300';
  }
}
