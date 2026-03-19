/**
 * TARGET チェック馬リスト (CHECKUMA.LST) リーダー/ライター
 *
 * ファイル形式:
 *   horse_id(10) + MMDD(4) + level(1) + comment(cp932, optional) + CRLF
 *
 *   - horse_id: ketto_num (10桁)
 *   - MMDD: チェック登録日 (月2桁+日2桁)
 *   - level: チェックレベル (0-9, TARGETのチェック色に対応)
 *   - comment: 任意のメモ (Shift-JIS)
 *
 * 例: 2310217826012520TEST\r\n
 *   → horse_id=2310217826, date=01/25, level=2, comment="TEST"
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';

const JV_ROOT = process.env.JV_DATA_ROOT_DIR || 'C:\\TFJV';
const CHECKUMA_PATH = path.join(JV_ROOT, 'CHECKUMA.LST');

export interface CheckUmaEntry {
  horseId: string;
  month: number;
  day: number;
  level: number;
  comment: string;
}

/**
 * CHECKUMA.LST を読み込んで全エントリを返す
 */
export function readCheckUmaList(): CheckUmaEntry[] {
  try {
    if (!fs.existsSync(CHECKUMA_PATH)) {
      return [];
    }

    const buf = fs.readFileSync(CHECKUMA_PATH);
    const lines = splitCrLf(buf);
    const entries: CheckUmaEntry[] = [];

    for (const line of lines) {
      if (line.length < 15) continue;

      const horseId = line.subarray(0, 10).toString('ascii');
      const mmdd = line.subarray(10, 14).toString('ascii');
      const levelChar = line.subarray(14, 15).toString('ascii');

      const commentBuf = line.subarray(15);
      const comment = commentBuf.length > 0
        ? iconv.decode(commentBuf, 'cp932').trim()
        : '';

      const month = parseInt(mmdd.substring(0, 2), 10);
      const day = parseInt(mmdd.substring(2, 4), 10);
      const level = parseInt(levelChar, 10) || 0;

      entries.push({ horseId, month, day, level, comment });
    }

    return entries;
  } catch (error) {
    console.error('[CheckUma] Read error:', error);
    return [];
  }
}

/**
 * 指定馬がチェックリストに含まれるか
 */
export function getCheckUmaEntry(horseId: string): CheckUmaEntry | null {
  const entries = readCheckUmaList();
  return entries.find(e => e.horseId === horseId) ?? null;
}

/**
 * 複数馬のチェック状態を一括取得
 */
export function getCheckUmaMap(horseIds: string[]): Map<string, CheckUmaEntry> {
  const entries = readCheckUmaList();
  const idSet = new Set(horseIds);
  const map = new Map<string, CheckUmaEntry>();
  for (const e of entries) {
    if (idSet.has(e.horseId)) {
      map.set(e.horseId, e);
    }
  }
  return map;
}

/**
 * チェック馬を追加（既存なら上書き）
 */
export function addCheckUma(
  horseId: string,
  level: number = 0,
  comment: string = ''
): boolean {
  try {
    const entries = readCheckUmaList();
    const now = new Date();
    const month = now.getMonth() + 1;
    const day = now.getDate();

    // 既存エントリを除外
    const filtered = entries.filter(e => e.horseId !== horseId);
    filtered.push({ horseId, month, day, level, comment });

    // levelでソート → horse_idでソート（TARGETと同じ並び順）
    filtered.sort((a, b) => {
      if (a.level !== b.level) return a.level - b.level;
      return a.horseId.localeCompare(b.horseId);
    });

    writeCheckUmaList(filtered);
    return true;
  } catch (error) {
    console.error('[CheckUma] Add error:', error);
    return false;
  }
}

/**
 * チェック馬を削除
 */
export function removeCheckUma(horseId: string): boolean {
  try {
    const entries = readCheckUmaList();
    const filtered = entries.filter(e => e.horseId !== horseId);
    if (filtered.length === entries.length) return false; // not found
    writeCheckUmaList(filtered);
    return true;
  } catch (error) {
    console.error('[CheckUma] Remove error:', error);
    return false;
  }
}

/**
 * エントリリストをファイルに書き込み
 */
function writeCheckUmaList(entries: CheckUmaEntry[]): void {
  const lines: Buffer[] = [];

  for (const e of entries) {
    const mmdd = String(e.month).padStart(2, '0') + String(e.day).padStart(2, '0');
    const levelStr = String(Math.min(9, Math.max(0, e.level)));
    const asciiPart = Buffer.from(`${e.horseId}${mmdd}${levelStr}`, 'ascii');

    if (e.comment) {
      const commentBuf = iconv.encode(e.comment, 'cp932');
      lines.push(Buffer.concat([asciiPart, commentBuf]));
    } else {
      lines.push(asciiPart);
    }
  }

  // Join with CRLF, end with CRLF
  const crlf = Buffer.from('\r\n');
  const parts: Buffer[] = [];
  for (let i = 0; i < lines.length; i++) {
    parts.push(lines[i]);
    parts.push(crlf);
  }

  fs.writeFileSync(CHECKUMA_PATH, Buffer.concat(parts));
}

/**
 * Buffer を CRLF で分割
 */
function splitCrLf(buf: Buffer): Buffer[] {
  const results: Buffer[] = [];
  let start = 0;

  for (let i = 0; i < buf.length - 1; i++) {
    if (buf[i] === 0x0d && buf[i + 1] === 0x0a) {
      if (i > start) {
        results.push(buf.subarray(start, i));
      }
      start = i + 2;
      i++; // skip \n
    }
  }

  // Last line without CRLF
  if (start < buf.length) {
    const last = buf.subarray(start);
    if (last.length > 0 && !(last.length === 1 && last[0] === 0x0a)) {
      results.push(last);
    }
  }

  return results;
}
