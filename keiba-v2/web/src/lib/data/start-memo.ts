/**
 * スタートメモ管理ライブラリ
 * レースごとの馬のスタート評価を保存・取得
 * 
 * 保存先: data3/userdata/start-memos.json
 */

import fs from 'fs/promises';
import path from 'path';
import { AI_DATA_PATH } from '@/lib/config';

// スタートメモのプリセットラベル
export const START_MEMO_PRESETS = [
  '押してハナ',
  'スタート◎',
  'スタート〇',
  'スタート△',
  '二の足で先団',
  '出遅れ',
  'ダッシュ◎',
  'ダッシュ〇',
  'ダッシュ△',
] as const;

export type StartMemoPreset = typeof START_MEMO_PRESETS[number];

export interface StartMemoEntry {
  horseNumber: number;
  horseName: string;
  memo: string;           // メモ内容（プリセットまたは自由入力）
  updatedAt: string;      // 更新日時
}

export interface RaceStartMemo {
  raceId: string;
  raceDate: string;
  raceName?: string;
  entries: StartMemoEntry[];
  createdAt: string;
  updatedAt: string;
}

// データ保存ディレクトリ（data3/userdata）
const DATA_DIR = AI_DATA_PATH;
const START_MEMO_FILE = path.join(DATA_DIR, 'start-memos.json');

// 全スタートメモデータ
interface StartMemoData {
  version: string;
  races: Record<string, RaceStartMemo>;
}

/**
 * データファイルの初期化
 */
async function ensureDataFile(): Promise<void> {
  try {
    await fs.mkdir(DATA_DIR, { recursive: true });
    try {
      await fs.access(START_MEMO_FILE);
    } catch {
      // ファイルが存在しない場合は初期化
      const initialData: StartMemoData = {
        version: '1.0',
        races: {},
      };
      await fs.writeFile(START_MEMO_FILE, JSON.stringify(initialData, null, 2), 'utf-8');
    }
  } catch (error) {
    console.error('Failed to ensure data file:', error);
  }
}

/**
 * 全データを読み込み
 */
async function loadData(): Promise<StartMemoData> {
  await ensureDataFile();
  try {
    const content = await fs.readFile(START_MEMO_FILE, 'utf-8');
    return JSON.parse(content);
  } catch {
    return { version: '1.0', races: {} };
  }
}

/**
 * 全データを保存
 */
async function saveData(data: StartMemoData): Promise<void> {
  await ensureDataFile();
  await fs.writeFile(START_MEMO_FILE, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * レースのスタートメモを取得
 */
export async function getRaceStartMemos(raceId: string): Promise<RaceStartMemo | null> {
  const data = await loadData();
  return data.races[raceId] || null;
}

/**
 * 馬のスタートメモを取得
 */
export async function getHorseStartMemo(raceId: string, horseNumber: number): Promise<StartMemoEntry | null> {
  const raceMemo = await getRaceStartMemos(raceId);
  if (!raceMemo) return null;
  return raceMemo.entries.find(e => e.horseNumber === horseNumber) || null;
}

/**
 * 馬のスタートメモを更新
 */
export async function updateHorseStartMemo(
  raceId: string,
  raceDate: string,
  raceName: string | undefined,
  horseNumber: number,
  horseName: string,
  memo: string
): Promise<boolean> {
  try {
    const data = await loadData();
    const now = new Date().toISOString();

    // レースのメモデータがなければ作成
    if (!data.races[raceId]) {
      data.races[raceId] = {
        raceId,
        raceDate,
        raceName,
        entries: [],
        createdAt: now,
        updatedAt: now,
      };
    }

    const raceMemo = data.races[raceId];
    raceMemo.updatedAt = now;

    // 既存のエントリを探す
    const existingIndex = raceMemo.entries.findIndex(e => e.horseNumber === horseNumber);
    
    const entry: StartMemoEntry = {
      horseNumber,
      horseName,
      memo,
      updatedAt: now,
    };

    if (existingIndex >= 0) {
      raceMemo.entries[existingIndex] = entry;
    } else {
      raceMemo.entries.push(entry);
    }

    await saveData(data);
    return true;
  } catch (error) {
    console.error('Failed to update start memo:', error);
    return false;
  }
}

/**
 * 馬のスタートメモを削除
 */
export async function deleteHorseStartMemo(raceId: string, horseNumber: number): Promise<boolean> {
  try {
    const data = await loadData();
    
    if (!data.races[raceId]) return true;

    const raceMemo = data.races[raceId];
    raceMemo.entries = raceMemo.entries.filter(e => e.horseNumber !== horseNumber);
    raceMemo.updatedAt = new Date().toISOString();

    // エントリがなくなったらレースデータも削除
    if (raceMemo.entries.length === 0) {
      delete data.races[raceId];
    }

    await saveData(data);
    return true;
  } catch (error) {
    console.error('Failed to delete start memo:', error);
    return false;
  }
}

/**
 * 全レースのスタートメモを取得（統計用）
 */
export async function getAllStartMemos(): Promise<StartMemoData> {
  return await loadData();
}
