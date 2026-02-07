/**
 * レース日付インデックス
 * 
 * 利用可能な日付と各日の競馬場・レース情報を高速に取得するためのインデックス
 * JSONファイルに永続化してアプリ再起動時も高速検索を維持
 */

import fs from 'fs';
import path from 'path';
import { PATHS, TRACKS, DATA_ROOT } from '../config';

const INDEX_FILE = path.join(DATA_ROOT, 'cache', 'race_date_index.json');
const INDEX_META_FILE = path.join(DATA_ROOT, 'cache', 'race_date_index_meta.json');

// インメモリキャッシュ
let dateIndex: Map<string, DateIndexEntry> = new Map();
let availableDates: string[] = [];
let indexLoaded = false;
let indexBuildInProgress = false;

interface DateIndexEntry {
  date: string;
  displayDate: string;
  tracks: TrackIndexEntry[];
}

interface TrackIndexEntry {
  track: string;
  races: RaceIndexEntry[];
}

interface RaceIndexEntry {
  id: string;
  raceNumber: number;
  raceName: string;
  className: string;
  distance: string;
  startTime: string;
  kai?: number;
  nichi?: number;
  // ペース分析情報（レース結果から取得）
  paceType?: 'sprint' | 'average' | 'stamina';  // 瞬発/平均/持続
  winnerFirst3f?: number;  // 勝ち馬の前半3F
  winnerLast3f?: number;   // 勝ち馬の後半3F
  paceDiff?: number;       // 前半-後半の差（マイナス=瞬発戦）
  rpci?: number;           // RPCI値 (前半3F/後半3F)*50
}

// ペース分類タイプをエクスポート
export type PaceType = 'sprint' | 'average' | 'stamina';

/** インデックス形式バージョン。2=race_info.jsonのみ対応、3=ペース分析情報追加、4=RPCI比率方式に統一 */
const INDEX_VERSION = 4;

interface IndexMeta {
  builtAt: string;
  dateCount: number;
  raceCount: number;
  version?: number;
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
    dateIndex = new Map(Object.entries(data).map(([k, v]) => [k, v as DateIndexEntry]));
    availableDates = Array.from(dateIndex.keys()).sort().reverse();

    if (fs.existsSync(INDEX_META_FILE)) {
      const meta: IndexMeta = JSON.parse(fs.readFileSync(INDEX_META_FILE, 'utf-8'));
      if ((meta.version ?? 1) < INDEX_VERSION) {
        console.log(`[RaceDateIndex] Cache version ${meta.version ?? 1} < ${INDEX_VERSION}, will rebuild (race_info-only support)`);
        dateIndex = new Map();
        availableDates = [];
        return false;
      }
      console.log(`[RaceDateIndex] Loaded from file: ${meta.dateCount} dates, ${meta.raceCount} races (built: ${meta.builtAt})`);
    }
    indexLoaded = true;
    return true;
  } catch (error) {
    console.error('[RaceDateIndex] Failed to load index:', error);
    return false;
  }
}

/**
 * インデックスをファイルに保存
 */
function saveIndexToFile(raceCount: number): void {
  try {
    const cacheDir = path.dirname(INDEX_FILE);
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }

    const data = Object.fromEntries(dateIndex);
    fs.writeFileSync(INDEX_FILE, JSON.stringify(data), 'utf-8');

    const meta: IndexMeta = {
      builtAt: new Date().toISOString(),
      dateCount: dateIndex.size,
      raceCount,
      version: INDEX_VERSION,
    };
    fs.writeFileSync(INDEX_META_FILE, JSON.stringify(meta, null, 2), 'utf-8');

    console.log(`[RaceDateIndex] Saved to file: ${meta.dateCount} dates, ${raceCount} races`);
  } catch (error) {
    console.error('[RaceDateIndex] Failed to save index:', error);
  }
}

/**
 * race_info.jsonからレース情報を読み込み
 */
