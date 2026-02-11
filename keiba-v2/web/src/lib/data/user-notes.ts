/**
 * ユーザーメモ管理
 * レースメモ・馬メモを別ファイルで管理
 */

import fs from 'fs';
import path from 'path';
import { PATHS } from '../config';

// メモ保存先ディレクトリ
const NOTES_DIR = path.join(PATHS.races, '..', 'user_notes');

/**
 * レースメモの型定義
 */
export interface RaceNotes {
  raceMemo?: string; // レース全体のメモ
  horses?: Record<string, string>; // 馬番 → メモ
  updatedAt?: string; // 最終更新日時
}

/**
 * 日付別のメモファイルの型定義
 */
export interface DateNotes {
  [raceId: string]: RaceNotes;
}

/**
 * メモ保存ディレクトリを確保
 */
function ensureNotesDir(): void {
  if (!fs.existsSync(NOTES_DIR)) {
    fs.mkdirSync(NOTES_DIR, { recursive: true });
  }
}

/**
 * メモファイルのパスを取得
 */
function getNotesFilePath(date: string): string {
  return path.join(NOTES_DIR, `${date}.json`);
}

/**
 * 日付のメモを全て読み込み
 */
export async function getDateNotes(date: string): Promise<DateNotes> {
  const filePath = getNotesFilePath(date);

  if (!fs.existsSync(filePath)) {
    return {};
  }

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content) as DateNotes;
  } catch (error) {
    console.error(`Error reading notes for ${date}:`, error);
    return {};
  }
}

/**
 * 特定レースのメモを取得
 */
export async function getRaceNotes(date: string, raceId: string): Promise<RaceNotes> {
  const dateNotes = await getDateNotes(date);
  return dateNotes[raceId] || {};
}

/**
 * 特定レースのメモを保存
 */
export async function saveRaceNotes(
  date: string,
  raceId: string,
  notes: RaceNotes
): Promise<void> {
  ensureNotesDir();

  const dateNotes = await getDateNotes(date);
  
  // 更新日時を追加
  notes.updatedAt = new Date().toISOString();
  
  // マージして保存
  dateNotes[raceId] = {
    ...dateNotes[raceId],
    ...notes,
  };

  const filePath = getNotesFilePath(date);
  fs.writeFileSync(filePath, JSON.stringify(dateNotes, null, 2), 'utf-8');
}

/**
 * レースメモのみを更新
 */
export async function updateRaceMemo(
  date: string,
  raceId: string,
  memo: string
): Promise<void> {
  const currentNotes = await getRaceNotes(date, raceId);
  await saveRaceNotes(date, raceId, {
    ...currentNotes,
    raceMemo: memo,
  });
}

/**
 * 馬メモを更新
 */
export async function updateHorseMemo(
  date: string,
  raceId: string,
  horseNumber: string,
  memo: string
): Promise<void> {
  const currentNotes = await getRaceNotes(date, raceId);
  const horses = currentNotes.horses || {};
  
  if (memo.trim() === '') {
    // 空の場合は削除
    delete horses[horseNumber];
  } else {
    horses[horseNumber] = memo;
  }
  
  await saveRaceNotes(date, raceId, {
    ...currentNotes,
    horses,
  });
}

/**
 * 馬メモを取得
 */
export async function getHorseMemo(
  date: string,
  raceId: string,
  horseNumber: string
): Promise<string> {
  const notes = await getRaceNotes(date, raceId);
  return notes.horses?.[horseNumber] || '';
}
