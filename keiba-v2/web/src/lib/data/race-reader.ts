import fs from 'fs';
import path from 'path';
import { remark } from 'remark';
import html from 'remark-html';
import gfm from 'remark-gfm';
import { PATHS, TRACKS } from '../config';
import type { RaceSummary, RaceDetail, DateGroup, TrackGroup } from '@/types';
import { 
  getAvailableDatesFromIndex, 
  getRacesByDateFromIndex, 
  isRaceIndexAvailable 
} from './race-date-index';

/**
 * 利用可能な日付一覧を取得
 * インデックスが利用可能な場合は高速取得
 */
export async function getAvailableDates(): Promise<string[]> {
  // インデックスが利用可能ならそれを使用（高速）
  if (isRaceIndexAvailable()) {
    return getAvailableDatesFromIndex();
  }

  // フォールバック: ディレクトリ走査
  const dates: string[] = [];
  const racesPath = PATHS.races;

  if (!fs.existsSync(racesPath)) {
    return dates;
  }

  const years = fs.readdirSync(racesPath).filter((f) => /^\d{4}$/.test(f));

  for (const year of years) {
    const yearPath = path.join(racesPath, year);
    const months = fs.readdirSync(yearPath).filter((f) => /^\d{2}$/.test(f));

    for (const month of months) {
      const monthPath = path.join(yearPath, month);
      const days = fs.readdirSync(monthPath).filter((f) => /^\d{2}$/.test(f));

      for (const day of days) {
        const dayPath = path.join(monthPath, day);
        let tracks: string[] = [];
        try {
          tracks = fs.readdirSync(dayPath).filter((f) => {
            const trackPath = path.join(dayPath, f);
            return fs.statSync(trackPath).isDirectory() && (TRACKS as readonly string[]).includes(f);
          });
        } catch {
          continue;
        }
        // 競馬場フォルダ＋MD出走表(.md) または race_info.json のみの日も「データあり」
        if (tracks.length > 0 || hasRaceInfoWithKaisai(dayPath)) {
          dates.push(`${year}-${month}-${day}`);
        }
      }
    }
  }

  return dates.sort().reverse();
}

/**
 * 指定日のレース一覧を取得
 * インデックスが利用可能な場合は高速取得
 */