function loadRaceInfoFromJson(dayPath: string): Map<string, RaceIndexEntry> {
  const raceMap = new Map<string, RaceIndexEntry>();
  const raceInfoPath = path.join(dayPath, 'race_info.json');

  if (!fs.existsSync(raceInfoPath)) {
    return raceMap;
  }

  try {
    const content = fs.readFileSync(raceInfoPath, 'utf-8');
    const data = JSON.parse(content) as {
      kaisai_data?: Record<string, Array<{
        race_id?: string;
        race_no?: string;
        race_name?: string;
        course?: string;
        start_time?: string;
      }>>;
    };

    const kaisaiData = data.kaisai_data || {};
    for (const [kaisaiKey, raceList] of Object.entries(kaisaiData)) {
      const kaisaiInfo = parseKaisaiKey(kaisaiKey);
      
      for (const race of raceList) {
        if (!race.race_id) continue;
        
        const raceNumber = parseInt(race.race_no || '0', 10);
        
        // ペース情報を取得
        const paceInfo = extractPaceInfo(dayPath, race.race_id);
        
        raceMap.set(race.race_id, {
          id: race.race_id,
          raceNumber,
          raceName: race.race_name || `${raceNumber}R`,
          className: extractClassName(race.race_name || ''),
          distance: race.course || '',
          startTime: race.start_time || '',
          kai: kaisaiInfo?.kai,
          nichi: kaisaiInfo?.nichi,
          ...paceInfo,  // ペース情報を追加
        });
      }
    }
  } catch (e) {
    // ignore
  }

  return raceMap;
}

function parseKaisaiKey(raw: string): { kai: number; track: string; nichi: number } | null {
  const match = raw.match(/(\d+)回([^\d]+)(\d+)日/);
  if (!match) return null;
  return {
    kai: parseInt(match[1], 10),
    track: match[2],
    nichi: parseInt(match[3], 10),
  };
}

function extractClassName(raceName: string): string {
  const classPatterns = [
    /G[123]/,
    /オープン/,
    /3勝クラス/,
    /2勝クラス/,
    /1勝クラス/,
    /未勝利/,
    /新馬/,
  ];
  
  for (const pattern of classPatterns) {
    const match = raceName.match(pattern);
    if (match) return match[0];
  }
  
  return '';
}

/**
 * レース結果からペース情報を取得
 * @param dayPath 日付ディレクトリのパス
 * @param raceId レースID
 */
function extractPaceInfo(dayPath: string, raceId: string): {
  paceType?: PaceType;
  winnerFirst3f?: number;
  winnerLast3f?: number;
  paceDiff?: number;
  rpci?: number;
} {
  const tempPath = path.join(dayPath, 'temp');
  
  // integrated_*.json を優先的に読み込み
  const integratedPath = path.join(tempPath, `integrated_${raceId}.json`);
  const seisekiPath = path.join(tempPath, `seiseki_${raceId}.json`);
  
  let filePath = '';
  if (fs.existsSync(integratedPath)) {
    filePath = integratedPath;
  } else if (fs.existsSync(seisekiPath)) {
    filePath = seisekiPath;
  }
  
  if (!filePath) return {};
  
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);
    
    // 勝ち馬（1着馬）を探す
    const entries = data.entries || [];
    let winnerEntry = null;
    
    for (const entry of entries) {
      const result = entry.result || {};
      const finishPos = result.finish_position || result.raw_data?.着順;
      if (finishPos === '1' || finishPos === 1) {
        winnerEntry = entry;
        break;
      }
    }
    
    if (!winnerEntry) return {};
    
    const result = winnerEntry.result || {};
    const rawData = result.raw_data || {};
    
    // 前半3F・後半3Fを取得
    const first3fStr = result.first_3f || rawData['前半3F'] || rawData.前半3F || '';
    const last3fStr = result.last_3f || rawData['上り3F'] || rawData.上り3F || rawData.上がり || '';
    
    const first3f = parseFloat(first3fStr);
    const last3f = parseFloat(last3fStr);
    
    if (isNaN(first3f) || isNaN(last3f)) return {};
    
    // ペース差（参考値として保持）
    const paceDiff = Math.round((first3f - last3f) * 10) / 10;

    // RPCI = (前半3F / 後半3F) × 50
    // >50: スロー（瞬発戦）、<50: ハイ（持続戦）
    const rpci = Math.round(((first3f / last3f) * 50) * 10) / 10;

    // ペース分類（RPCI閾値で判定 - rpci-utils.tsと統一）
    let paceType: PaceType;
    if (rpci >= 51) {
      paceType = 'sprint';    // 瞬発戦（スローペース）
    } else if (rpci <= 48) {
      paceType = 'stamina';   // 持続戦（ハイペース）
    } else {
      paceType = 'average';   // 平均ペース
    }

    return {
      paceType,
      winnerFirst3f: first3f,
      winnerLast3f: last3f,
      paceDiff,
      rpci,
    };
  } catch {
    return {};
  }
}

