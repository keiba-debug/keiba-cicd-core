/**
 * My印 v2 (明示消スキーマ) 書き込みライブラリ
 *
 * 責務:
 *  - $KEIBA_DATA_ROOT/my_marks_v2/{race_id}.json のアトミック書き込み
 *  - $KEIBA_DATA_ROOT/my_marks_v2/_audit/{yyyy-mm}.jsonl への変更履歴追記
 *
 * 設計背景: docs/auto-purchase/09_MY_MARKS_AND_STRATEGY.md §9.3 / §9.5
 */

import * as fs from 'fs';
import * as path from 'path';
import { writeAtomic, withFileLock } from '@/lib/io/atomic-write';
import {
  type MyMarksV2,
  type MyMarksV2Source,
  getMyMarksV2FilePath,
  readMyMarksV2,
} from './my-marks-v2-reader';

export interface WriteMyMarksV2Input {
  explicit_erase: number[];
  explicit_no_mark?: number[];
  source?: MyMarksV2Source;
}

export interface WriteMyMarksV2Result {
  before: MyMarksV2 | null;
  after: MyMarksV2;
  diff: {
    added_erase: number[];
    removed_erase: number[];
    added_no_mark: number[];
    removed_no_mark: number[];
  };
}

function getMyMarksV2Dir(): string {
  const root = process.env.KEIBA_DATA_ROOT || 'C:\\KEIBA-CICD\\data3';
  return path.join(root, 'my_marks_v2');
}

function getAuditFilePath(date: Date = new Date()): string {
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  return path.join(getMyMarksV2Dir(), '_audit', `${yyyy}-${mm}.jsonl`);
}

function ensureDir(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function dedupeAndValidate(arr: unknown): number[] {
  if (!Array.isArray(arr)) return [];
  const seen = new Set<number>();
  const out: number[] = [];
  for (const n of arr) {
    if (typeof n !== 'number' || !Number.isInteger(n)) continue;
    if (n < 1 || n > 18) continue;
    if (seen.has(n)) continue;
    seen.add(n);
    out.push(n);
  }
  return out.sort((a, b) => a - b);
}

function setDiff(after: number[], before: number[]): { added: number[]; removed: number[] } {
  const beforeSet = new Set(before);
  const afterSet = new Set(after);
  const added = after.filter((n) => !beforeSet.has(n));
  const removed = before.filter((n) => !afterSet.has(n));
  return { added, removed };
}

function nowJstIso(): string {
  // JST 固定で記録 (税務監査で時系列再現するため)
  const d = new Date();
  const jstOffsetMin = 9 * 60;
  const localOffsetMin = -d.getTimezoneOffset();
  const adjustedMs = d.getTime() + (jstOffsetMin - localOffsetMin) * 60 * 1000;
  const jst = new Date(adjustedMs);
  const yyyy = jst.getUTCFullYear();
  const mm = String(jst.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(jst.getUTCDate()).padStart(2, '0');
  const hh = String(jst.getUTCHours()).padStart(2, '0');
  const mi = String(jst.getUTCMinutes()).padStart(2, '0');
  const ss = String(jst.getUTCSeconds()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}:${ss}+09:00`;
}

function appendAuditLog(entry: object): void {
  const auditPath = getAuditFilePath();
  ensureDir(path.dirname(auditPath));
  fs.appendFileSync(auditPath, JSON.stringify(entry) + '\n', 'utf-8');
}

// writeAtomic / withFileLock は Session 126 で `@/lib/io/atomic-write` に共通化
// (シズネレビュー af17447ae78bb3da5 M1: bankroll と同じ穴を 2 回開けない)

/**
 * 指定レースの my_marks_v2 を書き込む。
 *
 * - 既存ファイルがあれば before として読み、diff を audit log に追記
 * - 新ファイルはアトミック書き込み (tmp → rename)
 * - 同一内容 (diff が空) でも updated_at だけ更新するため毎回書く
 */
export async function writeMyMarksV2(
  raceId: string,
  input: WriteMyMarksV2Input
): Promise<WriteMyMarksV2Result> {
  const filePath = getMyMarksV2FilePath(raceId);

  return withFileLock(filePath, () => {
    // ロック内で before を読む — 同時 PUT のロストアップデート防止
    const before = readMyMarksV2(raceId);
    const after: MyMarksV2 = {
      race_id: raceId,
      explicit_erase: dedupeAndValidate(input.explicit_erase),
      explicit_no_mark: dedupeAndValidate(input.explicit_no_mark ?? []),
      updated_at: nowJstIso(),
      source: input.source ?? 'manual',
    };

    const eraseDiff = setDiff(after.explicit_erase, before?.explicit_erase ?? []);
    const noMarkDiff = setDiff(after.explicit_no_mark, before?.explicit_no_mark ?? []);

    // audit log 追記 (失敗しても本体書き込みは続行: ログ欠損より状態欠損の方が事故大)
    try {
      appendAuditLog({
        ts: after.updated_at,
        race_id: raceId,
        before: before
          ? { explicit_erase: before.explicit_erase, explicit_no_mark: before.explicit_no_mark }
          : null,
        after: {
          explicit_erase: after.explicit_erase,
          explicit_no_mark: after.explicit_no_mark,
        },
        diff: {
          added_erase: eraseDiff.added,
          removed_erase: eraseDiff.removed,
          added_no_mark: noMarkDiff.added,
          removed_no_mark: noMarkDiff.removed,
        },
        source: after.source,
      });
    } catch (e) {
      console.error(`[my-marks-v2-writer] audit log append failed for ${raceId}:`, e);
    }

    writeAtomic(filePath, JSON.stringify(after, null, 2));

    return {
      before,
      after,
      diff: {
        added_erase: eraseDiff.added,
        removed_erase: eraseDiff.removed,
        added_no_mark: noMarkDiff.added,
        removed_no_mark: noMarkDiff.removed,
      },
    };
  });
}
