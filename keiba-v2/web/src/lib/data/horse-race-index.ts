/**
 * 馬→レースマッピングインデックス
 * 
 * 馬IDから該当レースのファイルパスを高速に検索するためのインデックス
 * JSONファイルに永続化してアプリ再起動時も高速検索を維持
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// データルートディレクトリ
const RACES_DIR = path.join(DATA3_ROOT, 'races');
const INDEX_FILE = path.join(DATA3_ROOT, 'indexes', 'horse_race_index.json');
const INDEX_META_FILE = path.join(DATA3_ROOT, 'indexes', 'horse_race_index_meta.json');

// インメモリキャッシュ
let horseRaceIndex: Map<string, string[]> = new Map();
let indexLoaded = false;
let indexBuildInProgress = false;

interface IndexMeta {
  builtAt: string;
  raceCount: number;
  horseCount: number;
  lastScanDate: string;
}

/**
 * インデックスをファイルから読み込み
 */
function loadIndexFromFile(): boolean {
  try {
    if (!fs.existsSync(INDEX_FILE)) {
      return false;
    }

    const data = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf-8'));
    horseRaceIndex = new Map(Object.entries(data));
    indexLoaded = true;
    
    // メタ情報を読み込み
    if (fs.existsSync(INDEX_META_FILE)) {
      const meta: IndexMeta = JSON.parse(fs.readFileSync(INDEX_META_FILE, 'utf-8'));
      console.log(`[HorseRaceIndex] Loaded from file: ${meta.horseCount} horses, ${meta.raceCount} races (built: ${meta.builtAt})`);
    }
    
    return true;
  } catch (error) {
    console.error('[HorseRaceIndex] Failed to load index:', error);
    return false;
  }
}

/**
 * インデックスをファイルに保存
 */
function saveIndexToFile(raceCount: number): void {
  try {
    // キャッシュディレクトリを確保
    const cacheDir = path.dirname(INDEX_FILE);
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }

    // インデックスデータを保存
    const data = Object.fromEntries(horseRaceIndex);
    fs.writeFileSync(INDEX_FILE, JSON.stringify(data), 'utf-8');

    // メタ情報を保存
    const meta: IndexMeta = {
      builtAt: new Date().toISOString(),
      raceCount,
      horseCount: horseRaceIndex.size,
      lastScanDate: new Date().toISOString().split('T')[0],
    };
    fs.writeFileSync(INDEX_META_FILE, JSON.stringify(meta, null, 2), 'utf-8');

    console.log(`[HorseRaceIndex] Saved to file: ${meta.horseCount} horses, ${raceCount} races`);
  } catch (error) {
    console.error('[HorseRaceIndex] Failed to save index:', error);
  }
}

/**
 * インデックスを構築
 */
export async function buildHorseRaceIndex(): Promise<void> {
  if (indexBuildInProgress) {
    console.log('[HorseRaceIndex] Build already in progress, skipping');
    return;
  }

  // 既存のインデックスがあれば読み込み
  if (!indexLoaded && loadIndexFromFile()) {
    return;
  }

  indexBuildInProgress = true;
  const startTime = Date.now();
  let raceCount = 0;

  try {
    if (!fs.existsSync(RACES_DIR)) {
      console.log('[HorseRaceIndex] Races directory not found');
      return;
    }

    // 年ディレクトリを走査（最新3年分）
    const years = fs.readdirSync(RACES_DIR)
      .filter(d => /^\d{4}$/.test(d))
      .sort((a, b) => parseInt(b) - parseInt(a))
      .slice(0, 3);

    for (const year of years) {
      const yearPath = path.join(RACES_DIR, year);
      if (!fs.existsSync(yearPath)) continue;

      const months = fs.readdirSync(yearPath)
        .filter(d => /^\d{2}$/.test(d))
        .sort((a, b) => parseInt(b) - parseInt(a));

      for (const month of months) {
        const monthPath = path.join(yearPath, month);
        if (!fs.existsSync(monthPath)) continue;

        const days = fs.readdirSync(monthPath)
          .filter(d => /^\d{2}$/.test(d));

        for (const day of days) {
          const dayDir = path.join(monthPath, day);

          // v4 race JSONを検索
          let raceFiles: string[];
          try {
            raceFiles = fs.readdirSync(dayDir)
              .filter(f => f.startsWith('race_') && f.endsWith('.json'));
          } catch { continue; }

          for (const file of raceFiles) {
            try {
              const filePath = path.join(dayDir, file);
              const content = fs.readFileSync(filePath, 'utf-8');
              const data = JSON.parse(content);

              raceCount++;

              // entriesから馬ID(ketto_num)を抽出
              for (const entry of data.entries || []) {
                const horseId = String(entry.ketto_num || entry.horse_id || '');
                if (!horseId) continue;

                if (!horseRaceIndex.has(horseId)) {
                  horseRaceIndex.set(horseId, []);
                }
                horseRaceIndex.get(horseId)!.push(filePath);
              }
            } catch {
              // ファイル読み込みエラーは無視
            }
          }
        }
      }
    }

    indexLoaded = true;
    
    // ファイルに保存
    saveIndexToFile(raceCount);

    const elapsed = Date.now() - startTime;
    console.log(`[HorseRaceIndex] Built: ${horseRaceIndex.size} horses, ${raceCount} races in ${elapsed}ms`);
  } catch (error) {
    console.error('[HorseRaceIndex] Build error:', error);
  } finally {
    indexBuildInProgress = false;
  }
}

/**
 * 馬IDからレースファイルパス一覧を取得
 */
export function getRaceFilesForHorse(horseId: string): string[] {
  // インデックスが未ロードなら読み込み試行
  if (!indexLoaded) {
    loadIndexFromFile();
  }

  return horseRaceIndex.get(horseId) || [];
}

/**
 * インデックスが利用可能かチェック
 */
export function isIndexAvailable(): boolean {
  if (!indexLoaded) {
    loadIndexFromFile();
  }
  return indexLoaded && horseRaceIndex.size > 0;
}

/**
 * インデックスをクリア（再構築用）
 */
export function clearIndex(): void {
  horseRaceIndex.clear();
  indexLoaded = false;
  
  try {
    if (fs.existsSync(INDEX_FILE)) {
      fs.unlinkSync(INDEX_FILE);
    }
    if (fs.existsSync(INDEX_META_FILE)) {
      fs.unlinkSync(INDEX_META_FILE);
    }
  } catch (e) {
    // ignore
  }
}