/**
 * 競馬場フォルダ・MDがなくても race_info.json のみで日付をインデックス化する
 */
function buildDateIndexFromRaceInfoOnly(
  dayPath: string,
  year: string,
  month: string,
  day: string
): { entry: DateIndexEntry; raceCount: number } | null {
  const raceInfoPath = path.join(dayPath, 'race_info.json');
  if (!fs.existsSync(raceInfoPath)) return null;

  try {
    const content = fs.readFileSync(raceInfoPath, 'utf-8');
    const data = JSON.parse(content) as {
      kaisai_data?: Record<string, Array<{
        race_id?: string;
        race_no?: string;
        race_name?: string;
        course?: string;
        start_time?: string;
      }>>;
    };
    const kaisaiData = data.kaisai_data || {};
    if (Object.keys(kaisaiData).length === 0) return null;

    const trackMap = new Map<string, RaceIndexEntry[]>();

    for (const [kaisaiKey, raceList] of Object.entries(kaisaiData)) {
      const kaisaiInfo = parseKaisaiKey(kaisaiKey);
      if (!kaisaiInfo || !(TRACKS as readonly string[]).includes(kaisaiInfo.track)) continue;
      const track = kaisaiInfo.track;
      if (!trackMap.has(track)) trackMap.set(track, []);
      for (const race of raceList) {
        if (!race.race_id) continue;
        const raceNumber = parseInt(race.race_no || '0', 10);
        
        // ペース情報を取得
        const paceInfo = extractPaceInfo(dayPath, race.race_id);
        
        trackMap.get(track)!.push({
          id: race.race_id,
          raceNumber,
          raceName: race.race_name || `${raceNumber}R`,
          className: extractClassName(race.race_name || ''),
          distance: race.course || '',
          startTime: race.start_time || '',
          kai: kaisaiInfo.kai,
          nichi: kaisaiInfo.nichi,
          ...paceInfo,  // ペース情報を追加
        });
      }
    }
    if (trackMap.size === 0) return null;

    const trackEntries: TrackIndexEntry[] = [];
    let raceCount = 0;
    for (const [track, races] of trackMap) {
      races.sort((a, b) => a.raceNumber - b.raceNumber);
      trackEntries.push({ track, races });
      raceCount += races.length;
    }
    trackEntries.sort((a, b) => {
      const indexA = TRACKS.indexOf(a.track as (typeof TRACKS)[number]);
      const indexB = TRACKS.indexOf(b.track as (typeof TRACKS)[number]);
      return indexA - indexB;
    });

    const dateStr = `${year}-${month}-${day}`;
    const displayDate = `${year}年${parseInt(month)}月${parseInt(day)}日`;
    return {
      entry: { date: dateStr, displayDate, tracks: trackEntries },
      raceCount,
    };
  } catch {
    return null;
  }
}

/**
 * インデックスを構築
 */
