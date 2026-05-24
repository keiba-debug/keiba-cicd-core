/**
 * My印 v2 (明示消スキーマ) 読み込みライブラリ
 *
 * 設計背景: docs/auto-purchase/09_MY_MARKS_AND_STRATEGY.md §9.3 参照
 *
 * TARGET DAT ファイルは物理層で「未入力」と「明示的な消」を区別できない
 * (両方とも 0x20 0x20)。この制約を回避するため、明示的に「消」を打った
 * 馬番リストを別ファイルに保存し、DAT と合成して扱う。
 *
 * ファイル配置: $KEIBA_DATA_ROOT/my_marks_v2/{race_id}.json
 * スキーマ:
 *   {
 *     "race_id": "2026012406010208",
 *     "explicit_erase": [3, 7],
 *     "explicit_no_mark": [],
 *     "updated_at": "2026-05-23T21:30:00+09:00",
 *     "source": "manual"
 *   }
 */

import * as fs from 'fs';
import * as path from 'path';

// 消し馬を表す内部正規化トークン
// 上位 UI / ML 特徴量は全てこの定数で判定する
export const ERASE_MARK = '消' as const;

export type MyMarksV2Source = 'manual' | 'auto_pruner' | 'import';

export interface MyMarksV2 {
  race_id: string;
  explicit_erase: number[];
  explicit_no_mark: number[];
  updated_at: string;
  source: MyMarksV2Source;
}

const VALID_SOURCES: readonly MyMarksV2Source[] = ['manual', 'auto_pruner', 'import'];

function getMyMarksV2Dir(): string {
  const root = process.env.KEIBA_DATA_ROOT || 'C:\\KEIBA-CICD\\data3';
  return path.join(root, 'my_marks_v2');
}

export function getMyMarksV2FilePath(raceId: string): string {
  return path.join(getMyMarksV2Dir(), `${raceId}.json`);
}

function sanitizeHorseNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<number>();
  const out: number[] = [];
  for (const n of value) {
    if (typeof n !== 'number' || !Number.isInteger(n)) continue;
    if (n < 1 || n > 18) continue;
    if (seen.has(n)) continue;
    seen.add(n);
    out.push(n);
  }
  return out.sort((a, b) => a - b);
}

/**
 * 指定レースの my_marks_v2 を読み込む。ファイル無し or パース失敗時は null。
 * 上位は null を「v2 データ無し = 全馬 v2 未入力」として扱う。
 */
export function readMyMarksV2(raceId: string): MyMarksV2 | null {
  const filePath = getMyMarksV2FilePath(raceId);
  if (!fs.existsSync(filePath)) return null;

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);
    if (typeof data !== 'object' || data === null) return null;

    const fileRaceId = typeof data.race_id === 'string' ? data.race_id : raceId;
    if (fileRaceId !== raceId) {
      console.warn(`[my-marks-v2-reader] race_id mismatch in ${filePath}: file=${fileRaceId} expected=${raceId}`);
    }

    const source: MyMarksV2Source = VALID_SOURCES.includes(data.source) ? data.source : 'manual';

    return {
      race_id: raceId,
      explicit_erase: sanitizeHorseNumberArray(data.explicit_erase),
      explicit_no_mark: sanitizeHorseNumberArray(data.explicit_no_mark),
      updated_at: typeof data.updated_at === 'string' ? data.updated_at : '',
      source,
    };
  } catch (e) {
    console.error(`[my-marks-v2-reader] parse error for ${raceId}:`, e);
    return null;
  }
}

/**
 * DAT 由来の horseMarks (馬番→印) に my_marks_v2.explicit_erase を合成する。
 *
 * - my_marks_v2 が無ければ horseMarks をそのまま返す
 * - explicit_erase の馬番には ERASE_MARK ('消') を上書きする
 *   (DAT で既に印があってもユーザーが後から「消」を打ったとみなし v2 が勝つ)
 *
 * @returns 合成後の新オブジェクト (元 horseMarks は破壊しない)
 */
export function mergeWithEraseMarks(
  horseMarks: Record<number, string>,
  v2: MyMarksV2 | null
): Record<number, string> {
  if (!v2 || v2.explicit_erase.length === 0) return { ...horseMarks };
  const merged: Record<number, string> = { ...horseMarks };
  for (const uma of v2.explicit_erase) {
    merged[uma] = ERASE_MARK;
  }
  return merged;
}
