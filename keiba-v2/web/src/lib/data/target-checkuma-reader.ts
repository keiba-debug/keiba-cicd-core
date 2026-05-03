/**
 * TARGET チェック馬リスト (CHECKUMA.LST) リーダー/ライター
 *
 * ファイル形式:
 *   horse_id(10) + MMDD(4) + level(1) + comment(cp932, optional) + CRLF
 *
 *   - horse_id: TARGET形式 = YY(生年下2桁) + 6桁連番 + YY(登録年下2桁)
 *     例: 2310563826 = 2023年生・連番105638・2026年登録
 *   - JRA-VAN kettoNum (YYYY+6桁連番) とは異なるため変換が必要
 *   - MMDD: チェック登録日 (月2桁+日2桁)
 *   - level: チェックレベル (0-9, TARGETのチェック色に対応)
 *   - comment: 任意のメモ (Shift-JIS)
 *
 * 入出力は JRA-VAN kettoNum (例: 2023105638) を使い、
 * ファイルI/Oの際に TARGET形式 (例: 2310563826) へ変換する。
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';

const JV_ROOT = process.env.JV_DATA_ROOT_DIR || 'C:\\TFJV';
const CHECKUMA_PATH = path.join(JV_ROOT, 'CHECKUMA.LST');

export interface CheckUmaEntry {
  /** JRA-VAN形式の kettoNum (YYYY+6桁連番) */
  horseId: string;
  /** ファイル上の元の horse_id (TARGET形式) — 書き出し時に登録年を保持するため */
  rawHorseId: string;
  month: number;
  day: number;
  level: number;
  comment: string;
}

/**
 * TARGET 10桁 horse_id を JRA-VAN kettoNum に変換
 * TARGET: YY+SSSSSS+RR  →  JRA-VAN: 20YY+SSSSSS
 * 既に "20" で始まる場合はJRA-VAN形式として扱う（レガシー互換）
 */
function targetToJra(rawHorseId: string): string {
  if (!/^\d{10}$/.test(rawHorseId)) return rawHorseId;
  // TARGET形式の最初2桁が生年下2桁。"20"以外の場合は確実にTARGET形式
  // "20" で始まる場合は2020年生まれの可能性（曖昧）だがTARGET形式として解釈
  return '20' + rawHorseId.slice(0, 8);
}

/**
 * JRA-VAN kettoNum を TARGET horse_id に変換
 * JRA-VAN: YYYY+SSSSSS  →  TARGET: YY+SSSSSS+RR(登録年下2桁)
 */
function jraToTarget(jraKettoNum: string, regYear?: number): string {
  if (!/^\d{10}$/.test(jraKettoNum)) return jraKettoNum;
  const canonical = jraKettoNum.slice(2); // 20YY+SSSSSS → YY+SSSSSS
  const reg = regYear ?? new Date().getFullYear();
  const regYY = String(reg % 100).padStart(2, '0');
  return canonical + regYY;
}

/**
 * CHECKUMA.LST を読み込んで全エントリを返す
 * horseId は JRA-VAN 形式に変換済み
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

      const rawHorseId = line.subarray(0, 10).toString('ascii');
      const mmdd = line.subarray(10, 14).toString('ascii');
      const levelChar = line.subarray(14, 15).toString('ascii');

      const commentBuf = line.subarray(15);
      const comment = commentBuf.length > 0
        ? iconv.decode(commentBuf, 'cp932').trim()
        : '';

      const month = parseInt(mmdd.substring(0, 2), 10);
      const day = parseInt(mmdd.substring(2, 4), 10);
      const level = parseInt(levelChar, 10) || 0;

      entries.push({
        horseId: targetToJra(rawHorseId),
        rawHorseId,
        month,
        day,
        level,
        comment,
      });
    }

    return entries;
  } catch (error) {
    console.error('[CheckUma] Read error:', error);
    return [];
  }
}

/**
 * 指定馬がチェックリストに含まれるか (JRA-VAN kettoNum で検索)
 */
export function getCheckUmaEntry(jraKettoNum: string): CheckUmaEntry | null {
  const entries = readCheckUmaList();
  return entries.find(e => e.horseId === jraKettoNum) ?? null;
}

/**
 * 複数馬のチェック状態を一括取得 (JRA-VAN kettoNum で検索)
 */
export function getCheckUmaMap(jraKettoNums: string[]): Map<string, CheckUmaEntry> {
  const entries = readCheckUmaList();
  const idSet = new Set(jraKettoNums);
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
 * 入力: JRA-VAN kettoNum。ファイルには TARGET 形式で書き込む。
 */
export function addCheckUma(
  jraKettoNum: string,
  level: number = 0,
  comment: string = ''
): boolean {
  try {
    const entries = readCheckUmaList();
    const now = new Date();
    const month = now.getMonth() + 1;
    const day = now.getDate();

    // 既存エントリを JRA-VAN で検索
    const existing = entries.find(e => e.horseId === jraKettoNum);
    const rawHorseId = existing?.rawHorseId ?? jraToTarget(jraKettoNum, now.getFullYear());

    // 既存エントリを除外
    const filtered = entries.filter(e => e.horseId !== jraKettoNum);
    filtered.push({
      horseId: jraKettoNum,
      rawHorseId,
      month,
      day,
      level,
      comment,
    });

    // levelでソート → rawHorseId でソート（TARGET と同じ並び順）
    filtered.sort((a, b) => {
      if (a.level !== b.level) return a.level - b.level;
      return a.rawHorseId.localeCompare(b.rawHorseId);
    });

    writeCheckUmaList(filtered);
    return true;
  } catch (error) {
    console.error('[CheckUma] Add error:', error);
    return false;
  }
}

/**
 * チェック馬を削除 (JRA-VAN kettoNum で指定)
 */
export function removeCheckUma(jraKettoNum: string): boolean {
  try {
    const entries = readCheckUmaList();
    const filtered = entries.filter(e => e.horseId !== jraKettoNum);
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
 * rawHorseId (TARGET形式) を使う
 */
function writeCheckUmaList(entries: CheckUmaEntry[]): void {
  const lines: Buffer[] = [];

  for (const e of entries) {
    const mmdd = String(e.month).padStart(2, '0') + String(e.day).padStart(2, '0');
    const levelStr = String(Math.min(9, Math.max(0, e.level)));
    const asciiPart = Buffer.from(`${e.rawHorseId}${mmdd}${levelStr}`, 'ascii');

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