export async function buildRaceDateIndex(): Promise<void> {
  if (indexBuildInProgress) {
    console.log('[RaceDateIndex] Build already in progress, skipping');
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
    const racesPath = PATHS.races;
    if (!fs.existsSync(racesPath)) {
      console.log('[RaceDateIndex] Races directory not found');
      return;
    }

    const years = fs.readdirSync(racesPath)
      .filter(f => /^\d{4}$/.test(f))
      .sort((a, b) => parseInt(b) - parseInt(a));

    for (const year of years) {
      const yearPath = path.join(racesPath, year);
      const months = fs.readdirSync(yearPath)
        .filter(f => /^\d{2}$/.test(f));

      for (const month of months) {
        const monthPath = path.join(yearPath, month);
        const days = fs.readdirSync(monthPath)
          .filter(f => /^\d{2}$/.test(f));

        for (const day of days) {
          const dayPath = path.join(monthPath, day);
          const dateStr = `${year}-${month}-${day}`;
          
          // race_info.jsonからレース情報を読み込み
          const raceInfo = loadRaceInfoFromJson(dayPath);
          
          // 競馬場フォルダを取得
          let trackDirs: string[] = [];
          try {
            trackDirs = fs.readdirSync(dayPath).filter(f => {
              const trackPath = path.join(dayPath, f);
              return fs.statSync(trackPath).isDirectory() && (TRACKS as readonly string[]).includes(f);
            });
          } catch {
            // 読めない日付フォルダはスキップ
            continue;
          }

          if (trackDirs.length === 0) {
            // MD出走表（競馬場フォルダ内の .md）が無くても race_info.json のみで「データあり」とする
            const fromRaceInfo = buildDateIndexFromRaceInfoOnly(dayPath, year, month, day);
            if (fromRaceInfo) {
              dateIndex.set(fromRaceInfo.entry.date, fromRaceInfo.entry);
              raceCount += fromRaceInfo.raceCount;
            }
            continue;
          }

          const trackEntries: TrackIndexEntry[] = [];

          for (const track of trackDirs) {
            const trackPath = path.join(dayPath, track);
            // MD出走表（.md）の有無でレースを列挙。無い場合は race_info.json の情報のみ使用
            const mdFiles = fs.readdirSync(trackPath)
              .filter(f => f.endsWith('.md'));

            const raceEntries: RaceIndexEntry[] = [];

            for (const file of mdFiles) {
              const raceId = file.replace('.md', '');
              const raceNumber = parseInt(raceId.slice(-2), 10);
              
              // race_info.jsonの情報を優先
              const infoFromJson = raceInfo.get(raceId);
              
              if (infoFromJson) {
                raceEntries.push(infoFromJson);
              } else {
                // race_info.jsonにない場合はMDファイルから抽出
                const filePath = path.join(trackPath, file);
                const content = fs.readFileSync(filePath, 'utf-8');
                const entry = parseRaceFromMd(content, raceId, raceNumber);
                raceEntries.push(entry);
              }
              raceCount++;
            }

            raceEntries.sort((a, b) => a.raceNumber - b.raceNumber);
            trackEntries.push({ track, races: raceEntries });
          }

          // TRACKS配列の順序でソート
          trackEntries.sort((a, b) => {
            const indexA = TRACKS.indexOf(a.track as any);
            const indexB = TRACKS.indexOf(b.track as any);
            return indexA - indexB;
          });

          const displayDate = `${year}年${parseInt(month)}月${parseInt(day)}日`;
          dateIndex.set(dateStr, {
            date: dateStr,
            displayDate,
            tracks: trackEntries,
          });
        }
      }
    }

    availableDates = Array.from(dateIndex.keys()).sort().reverse();
    indexLoaded = true;
    
    saveIndexToFile(raceCount);

    const elapsed = Date.now() - startTime;
    console.log(`[RaceDateIndex] Built: ${dateIndex.size} dates, ${raceCount} races in ${elapsed}ms`);
  } catch (error) {
    console.error('[RaceDateIndex] Build error:', error);
  } finally {
    indexBuildInProgress = false;
  }
}

function parseRaceFromMd(content: string, raceId: string, raceNumber: number): RaceIndexEntry {
  // タイトル行からレース名を抽出
  const titleMatch = content.match(/^# (.+)$/m);
  let raceName = `${raceNumber}R`;
  let className = '';
  
  if (titleMatch) {
    const titleLine = titleMatch[1];
    const raceMatch = titleLine.match(/\d+R\s*(?:\(([^)]+)\))?\s*(.+)?/);
    if (raceMatch) {
      className = raceMatch[1] || '';
      raceName = raceMatch[2] || `${raceNumber}R`;
    }
  }

  // 距離を抽出
  const distanceMatch = content.match(/競馬場[:\s]*\S+\s+([\S]+)/);
  const distance = distanceMatch ? distanceMatch[1] : '';

  // 発走時刻を抽出
  const timeMatch = content.match(/発走予定\**[:\s]*(\d{1,2}:\d{2})/);
  const startTime = timeMatch ? timeMatch[1] : '';

  return {
    id: raceId,
    raceNumber,
    raceName,
    className,
    distance,
    startTime,
  };
}

/**
 * 利用可能な日付一覧を取得（高速）
 */
export function getAvailableDatesFromIndex(): string[] {
  if (!indexLoaded) {
    loadIndexFromFile();
  }
  return availableDates;
}

/**
 * 指定日のレース一覧を取得（高速）
 */
export function getRacesByDateFromIndex(date: string): DateIndexEntry | null {
  if (!indexLoaded) {
    loadIndexFromFile();
  }
  return dateIndex.get(date) || null;
}

/**
 * インデックスが利用可能かチェック
 */
export function isRaceIndexAvailable(): boolean {
  if (!indexLoaded) {
    loadIndexFromFile();
  }
  return indexLoaded && dateIndex.size > 0;
}

/**
 * インデックスをクリア（再構築用）
 */
export function clearRaceDateIndex(): void {
  dateIndex.clear();
  availableDates = [];
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