export async function getRacesByDate(date: string): Promise<DateGroup | null> {
  // インデックスが利用可能ならそれを使用（高速）
  if (isRaceIndexAvailable()) {
    const indexed = getRacesByDateFromIndex(date);
    if (indexed) {
      // NOTE:
      // インデックスは永続化されるため、race_info.json 更新後に内容が古くなることがある。
      // 特に kai/nichi（= JRAレーシングビュアー用）や startTime がズレると、
      // レース一覧からのレーシングビュアーURLが「間違って見える」原因になる。
      // ここでは、日付単位で race_info.json を読み直してインデックス値を上書きする。
      const [year, month, day] = date.split('-');
      const dayPath = path.join(PATHS.races, year, month, day);
      const infoByRaceId = loadRaceInfoByRaceId(dayPath);

      // インデックスデータをRaceSummary形式に変換
      const trackGroups: TrackGroup[] = indexed.tracks.map(t => ({
        track: t.track,
        races: t.races.map((r) => {
          const info = infoByRaceId.get(r.id);
          return {
            id: r.id,
            date,
            track: t.track,
            raceNumber: r.raceNumber,
            raceName: r.raceName,
            className: r.className,
            distance: info?.course || r.distance,
            startTime: info?.startTime || r.startTime,
            kai: info?.kai ?? r.kai,
            nichi: info?.nichi ?? r.nichi,
            filePath: '',
            // ペース情報を追加
            paceType: r.paceType,
            winnerFirst3f: r.winnerFirst3f,
            winnerLast3f: r.winnerLast3f,
            paceDiff: r.paceDiff,
            rpci: r.rpci,
          };
        }),
      }));
      
      return {
        date,
        displayDate: indexed.displayDate,
        tracks: trackGroups,
      };
    }
  }

  // フォールバック: ファイル走査
  const [year, month, day] = date.split('-');
  const dayPath = path.join(PATHS.races, year, month, day);

  if (!fs.existsSync(dayPath)) {
    return null;
  }

  let trackDirs: string[] = [];
  try {
    trackDirs = fs.readdirSync(dayPath).filter((f) => {
      const trackPath = path.join(dayPath, f);
      return fs.statSync(trackPath).isDirectory() && (TRACKS as readonly string[]).includes(f);
    });
  } catch {
    return null;
  }

  // MD出走表(.md)が無くても race_info.json のみでレース一覧を返す
  if (trackDirs.length === 0) {
    return buildDateGroupFromRaceInfoOnly(dayPath, date);
  }

  const trackGroups: TrackGroup[] = [];
  const infoByRaceId = loadRaceInfoByRaceId(dayPath);
  for (const track of trackDirs) {
    const trackPath = path.join(dayPath, track);
    const mdFiles = fs.readdirSync(trackPath).filter((f) => f.endsWith('.md'));

    const races: RaceSummary[] = [];
    for (const file of mdFiles) {
      const filePath = path.join(trackPath, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const summary = parseRaceSummary(content, file, date, track, filePath);
      if (summary) {
        const info = infoByRaceId.get(summary.id);
        if (info?.course) {
          summary.distance = info.course;
        }
        if (info?.kai) {
          summary.kai = info.kai;
        }
        if (info?.nichi) {
          summary.nichi = info.nichi;
        }
        // race_info.jsonの発走時刻を優先
        if (info?.startTime) {
          summary.startTime = info.startTime;
        }
        races.push(summary);
      }
    }

    // レース番号順にソート
    races.sort((a, b) => a.raceNumber - b.raceNumber);

    if (races.length > 0) {
      trackGroups.push({ track, races });
    }
  }

  // 競馬場順にソート（TRACKS配列の順序）
  trackGroups.sort((a, b) => {
    const indexA = TRACKS.indexOf(a.track as any);
    const indexB = TRACKS.indexOf(b.track as any);
    return indexA - indexB;
  });

  const displayDate = `${year}年${parseInt(month)}月${parseInt(day)}日`;

  return {
    date,
    displayDate,
    tracks: trackGroups,
  };
}

/**
 * レースMDからサマリ情報を抽出
 */
function parseRaceSummary(
  content: string,
  filename: string,
  date: string,
  track: string,
  filePath: string
): RaceSummary | null {
  // ファイル名からレースIDを取得（例: 202601050701.md）
  const id = filename.replace('.md', '');
  const raceNumber = parseInt(id.slice(-2), 10);

  // タイトル行からレース名を抽出
  // 例: # 中山1R (未勝利) 3歳未勝利
  const titleMatch = content.match(/^# (.+)$/m);
  if (!titleMatch) return null;

  const titleLine = titleMatch[1];
  // 例: 中山1R (未勝利) 3歳未勝利
  const raceMatch = titleLine.match(/(\S+?)(\d+)R\s*(?:\(([^)]+)\))?\s*(.+)?/);

  let raceName = '';
  let className = '';
  if (raceMatch) {
    className = raceMatch[3] || '';
    raceName = raceMatch[4] || `${raceNumber}R`;
  } else {
    raceName = titleLine;
  }

  // 距離を抽出（例: ダ・1200m、芝1800m）
  const distanceMatch = content.match(/競馬場[:\s]*\S+\s+([\S]+)/);
  const distance = distanceMatch ? distanceMatch[1] : '';

  // 発走時刻を抽出（形式: `- **発走予定**: 09:50` または `発走予定: 09:50`）
  const timeMatch = content.match(/発走予定\**[:\s]*(\d{1,2}:\d{2})/);
  const startTime = timeMatch ? timeMatch[1] : '';

  return {
    id,
    date,
    track,
    raceNumber,
    raceName,
    className,
    distance,
    startTime,
    filePath,
  };
}

function loadRaceInfoByRaceId(dayPath: string): Map<string, { course?: string; kai?: number; nichi?: number; track?: string; startTime?: string }> {
  const infoMap = new Map<string, { course?: string; kai?: number; nichi?: number; track?: string; startTime?: string }>();
  const raceInfoPath = path.join(dayPath, 'race_info.json');

  if (!fs.existsSync(raceInfoPath)) {
    return infoMap;
  }

  try {
    const content = fs.readFileSync(raceInfoPath, 'utf-8');
    const data = JSON.parse(content) as {
      kaisai_data?: Record<string, Array<{ race_id?: string; course?: string; race_no?: string; start_time?: string }>>;
    };
    const kaisaiData = data.kaisai_data || {};
    for (const [kaisaiKey, raceList] of Object.entries(kaisaiData)) {
      const kaisaiInfo = parseKaisaiKey(kaisaiKey);
      for (const race of raceList) {
        if (!race.race_id) continue;
        infoMap.set(race.race_id, {
          course: race.course,
          kai: kaisaiInfo?.kai,
          nichi: kaisaiInfo?.nichi,
          track: kaisaiInfo?.track,
          startTime: race.start_time,
        });
      }
    }
  } catch {
    return infoMap;
  }

  return infoMap;
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

function extractClassNameFromRaceName(raceName: string): string {
  const patterns = [/G[123]/, /オープン/, /3勝クラス/, /2勝クラス/, /1勝クラス/, /未勝利/, /新馬/];
  for (const p of patterns) {
    const m = raceName.match(p);
    if (m) return m[0] as string;
  }
  return '';
}

function hasRaceInfoWithKaisai(dayPath: string): boolean {
  const p = path.join(dayPath, 'race_info.json');
  if (!fs.existsSync(p)) return false;
  try {
    const data = JSON.parse(fs.readFileSync(p, 'utf-8')) as { kaisai_data?: Record<string, unknown[]> };
    const k = data.kaisai_data && Object.keys(data.kaisai_data).length > 0;
    return !!k;
  } catch {
    return false;
  }
}

function buildDateGroupFromRaceInfoOnly(dayPath: string, date: string): DateGroup | null {
  const raceInfoPath = path.join(dayPath, 'race_info.json');
  if (!fs.existsSync(raceInfoPath)) return null;
  let data: { kaisai_data?: Record<string, Array<{ race_id?: string; race_no?: string; race_name?: string; course?: string; start_time?: string }>> };
  try {
    data = JSON.parse(fs.readFileSync(raceInfoPath, 'utf-8'));
  } catch {
    return null;
  }
  const kaisaiData = data.kaisai_data || {};
  if (Object.keys(kaisaiData).length === 0) return null;

  const trackMap = new Map<string, RaceSummary[]>();
  for (const [kaisaiKey, raceList] of Object.entries(kaisaiData)) {
    const kai = parseKaisaiKey(kaisaiKey);
    if (!kai || !(TRACKS as readonly string[]).includes(kai.track)) continue;
    const track = kai.track;
    if (!trackMap.has(track)) trackMap.set(track, []);
    for (const r of raceList) {
      if (!r.race_id) continue;
      const raceNumber = parseInt(r.race_no || '0', 10);
      trackMap.get(track)!.push({
        id: r.race_id,
        date,
        track,
        raceNumber,
        raceName: r.race_name || `${raceNumber}R`,
        className: extractClassNameFromRaceName(r.race_name || ''),
        distance: r.course || '',
        startTime: r.start_time || '',
        kai: kai.kai,
        nichi: kai.nichi,
        filePath: '',
      });
    }
  }
  if (trackMap.size === 0) return null;

  const tracks: TrackGroup[] = [];
  for (const [track, races] of trackMap) {
    races.sort((a, b) => a.raceNumber - b.raceNumber);
    tracks.push({ track, races });
  }
  tracks.sort((a, b) => {
    const iA = TRACKS.indexOf(a.track as (typeof TRACKS)[number]);
    const iB = TRACKS.indexOf(b.track as (typeof TRACKS)[number]);
    return iA - iB;
  });

  const [y, m, d] = date.split('-');
  const displayDate = `${y}年${parseInt(m)}月${parseInt(d)}日`;
  return { date, displayDate, tracks };
}

/**
 * レース詳細を取得
 */
export async function getRaceDetail(
  date: string,
  track: string,
  raceId: string
): Promise<RaceDetail | null> {
  const [year, month, day] = date.split('-');
  const filePath = path.join(PATHS.races, year, month, day, track, `${raceId}.md`);
  const infoByRaceId = loadRaceInfoByRaceId(path.join(PATHS.races, year, month, day));

  if (!fs.existsSync(filePath)) {
    return null;
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  const summary = parseRaceSummary(content, `${raceId}.md`, date, track, filePath);
  const info = infoByRaceId.get(raceId);
  if (summary && info?.course) {
    summary.distance = info.course;
  }

  if (!summary) return null;

  // ローカルパスをURLに変換
  const processedContent = convertLocalPaths(content);

  // MarkdownをHTMLに変換
  const result = await remark().use(gfm).use(html).process(processedContent);
  let htmlContent = result.toString();

  // 馬リンクを新規タブで開くように変換
  htmlContent = addTargetBlankToHorseLinks(htmlContent);

  return {
    ...summary,
    content,
    htmlContent,
    horses: [], // TODO: 出走馬情報を抽出
  };
}

/**
 * 馬リンクに target="_blank" を追加して新規タブで開くようにする
 */
function addTargetBlankToHorseLinks(html: string): string {
  // <a href="/horses/..."> を <a href="/horses/..." target="_blank" rel="noopener noreferrer"> に変換
  return html.replace(
    /<a href="(\/horses\/[^"]+)">/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">'
  );
}

/**
 * 開催情報キーから競馬場名を抽出
 * 例: "1回東京1日目" → "東京", "2回京都1日目" → "京都"
 */
function extractTrackFromKaisaiKey(kaisaiKey: string): string | null {
  for (const track of TRACKS) {
    if (kaisaiKey.includes(track)) {
      return track;
    }
  }
  return null;
}

/**
 * 同日の競馬場一覧とレース番号一覧を取得（ナビゲーション用）
 * 優先順位: 1. navigation_index.json 2. JSON (race_info/nittei) 3. MDファイル
 */
export async function getRaceNavigation(
  date: string,
  currentTrack: string,
  currentRaceNumber?: number
): Promise<{
  tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[];
  races: { raceNumber: number; raceId: string; raceName: string; startTime: string }[];
  allRacesByTime: { track: string; raceNumber: number; raceId: string; startTime: string }[];
  prevRace: { track: string; raceId: string } | null;
  nextRace: { track: string; raceId: string } | null;
} | null> {
  const [year, month, day] = date.split('-');
  const dayPath = path.join(PATHS.races, year, month, day);

  if (!fs.existsSync(dayPath)) {
    return null;
  }

  // 1. 事前生成されたインデックスを試す（最速）
  const indexResult = await getRaceNavigationFromIndex(date, currentTrack, currentRaceNumber, dayPath);
  if (indexResult) {
    return indexResult;
  }

  // 2. JSONからのナビゲーション構築を試行
  const jsonResult = await getRaceNavigationFromJson(date, currentTrack, currentRaceNumber, dayPath);
  if (jsonResult) {
    return jsonResult;
  }

  // 3. フォールバック: MDファイルからナビゲーション構築
  return getRaceNavigationFromMd(date, currentTrack, currentRaceNumber, dayPath);
}

/**
 * 事前生成されたナビゲーションインデックスから読み込み（最速）
 */
async function getRaceNavigationFromIndex(
  date: string,
  currentTrack: string,
  currentRaceNumber: number | undefined,
  dayPath: string
): Promise<{
  tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[];
  races: { raceNumber: number; raceId: string; raceName: string; startTime: string }[];
  allRacesByTime: { track: string; raceNumber: number; raceId: string; startTime: string }[];
  prevRace: { track: string; raceId: string } | null;
  nextRace: { track: string; raceId: string } | null;
} | null> {
  const indexPath = path.join(dayPath, 'temp', 'navigation_index.json');
  
  if (!fs.existsSync(indexPath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(indexPath, 'utf-8');
    const index = JSON.parse(content) as {
      tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[];
      allRacesByTime: { track: string; raceNumber: number; raceId: string; startTime: string; raceName?: string }[];
    };

    // 現在の競馬場のレース一覧を抽出
    const currentTrackRaces = index.allRacesByTime
      .filter(r => r.track === currentTrack)
      .map(r => ({
        raceNumber: r.raceNumber,
        raceId: r.raceId,
        raceName: r.raceName || `${r.raceNumber}R`,
        startTime: r.startTime,
      }))
      .sort((a, b) => a.raceNumber - b.raceNumber);

    // 前後レースを計算
    let prevRace: { track: string; raceId: string } | null = null;
    let nextRace: { track: string; raceId: string } | null = null;

    if (currentRaceNumber !== undefined) {
      // 現在のレースのインデックスを見つける
      const currentIdx = index.allRacesByTime.findIndex(
        r => r.track === currentTrack && r.raceNumber === currentRaceNumber
      );

      if (currentIdx > 0) {
        const prev = index.allRacesByTime[currentIdx - 1];
        prevRace = { track: prev.track, raceId: prev.raceId };
      }

      if (currentIdx >= 0 && currentIdx < index.allRacesByTime.length - 1) {
        const next = index.allRacesByTime[currentIdx + 1];
        nextRace = { track: next.track, raceId: next.raceId };
      }
    }

    return {
      tracks: index.tracks,
      races: currentTrackRaces,
      allRacesByTime: index.allRacesByTime,
      prevRace,
      nextRace,
    };
  } catch {
    // パースエラーは無視してフォールバック
    return null;
  }
}

/**
 * JSONファイル（race_info.json または nittei_*.json）からナビゲーション情報を構築
 */
async function getRaceNavigationFromJson(
  date: string,
  currentTrack: string,
  currentRaceNumber: number | undefined,
  dayPath: string
): Promise<{
  tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[];
  races: { raceNumber: number; raceId: string; raceName: string; startTime: string }[];
  allRacesByTime: { track: string; raceNumber: number; raceId: string; startTime: string }[];
  prevRace: { track: string; raceId: string } | null;
  nextRace: { track: string; raceId: string } | null;
} | null> {
  // race_info.json を試す
  const raceInfoPath = path.join(dayPath, 'race_info.json');
  let kaisaiData: Record<string, Array<{
    race_no: string;
    race_name: string;
    course: string;
    race_id: string;
    start_time?: string;
  }>> | null = null;

  if (fs.existsSync(raceInfoPath)) {
    try {
      const content = fs.readFileSync(raceInfoPath, 'utf-8');
      const data = JSON.parse(content);
      kaisaiData = data.kaisai_data;
    } catch {
      // JSONパースエラーは無視
    }
  }

  // race_info.json がなければ temp/nittei_*.json を試す
  if (!kaisaiData) {
    const tempPath = path.join(dayPath, 'temp');
    if (fs.existsSync(tempPath)) {
      const dateStr = date.replace(/-/g, '');
      const nitteiPath = path.join(tempPath, `nittei_${dateStr}.json`);
      if (fs.existsSync(nitteiPath)) {
        try {
          const content = fs.readFileSync(nitteiPath, 'utf-8');
          const data = JSON.parse(content);
          kaisaiData = data.kaisai_data;
        } catch {
          // JSONパースエラーは無視
        }
      }
    }
  }

  if (!kaisaiData) {
    return null;
  }

  // 全レースを収集
  const allRaces: { track: string; raceNumber: number; raceId: string; startTime: string }[] = [];
  const tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[] = [];
  const trackMap = new Map<string, { raceByNumber: Record<number, string>; firstRaceId: string }>();

  for (const [kaisaiKey, races] of Object.entries(kaisaiData)) {
    const trackName = extractTrackFromKaisaiKey(kaisaiKey);
    if (!trackName) continue;

    for (const race of races) {
      const raceNumber = parseInt(race.race_no.replace('R', ''), 10);
      const startTime = race.start_time || '99:99';
      
      allRaces.push({
        track: trackName,
        raceNumber,
        raceId: race.race_id,
        startTime,
      });

      // トラック別データを蓄積
      if (!trackMap.has(trackName)) {
        trackMap.set(trackName, { raceByNumber: {}, firstRaceId: race.race_id });
      }
      const trackData = trackMap.get(trackName)!;
      trackData.raceByNumber[raceNumber] = race.race_id;
      // 最小レース番号のIDをfirstRaceIdに
      if (raceNumber === 1) {
        trackData.firstRaceId = race.race_id;
      }
    }
  }

  // tracks配列を構築
  for (const [trackName, data] of trackMap.entries()) {
    tracks.push({
      name: trackName,
      firstRaceId: data.firstRaceId,
      raceByNumber: data.raceByNumber,
    });
  }

  // TRACKS配列の順序でソート
  tracks.sort((a, b) => {
    const indexA = TRACKS.indexOf(a.name as any);
    const indexB = TRACKS.indexOf(b.name as any);
    return indexA - indexB;
  });

  // 時刻を分に変換する関数
  const timeToMinutes = (time: string): number => {
    if (!time || time === '99:99') return 9999;
    const [hours, minutes] = time.split(':').map(Number);
    return hours * 60 + minutes;
  };

  // 全レースを出走時間順にソート
  allRaces.sort((a, b) => {
    const timeA = timeToMinutes(a.startTime);
    const timeB = timeToMinutes(b.startTime);
    if (timeA !== timeB) {
      return timeA - timeB;
    }
    const trackIndexA = TRACKS.indexOf(a.track as any);
    const trackIndexB = TRACKS.indexOf(b.track as any);
    return trackIndexA - trackIndexB;
  });

  // 現在のレースのインデックスを特定
  const currentIndex = allRaces.findIndex(
    (r) => r.track === currentTrack && r.raceNumber === currentRaceNumber
  );

  // 前後のレースを取得
  const prevRace = currentIndex > 0
    ? { track: allRaces[currentIndex - 1].track, raceId: allRaces[currentIndex - 1].raceId }
    : null;
  const nextRace = currentIndex >= 0 && currentIndex < allRaces.length - 1
    ? { track: allRaces[currentIndex + 1].track, raceId: allRaces[currentIndex + 1].raceId }
    : null;

  // 現在の競馬場のレース一覧を取得
  const races: { raceNumber: number; raceId: string; raceName: string; startTime: string }[] = [];
  for (const [kaisaiKey, raceList] of Object.entries(kaisaiData)) {
    const trackName = extractTrackFromKaisaiKey(kaisaiKey);
    if (trackName !== currentTrack) continue;

    for (const race of raceList) {
      const raceNumber = parseInt(race.race_no.replace('R', ''), 10);
      races.push({
        raceNumber,
        raceId: race.race_id,
        raceName: race.race_name || `${raceNumber}R`,
        startTime: race.start_time || '',
      });
    }
  }
  races.sort((a, b) => a.raceNumber - b.raceNumber);

  return { tracks, races, allRacesByTime: allRaces, prevRace, nextRace };
}

/**
 * MDファイルからナビゲーション情報を構築（レガシー対応）
 */
async function getRaceNavigationFromMd(
  _date: string,
  currentTrack: string,
  currentRaceNumber: number | undefined,
  dayPath: string
): Promise<{
  tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[];
  races: { raceNumber: number; raceId: string; raceName: string; startTime: string }[];
  allRacesByTime: { track: string; raceNumber: number; raceId: string; startTime: string }[];
  prevRace: { track: string; raceId: string } | null;
  nextRace: { track: string; raceId: string } | null;
} | null> {
  // 競馬場一覧を取得
  const trackDirs = fs.readdirSync(dayPath).filter((f) => {
    const trackPath = path.join(dayPath, f);
    return fs.statSync(trackPath).isDirectory() && TRACKS.includes(f as any);
  });

  if (trackDirs.length === 0) {
    return null;
  }

  // 全レースを収集（出走時間順ナビ用）
  const allRaces: { track: string; raceNumber: number; raceId: string; startTime: string }[] = [];

  // 各競馬場のレース情報を取得
  const tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[] = [];
  for (const track of trackDirs) {
    const trackPath = path.join(dayPath, track);
    const mdFiles = fs
      .readdirSync(trackPath)
      .filter((f) => f.endsWith('.md'))
      .sort();
    
    if (mdFiles.length > 0) {
      const raceByNumber: Record<number, string> = {};
      
      for (const file of mdFiles) {
        const raceId = file.replace('.md', '');
        const raceNumber = parseInt(raceId.slice(-2), 10);
        raceByNumber[raceNumber] = raceId;
        
        // 発走時刻を取得
        const filePath = path.join(trackPath, file);
        const content = fs.readFileSync(filePath, 'utf-8');
        const timeMatch = content.match(/発走予定\**[:\s]*(\d{1,2}:\d{2})/);
        const startTime = timeMatch ? timeMatch[1] : '99:99';
        
        allRaces.push({ track, raceNumber, raceId, startTime });
      }
      
      tracks.push({
        name: track,
        firstRaceId: mdFiles[0].replace('.md', ''),
        raceByNumber,
      });
    }
  }

  // TRACKS配列の順序でソート
  tracks.sort((a, b) => {
    const indexA = TRACKS.indexOf(a.name as any);
    const indexB = TRACKS.indexOf(b.name as any);
    return indexA - indexB;
  });

  // 時刻を分に変換する関数
  const timeToMinutes = (time: string): number => {
    if (!time || time === '99:99') return 9999;
    const [hours, minutes] = time.split(':').map(Number);
    return hours * 60 + minutes;
  };

  // 全レースを出走時間順にソート
  allRaces.sort((a, b) => {
    const timeA = timeToMinutes(a.startTime);
    const timeB = timeToMinutes(b.startTime);
    if (timeA !== timeB) {
      return timeA - timeB;
    }
    const trackIndexA = TRACKS.indexOf(a.track as any);
    const trackIndexB = TRACKS.indexOf(b.track as any);
    return trackIndexA - trackIndexB;
  });

  // 現在のレースのインデックスを特定
  const currentIndex = allRaces.findIndex(
    (r) => r.track === currentTrack && r.raceNumber === currentRaceNumber
  );

  // 前後のレースを取得
  const prevRace = currentIndex > 0
    ? { track: allRaces[currentIndex - 1].track, raceId: allRaces[currentIndex - 1].raceId }
    : null;
  const nextRace = currentIndex >= 0 && currentIndex < allRaces.length - 1
    ? { track: allRaces[currentIndex + 1].track, raceId: allRaces[currentIndex + 1].raceId }
    : null;

  // 現在の競馬場のレース一覧を取得
  const currentTrackPath = path.join(dayPath, currentTrack);
  const races: { raceNumber: number; raceId: string; raceName: string; startTime: string }[] = [];

  if (fs.existsSync(currentTrackPath)) {
    const mdFiles = fs
      .readdirSync(currentTrackPath)
      .filter((f) => f.endsWith('.md'));

    for (const file of mdFiles) {
      const filePath = path.join(currentTrackPath, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const raceId = file.replace('.md', '');
      const raceNumber = parseInt(raceId.slice(-2), 10);

      // レース名を抽出
      const titleMatch = content.match(/^# (.+)$/m);
      let raceName = `${raceNumber}R`;
      if (titleMatch) {
        const titleLine = titleMatch[1];
        const raceMatch = titleLine.match(/\d+R\s*(?:\([^)]+\))?\s*(.+)?/);
        if (raceMatch && raceMatch[1]) {
          raceName = raceMatch[1].trim();
        }
      }

      // 発走時刻を抽出
      const timeMatch = content.match(/発走予定\**[:\s]*(\d{1,2}:\d{2})/);
      const startTime = timeMatch ? timeMatch[1] : '';

      races.push({ raceNumber, raceId, raceName, startTime });
    }

    races.sort((a, b) => a.raceNumber - b.raceNumber);
  }

  return { tracks, races, allRacesByTime: allRaces, prevRace, nextRace };
}

/**
 * ローカルファイルパスをWebアプリURLに変換
 */
function convertLocalPaths(content: string): string {
  // 馬プロファイルへのリンクを変換
  // [馬名](Z:/KEIBA-CICD/data2/horses/profiles/0953665_イッツソーブライト.md)
  // → [馬名](/horses/0953665)
  const horsePattern =
    /\[([^\]]+)\]\((?:Z:|\/)?[^)]*horses\/profiles\/(\d+)_[^)]+\.md\)/g;
  content = content.replace(horsePattern, '[$1](/horses/$2)');

  // レースへのリンクを変換
  // [レース](Z:/KEIBA-CICD/data2/races/2025/12/28/中山/202505050811.md)
  // → [レース](/races/2025-12-28/中山/202505050811)
  const racePattern =
    /\[([^\]]+)\]\((?:Z:|\/)?[^)]*races\/(\d{4})\/(\d{2})\/(\d{2})\/([^/]+)\/(\d+)\.md\)/g;
  content = content.replace(racePattern, '[$1](/races/$2-$3-$4/$5/$6)');

  return content;
}

/**
 * 指定日のrace_info.jsonを読み込み
 */
export interface RaceInfoData {
  date: string;
  kaisai_data: Record<string, Array<{
    race_no: string;
    race_name: string;
    course: string;
    race_id: string;
    start_time?: string;
    start_at?: string;
  }>>;
}

export async function getRaceInfo(date: string): Promise<RaceInfoData | null> {
  const [year, month, day] = date.split('-');
  const filePath = path.join(PATHS.races, year, month, day, 'race_info.json');

  if (!fs.existsSync(filePath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content) as RaceInfoData;
  } catch (error) {
    console.error(`Error reading race_info.json for ${date}:`, error);
    return null;
  }
}
