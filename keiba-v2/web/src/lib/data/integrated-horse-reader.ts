/**
 * 統合馬プロファイルデータ読み込みユーティリティ
 * 
 * データソース優先順位:
 * 1. TARGET JV-Data (Y:/UM_DATA) - 高速な基本情報取得
 * 2. TARGET SE_DATA (Y:/SE_DATA) - 過去レース成績ベース
 * 3. integrated_*.json - 競馬ブックコメント等の付加情報
 * 4. MDプロファイル (Z:/KEIBA-CICD/data2/horses/profiles) - ユーザーメモ
 */

import fs from 'fs';
import path from 'path';
import { findHorseFromTarget, calculateHorseAge, isTargetDataAvailable, type TargetHorseData } from './target-horse-reader';
import { getHorseRaceResultsFromTarget, isTargetSeDataAvailable, type TargetRaceResult } from './target-race-result-reader';
import { getRaceFilesForHorse, isIndexAvailable } from './horse-race-index';
import { getTrainerInfo } from './trainer-index';
import { DATA3_ROOT } from '@/lib/config';

// ディレクトリ一覧キャッシュ（1分間有効）
const dirCache = new Map<string, { entries: string[]; timestamp: number }>();
const DIR_CACHE_TTL = 60000; // 1分

// training_summary.json キャッシュ（日付 -> 馬名 -> 調教データ）
interface TrainingSummaryEntry {
  detail?: string;
  lapRank?: string;
  finalSpeed?: string;
}
const trainingSummaryCache = new Map<string, Map<string, TrainingSummaryEntry>>();

/**
 * 指定日の training_summary.json を読み込み、馬名でインデックス化
 */
function loadTrainingSummary(datePath: string): Map<string, TrainingSummaryEntry> {
  // datePath形式: YYYY/MM/DD
  if (trainingSummaryCache.has(datePath)) {
    return trainingSummaryCache.get(datePath)!;
  }
  
  const result = new Map<string, TrainingSummaryEntry>();
  
  try {
    const [year, month, day] = datePath.split('/');
    const filePath = path.join(
      DATA3_ROOT,
      'races', year, month, day, 'temp', 'training_summary.json'
    );
    
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      const data = JSON.parse(content);
      const summaries = data.summaries || {};
      
      for (const [horseName, entry] of Object.entries(summaries)) {
        const typedEntry = entry as Record<string, unknown>;
        result.set(horseName, {
          detail: typedEntry.detail as string || '',
          lapRank: typedEntry.lapRank as string || '',
          finalSpeed: typedEntry.finalSpeed as string || '',
        });
      }
    }
  } catch (e) {
    // ファイル読み込みエラーは無視
  }
  
  trainingSummaryCache.set(datePath, result);
  return result;
}

function readdirCached(dirPath: string): string[] {
  const now = Date.now();
  const cached = dirCache.get(dirPath);
  
  if (cached && (now - cached.timestamp) < DIR_CACHE_TTL) {
    return cached.entries;
  }
  
  try {
    const entries = fs.readdirSync(dirPath);
    dirCache.set(dirPath, { entries, timestamp: now });
    return entries;
  } catch {
    return [];
  }
}

function existsCached(filePath: string): boolean {
  try {
    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

// race_info.jsonキャッシュ
const raceInfoCache = new Map<string, Record<string, { track: string; raceName: string; distance: string }>>();

/**
 * race_info.jsonから正しい競馬場名を取得
 * integrated_*.jsonのvenueが間違っている場合の補正用
 */
function getTrackFromRaceInfo(integratedFilePath: string, raceId: string): string | null {
  try {
    // ファイルパスから日付フォルダを取得
    // 例: Z:\KEIBA-CICD\data2\races\2026\01\24\temp\integrated_xxx.json
    const pathMatch = integratedFilePath.match(/races[/\\](\d{4})[/\\](\d{2})[/\\](\d{2})/);
    if (!pathMatch) return null;

    const [, year, month, day] = pathMatch;
    const dateKey = `${year}/${month}/${day}`;
    
    // キャッシュを確認
    if (raceInfoCache.has(dateKey)) {
      const cached = raceInfoCache.get(dateKey)!;
      return cached[raceId]?.track || null;
    }

    // race_info.jsonを読み込み
    const raceInfoPath = path.join(
      DATA3_ROOT,
      'races', year, month, day, 'race_info.json'
    );
    
    if (!fs.existsSync(raceInfoPath)) {
      raceInfoCache.set(dateKey, {});
      return null;
    }

    const raceInfo = JSON.parse(fs.readFileSync(raceInfoPath, 'utf-8'));
    const raceMap: Record<string, { track: string; raceName: string; distance: string }> = {};
    
    // kaisai_dataからraceId→競馬場マッピングを作成
    for (const [kaisaiKey, races] of Object.entries(raceInfo.kaisai_data || {})) {
      // kaisaiKeyの例: "1回中山8日目"
      const trackMatch = kaisaiKey.match(/\d+回(.+?)\d+日目/);
      const track = trackMatch ? trackMatch[1] : '';
      
      for (const race of (races as Array<{ race_id: string; race_name?: string; course?: string }>)) {
        raceMap[race.race_id] = {
          track,
          raceName: race.race_name || '',
          distance: race.course || '',
        };
      }
    }
    
    raceInfoCache.set(dateKey, raceMap);
    return raceMap[raceId]?.track || null;
  } catch {
    return null;
  }
}

/**
 * race_info.jsonからレース情報を取得（キャッシュ構築も行う）
 */
function getRaceInfoFromCache(datePath: string, raceId: string): { track: string; raceName: string; distance: string } | null {
  const dateKey = datePath; // YYYY/MM/DD形式
  
  // キャッシュがあればそこから返す
  if (raceInfoCache.has(dateKey)) {
    const cached = raceInfoCache.get(dateKey)!;
    return cached[raceId] || null;
  }
  
  // キャッシュがなければ構築する
  try {
    const [year, month, day] = datePath.split('/');
    const raceInfoPath = path.join(
      DATA3_ROOT,
      'races', year, month, day, 'race_info.json'
    );
    
    if (!fs.existsSync(raceInfoPath)) {
      raceInfoCache.set(dateKey, {});
      return null;
    }

    const raceInfo = JSON.parse(fs.readFileSync(raceInfoPath, 'utf-8'));
    const raceMap: Record<string, { track: string; raceName: string; distance: string }> = {};
    
    // kaisai_dataからraceId→レース情報マッピングを作成
    for (const [kaisaiKey, races] of Object.entries(raceInfo.kaisai_data || {})) {
      const trackMatch = kaisaiKey.match(/\d+回(.+?)\d+日目/);
      const track = trackMatch ? trackMatch[1] : '';
      
      for (const race of (races as Array<{ race_id: string; race_name?: string; course?: string }>)) {
        raceMap[race.race_id] = {
          track,
          raceName: race.race_name || '',
          distance: race.course || '',
        };
      }
    }
    
    raceInfoCache.set(dateKey, raceMap);
    return raceMap[raceId] || null;
  } catch {
    raceInfoCache.set(dateKey, {});
    return null;
  }
}

/**
 * 直近のintegrated_*.jsonから馬ID（競馬ブックID）で馬名を検索
 * 初出走馬で他のソースに情報がない場合のフォールバック
 */
function findHorseNameFromRecentRaces(horseId: string): { horseName: string; kettoNum: string } | null {
  const racesDir = path.join(DATA3_ROOT, 'races');
  try {
    const years = fs.readdirSync(racesDir).filter(d => /^\d{4}$/.test(d)).sort().reverse();
    let daysChecked = 0;
    for (const year of years) {
      const months = fs.readdirSync(path.join(racesDir, year)).filter(d => /^\d{2}$/.test(d)).sort().reverse();
      for (const month of months) {
        const days = fs.readdirSync(path.join(racesDir, year, month)).filter(d => /^\d{2}$/.test(d)).sort().reverse();
        for (const day of days) {
          if (daysChecked >= 5) return null;
          daysChecked++;
          const tempDir = path.join(racesDir, year, month, day, 'temp');
          if (!fs.existsSync(tempDir)) continue;
          const files = fs.readdirSync(tempDir).filter(f => f.startsWith('integrated_') && f.endsWith('.json'));
          for (const file of files) {
            try {
              const content = fs.readFileSync(path.join(tempDir, file), 'utf-8');
              const data = JSON.parse(content);
              for (const entry of data.entries || []) {
                const entryHorseId = String(entry.horse_id || entry.horse_profile_id || '');
                if (entryHorseId === horseId && entry.horse_name) {
                  // training_summary.jsonからkettoNumも取得
                  const tsPath = path.join(tempDir, 'training_summary.json');
                  let kettoNum = '';
                  try {
                    if (fs.existsSync(tsPath)) {
                      const tsContent = fs.readFileSync(tsPath, 'utf-8');
                      const tsData = JSON.parse(tsContent);
                      const summary = tsData.summaries?.[entry.horse_name];
                      if (summary?.kettoNum) {
                        kettoNum = summary.kettoNum;
                      }
                    }
                  } catch { /* ignore */ }
                  return { horseName: entry.horse_name, kettoNum };
                }
              }
            } catch { /* ignore */ }
          }
        }
      }
    }
  } catch { /* ignore */ }
  return null;
}

// データルートディレクトリ
const DATA_ROOT = DATA3_ROOT;

// 馬プロフィールディレクトリ
const HORSES_DIR = path.join(DATA_ROOT, 'horses', 'profiles');

/**
 * 馬の基本情報
 */
export interface HorseBasicInfo {
  id: string;
  name: string;
  age: string;            // 性齢 (例: "牡4")
  trainer: string;        // 調教師
  trainerId: string;      // 競馬ブック厩舎ID (例: "ｳ011")
  trainerLink: string;    // 厩舎ページURL
  trainerTozai: string;   // 所属 ("美浦" | "栗東")
  trainerJvnCode: string; // JRA-VAN調教師コード
  trainerComment: string; // 調教師コメント（勝負調教パターン等）
  jockey: string;         // 最近の騎手
  totalRaces: number;     // 通算出走数
  updatedAt: string;      // 最終更新日時
}

/**
 * 過去レース成績
 */
export interface HorseRaceResult {
  date: string;           // 日付 YYYY/MM/DD
  track: string;          // 競馬場
  raceId: string;         // レースID
  raceNumber: number;     // レース番号
  raceName: string;       // レース名
  raceClass: string;      // クラス
  distance: string;       // 距離（例: "芝1600"）
  condition: string;      // 馬場状態
  headCount: number;      // 頭数
  horseNumber: number;    // 馬番
  frameNumber: number;    // 枠番
  weight: string;         // 斤量
  horseWeight: string;    // 馬体重
  horseWeightDiff: string; // 馬体重増減
  jockey: string;         // 騎手
  finishPosition: string; // 着順
  popularity: string;     // 人気
  time: string;           // タイム
  timeDiff: string;       // タイム差/着差
  first3f: string;        // 前半3F
  last3f: string;         // 上がり3F
  corner4Pos: string;     // 4角位置
  cornerPositions: string; // 通過順位
  odds: string;           // オッズ
  // 付加情報
  honshiMark: string;     // 本誌印
  shortComment: string;   // 短評
  trainingArrow: string;  // 調教矢印
  trainingComment: string; // 調教短評
  attackExplanation: string; // 攻め馬解説
  stableComment: string;  // 厩舎談話
  paddockMark: string;    // パドック評価
  paddockComment: string; // パドックコメント
  resultMemo: string;     // 結果メモ
  resultComment: string;  // 結果コメント
  sunpyou: string;        // 寸評
  // 調教師情報
  trainer?: string;       // 調教師名
  trainerId?: string;     // 競馬ブック厩舎ID
  trainerLink?: string;   // 厩舎ページURL
  trainerTozai?: string;  // 所属
  // 調教情報（training_summary.jsonから取得）
  trainingDetail?: string;     // 調教タイム詳細
  trainingLapRank?: string;    // ラップランク
  trainingFinalSpeed?: string; // 最終追切の好タイムフラグ
  // TARGET形式のレースID（12桁、race_trend_index.jsonのキーと一致）
  targetRaceId?: string;
  // レース傾向（race_trend_index.jsonから付与）
  raceTrend?: string;          // 'sprint_finish' | 'long_sprint' | 'even_pace' | 'front_loaded' | 'front_loaded_strong'
}

/**
 * 成績統計
 */
export interface HorseStats {
  total: StatGroup;
  turf: StatGroup;
  dirt: StatGroup;
  byDistance: Record<string, StatGroup>;
  byCondition: Record<string, StatGroup>;
  byFrame: Record<string, StatGroup>;     // 枠順別 (内枠/中枠/外枠)
  byFieldSize: Record<string, StatGroup>; // 頭数別 (少頭数/中頭数/多頭数)
  byTrend?: Record<string, StatGroup>;    // レース傾向別 (瞬発/ロンスパ/平均/H前傾/H後傾)
}

export interface StatGroup {
  races: number;
  wins: number;
  seconds: number;
  thirds: number;
  winRate: number;
  placeRate: number;
  showRate: number;
}

/**
 * 統合馬プロファイルデータ
 */
export interface IntegratedHorseData {
  basic: HorseBasicInfo;
  pastRaces: HorseRaceResult[];
  stats: HorseStats;
  userMemo: string;
}

/**
 * 馬IDからプロファイルMDファイルパスを取得
 */
function findHorseProfilePath(horseId: string): string | null {
  if (!fs.existsSync(HORSES_DIR)) {
    return null;
  }

  const files = fs.readdirSync(HORSES_DIR);
  const targetFile = files.find((f) => f.startsWith(`${horseId}_`) && f.endsWith('.md'));
  
  if (!targetFile) {
    return null;
  }

  return path.join(HORSES_DIR, targetFile);
}

/**
 * 馬プロファイルMDから基本情報を抽出
 */
function extractBasicInfoFromMd(content: string, horseId: string): HorseBasicInfo {
  const lines = content.split('\n');
  
  let name = '';
  let age = '';
  let trainer = '';
  let jockey = '';
  let updatedAt = '';
  
  // ファイル冒頭の # 馬プロファイル: XXX から馬名を抽出
  const titleMatch = content.match(/^# 馬プロファイル:\s*(.+)/m);
  if (titleMatch) {
    name = titleMatch[1].trim();
  }
  
  // 基本情報セクションから抽出
  const ageMatch = content.match(/\*?\*?性齢\*?\*?[:\s]*\*?\*?([^\n*]+)/);
  if (ageMatch) {
    age = ageMatch[1].trim();
  }
  
  const trainerMatch = content.match(/\*?\*?調教師\*?\*?[:\s]*\*?\*?([^\n*]+)/);
  if (trainerMatch) {
    trainer = trainerMatch[1].trim();
  }
  
  const jockeyMatch = content.match(/\*?\*?騎手\*?\*?[:\s]*\*?\*?([^\n*]+)/);
  if (jockeyMatch) {
    jockey = jockeyMatch[1].trim();
  }
  
  const updateMatch = content.match(/\*最終更新:\s*([^*]+)\*/);
  if (updateMatch) {
    updatedAt = updateMatch[1].trim();
  }
  
  return {
    id: horseId,
    name,
    age,
    trainer,
    trainerId: '',
    trainerLink: '',
    trainerTozai: '',
    trainerJvnCode: '',
    trainerComment: '',
    jockey,
    totalRaces: 0, // 後で計算
    updatedAt,
  };
}

/**
 * 馬プロファイルMDからユーザーメモを抽出
 */
function extractUserMemoFromMd(content: string): string {
  const memoMatch = content.match(/## ユーザーメモ\n([\s\S]*?)(?:\n---|\n##|$)/);
  if (memoMatch) {
    const memo = memoMatch[1].trim();
    // デフォルトプレースホルダーは空として扱う
    if (memo === '（ここに予想メモや注目ポイントを記入）') {
      return '';
    }
    return memo;
  }
  return '';
}

/**
 * レースファイルからレース結果を抽出
 */
function extractRaceResultFromFile(filePath: string, horseId: string, horseName: string): HorseRaceResult | null {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);

    // entriesから該当馬を探す
    for (const entry of data.entries || []) {
      const entryHorseId = String(entry.horse_id || entry.horse_profile_id || '');
      const entryHorseName = entry.horse_name || '';

      const idMatch = entryHorseId === horseId;
      const nameMatch = horseName && entryHorseName === horseName;

      if (idMatch || nameMatch) {
        // ファイルパスから日付を抽出
        const pathMatch = filePath.match(/races[/\\](\d{4})[/\\](\d{2})[/\\](\d{2})/);
        const year = pathMatch?.[1] || '';
        const month = pathMatch?.[2] || '';
        const day = pathMatch?.[3] || '';

        const raceInfo = data.race_info || {};
        const entryData = entry.entry_data || {};
        const trainingData = entry.training_data || {};
        const stableComment = entry.stable_comment || {};
        const paddockInfo = entry.paddock_info || {};
        const result = entry.result || {};
        const rawData = result.raw_data || {};

        const raceId = data.meta?.race_id || path.basename(filePath).replace('integrated_', '').replace('.json', '');

        return {
          date: `${year}/${month}/${day}`,
          track: raceInfo.venue || '',
          raceId,
          raceNumber: raceInfo.race_number || 0,
          raceName: raceInfo.race_name || '',
          raceClass: raceInfo.race_class || raceInfo.grade || '',
          distance: raceInfo.race_condition || raceInfo.course || '',
          condition: raceInfo.track_condition || raceInfo.turf_condition || '',
          headCount: (data.entries || []).length,
          horseNumber: entry.horse_number || 0,
          frameNumber: entryData.waku || 0,
          weight: entryData.weight || '',
          horseWeight: rawData.馬体重 || entryData.horse_weight || '',
          horseWeightDiff: rawData.増減 || entryData.horse_weight_diff || '',
          jockey: entryData.jockey || rawData.騎手 || '',
          finishPosition: result.finish_position || rawData.着順 || '',
          popularity: entryData.odds_rank || rawData.単人気 || '',
          time: result.time || rawData.タイム || '',
          timeDiff: rawData.着差 || '',
          first3f: result.first_3f || rawData.前半3F || '',
          last3f: result.last_3f || rawData.上り3F || rawData.上がり || '',
          corner4Pos: result.last_corner_position || rawData['4角位置'] || '',
          cornerPositions: rawData.通過順位 || result.passing_orders || '',
          odds: entryData.odds || '',
          honshiMark: entryData.honshi_mark || '',
          shortComment: entryData.short_comment || '',
          trainingArrow: trainingData.training_arrow || '',
          trainingComment: trainingData.short_review || '',
          attackExplanation: trainingData.attack_explanation || '',
          stableComment: stableComment.comment || '',
          paddockMark: paddockInfo.mark || '',
          paddockComment: paddockInfo.comment || '',
          resultMemo: rawData.memo || '',
          resultComment: rawData.interview || '',
          sunpyou: result.sunpyo || rawData.寸評 || '',
          // 調教師情報
          trainer: entryData.trainer || '',
          trainerId: entryData.trainer_id || '',
          trainerLink: entryData.trainer_link || '',
          trainerTozai: entryData.trainer_tozai || '',
        };
      }
    }
  } catch (e) {
    // ファイル読み込みエラーは無視
  }
  return null;
}

/**
 * TARGET SE_DATAからHorseRaceResult形式に変換
 */
function targetResultToHorseRaceResult(target: TargetRaceResult): HorseRaceResult {
  // 日付をYYYY/MM/DD形式に変換
  const dateStr = target.raceDate;
  const formattedDate = dateStr.length === 8 
    ? `${dateStr.substring(0, 4)}/${dateStr.substring(4, 6)}/${dateStr.substring(6, 8)}`
    : dateStr;
  
  // コーナー通過順を文字列化
  const corners = [target.corner1, target.corner2, target.corner3, target.corner4]
    .filter(c => c > 0)
    .join('-');
  
  return {
    date: formattedDate,
    track: target.venue,
    raceId: target.raceId,
    raceNumber: target.raceNumber,
    raceName: '',  // TARGET SE_DATAにはレース名がない（後でマージ）
    targetRaceId: target.raceId, // TARGET形式のraceIdを保持（race_trend_index用）
    raceClass: '',
    distance: '',  // TARGET SE_DATAには距離情報がない（後でマージ）
    condition: '',
    headCount: 0,  // TARGET SE_DATAには頭数がない（後でマージ）
    horseNumber: target.umaban,
    frameNumber: target.wakuban,
    weight: String(target.weight),
    horseWeight: String(target.horseWeight),
    horseWeightDiff: target.weightDiff,
    jockey: target.jockeyName,
    finishPosition: String(target.finishPosition),
    popularity: String(target.popularity),
    time: target.time,
    timeDiff: '',
    first3f: '',   // TARGET SE_DATAには前半3Fがない（後でマージ）
    last3f: target.last3f,
    corner4Pos: target.corner4 > 0 ? String(target.corner4) : '',
    cornerPositions: corners,
    odds: String(target.odds),
    // 競馬ブック付加情報（後でマージ）
    honshiMark: '',
    shortComment: '',
    trainingArrow: '',
    trainingComment: '',
    attackExplanation: '',
    stableComment: '',
    paddockMark: '',
    paddockComment: '',
    resultMemo: '',
    resultComment: '',
    sunpyou: '',
  };
}

/**
 * 競馬ブックデータをTARGETベースの結果にマージ
 */
function mergeKeibabookData(base: HorseRaceResult, keibabook: HorseRaceResult): HorseRaceResult {
  return {
    ...base,
    // レースIDを競馬ブックから取得（リンク用に重要）
    raceId: keibabook.raceId || base.raceId,
    // レース情報を競馬ブックから補完
    raceName: keibabook.raceName || base.raceName,
    raceClass: keibabook.raceClass || base.raceClass,
    distance: keibabook.distance || base.distance,
    condition: keibabook.condition || base.condition,
    headCount: keibabook.headCount || base.headCount,
    first3f: keibabook.first3f || base.first3f,
    corner4Pos: keibabook.corner4Pos || base.corner4Pos,
    cornerPositions: keibabook.cornerPositions || base.cornerPositions,
    // 競馬ブック固有データ
    honshiMark: keibabook.honshiMark,
    shortComment: keibabook.shortComment,
    trainingArrow: keibabook.trainingArrow,
    trainingComment: keibabook.trainingComment,
    attackExplanation: keibabook.attackExplanation,
    stableComment: keibabook.stableComment,
    paddockMark: keibabook.paddockMark,
    paddockComment: keibabook.paddockComment,
    resultMemo: keibabook.resultMemo,
    resultComment: keibabook.resultComment,
    sunpyou: keibabook.sunpyou,
  };
}

/**
 * 過去レースデータを集約
 * 
 * データソース優先順位:
 * 1. TARGET SE_DATA（基本成績データ）- 高速・全履歴
 * 2. integrated_*.json（競馬ブックコメント等）- 付加情報
 * 
 * @param horseId 競馬ブック馬ID（7桁）
 * @param horseName 馬名
 * @param maxRaces 最大取得件数
 * @param targetKettoNum TARGET血統登録番号（10桁）- SE_DATA検索用
 */
async function collectPastRaces(
  horseId: string, 
  horseName: string, 
  maxRaces: number = 30,
  targetKettoNum: string = ''
): Promise<HorseRaceResult[]> {
  const startTime = Date.now();
  const results: HorseRaceResult[] = [];
  const keibabookDataByRaceId = new Map<string, HorseRaceResult>();

  // 1. TARGET SE_DATAから基本成績を取得（高速）
  // targetKettoNumがあればそれを使用、なければhorseIdをパディング
  const kettoNumForSearch = targetKettoNum || horseId.padStart(10, '0');
  
  if (isTargetSeDataAvailable()) {
    try {
      const targetResults = await getHorseRaceResultsFromTarget(kettoNumForSearch);
      
      for (const tr of targetResults) {
        if (results.length >= maxRaces) break;
        results.push(targetResultToHorseRaceResult(tr));
      }
      
      const elapsed = Date.now() - startTime;
      if (elapsed > 100 || results.length === 0) {
        console.log(`[IntegratedHorseReader] TARGET SE_DATA lookup (kettoNum=${kettoNumForSearch}) took ${elapsed}ms for ${results.length} results`);
      }
    } catch (e) {
      console.error('[IntegratedHorseReader] TARGET SE_DATA error:', e);
    }
  }

  // 2. 競馬ブックデータから付加情報を収集
  // raceIdの形式が異なるため、日付+競馬場+レース番号でマッチング
  const keibabookDataByMatchKey = new Map<string, HorseRaceResult>();
  
  if (isIndexAvailable()) {
    const raceFiles = getRaceFilesForHorse(horseId);
    
    console.log(`[IntegratedHorseReader] Processing ${raceFiles.length} race files for horseId=${horseId}`);
    
    for (const filePath of raceFiles) {
      const kbResult = extractRaceResultFromFile(filePath, horseId, horseName);
      if (kbResult) {
        const originalTrack = kbResult.track;
        
        // race_info.jsonから正しい競馬場・距離・レース名を取得
        const raceInfoData = getRaceInfoFromCache(kbResult.date, kbResult.raceId);
        if (raceInfoData) {
          kbResult.track = raceInfoData.track || kbResult.track;
          kbResult.distance = raceInfoData.distance || kbResult.distance;
          kbResult.raceName = raceInfoData.raceName || kbResult.raceName;
          console.log(`[IntegratedHorseReader] Corrected track from "${originalTrack}" to "${kbResult.track}" for raceId=${kbResult.raceId}`);
        } else {
          console.log(`[IntegratedHorseReader] No race_info data for date=${kbResult.date}, raceId=${kbResult.raceId}`);
        }
        
        // 日付+競馬場+レース番号でマッチングキーを生成
        // date形式: YYYY/MM/DD, track: 中山, raceNumber: 7
        const matchKey = `${kbResult.date.replace(/\//g, '')}|${kbResult.track}|${kbResult.raceNumber}`;
        keibabookDataByMatchKey.set(matchKey, kbResult);
        // raceIdでもセット（フォールバック用）
        keibabookDataByRaceId.set(kbResult.raceId, kbResult);
      }
    }
  }

  // デバッグ: 競馬ブックデータのキー一覧
  console.log(`[IntegratedHorseReader] Keibabook data collected: ${keibabookDataByMatchKey.size} entries by matchKey, ${keibabookDataByRaceId.size} entries by raceId`);
  if (keibabookDataByMatchKey.size > 0) {
    const sampleKeys = Array.from(keibabookDataByMatchKey.keys()).slice(0, 3);
    console.log(`[IntegratedHorseReader] Sample matchKeys: ${sampleKeys.join(', ')}`);
  }

  // 3. TARGETデータがない場合はフォールバック
  if (results.length === 0) {
    // 競馬ブックデータのみ使用
    for (const [, kbResult] of keibabookDataByRaceId) {
      if (results.length >= maxRaces) break;
      results.push(kbResult);
    }
  } else {
    // 4. TARGETベースに競馬ブックデータをマージ
    let matchCount = 0;
    const unmatchedKeys: string[] = [];
    
    // デバッグ: 最初の3件のTARGET matchKeyを表示
    const targetSampleKeys = results.slice(0, 3).map(r => 
      `${r.date.replace(/\//g, '')}|${r.track}|${r.raceNumber}`
    );
    console.log(`[IntegratedHorseReader] Sample TARGET matchKeys: ${targetSampleKeys.join(', ')}`);
    
    for (let i = 0; i < results.length; i++) {
      // 日付+競馬場+レース番号でマッチング
      // date形式: YYYY/MM/DD, track: 中山, raceNumber: 7
      const matchKey = `${results[i].date.replace(/\//g, '')}|${results[i].track}|${results[i].raceNumber}`;
      let kbData = keibabookDataByMatchKey.get(matchKey);
      
      // マッチしない場合はraceIdでフォールバック
      if (!kbData) {
        kbData = keibabookDataByRaceId.get(results[i].raceId);
      }
      
      if (kbData) {
        results[i] = mergeKeibabookData(results[i], kbData);
        matchCount++;
      } else {
        unmatchedKeys.push(matchKey);
        // 競馬ブックデータがない場合、race_info.jsonから距離・レース名を補完
        const dateForPath = results[i].date; // YYYY/MM/DD形式
        const [year, month, day] = dateForPath.split('/');
        if (year && month && day) {
          const raceInfoPath = path.join(
            DATA3_ROOT,
            'races', year, month, day, 'race_info.json'
          );
          
          // race_info.jsonから情報取得を試みる
          try {
            if (fs.existsSync(raceInfoPath)) {
              const raceInfo = JSON.parse(fs.readFileSync(raceInfoPath, 'utf-8'));
              for (const [kaisaiKey, races] of Object.entries(raceInfo.kaisai_data || {})) {
                const trackMatch = kaisaiKey.match(/\d+回(.+?)\d+日目/);
                const track = trackMatch ? trackMatch[1] : '';
                
                // 競馬場が一致するレースを探す
                if (track === results[i].track) {
                  for (const race of (races as Array<{ race_no: string; race_name?: string; course?: string; race_id?: string }>)) {
                    const raceNo = parseInt(race.race_no?.replace('R', '') || '0', 10);
                    if (raceNo === results[i].raceNumber) {
                      results[i].raceName = race.race_name || '';
                      results[i].distance = race.course || '';
                      // 正しいraceIdを取得（競馬ブック形式）
                      if (race.race_id) {
                        results[i].raceId = race.race_id;
                      }
                      break;
                    }
                  }
                }
              }
            }
          } catch {
            // ignore
          }
        }
      }
    }
    
    // マッチング結果ログ
    console.log(`[IntegratedHorseReader] Merge result: ${matchCount}/${results.length} matched`);
    if (unmatchedKeys.length > 0 && unmatchedKeys.length <= 5) {
      console.log(`[IntegratedHorseReader] Unmatched TARGET keys: ${unmatchedKeys.join(', ')}`);
    }
  }

  // 各レースに調教情報を追加
  let trainingCount = 0;
  for (const result of results) {
    // date形式: YYYY/MM/DD
    const trainingSummary = loadTrainingSummary(result.date);
    
    // 馬名で検索
    const trainingEntry = trainingSummary.get(horseName);
    if (trainingEntry) {
      result.trainingDetail = trainingEntry.detail || '';
      result.trainingLapRank = trainingEntry.lapRank || '';
      result.trainingFinalSpeed = trainingEntry.finalSpeed || '';
      trainingCount++;
    }
  }
  
  if (trainingCount > 0) {
    console.log(`[IntegratedHorseReader] Training data added: ${trainingCount}/${results.length} races`);
  }

  const elapsed = Date.now() - startTime;
  if (elapsed > 500) {
    console.log(`[IntegratedHorseReader] collectPastRaces total: ${elapsed}ms for ${results.length} results`);
  }

  // 日付降順でソート
  results.sort((a, b) => b.date.localeCompare(a.date));
  return results;
}

/**
 * 成績統計を計算
 */
function calculateStats(pastRaces: HorseRaceResult[]): HorseStats {
  const createEmptyStats = (): StatGroup => ({
    races: 0,
    wins: 0,
    seconds: 0,
    thirds: 0,
    winRate: 0,
    placeRate: 0,
    showRate: 0,
  });

  const stats: HorseStats = {
    total: createEmptyStats(),
    turf: createEmptyStats(),
    dirt: createEmptyStats(),
    byDistance: {},
    byCondition: {},
    byFrame: {},
    byFieldSize: {},
  };

  for (const race of pastRaces) {
    const pos = parseInt(race.finishPosition, 10);
    if (isNaN(pos)) continue;

    // 芝/ダート判定
    const isTurf = race.distance.includes('芝');
    const isDirt = race.distance.includes('ダ') || race.distance.includes('D');

    // 距離抽出 (1200, 1400, 1600, 1800, 2000+)
    const distMatch = race.distance.match(/(\d{3,4})/);
    const distNum = distMatch ? parseInt(distMatch[1], 10) : 0;
    let distKey = '';
    if (distNum > 0) {
      if (distNum < 1400) distKey = '1200m';
      else if (distNum < 1600) distKey = '1400m';
      else if (distNum < 1800) distKey = '1600m';
      else if (distNum < 2000) distKey = '1800m';
      else distKey = '2000m+';
    }

    // 馬場状態
    const condKey = race.condition || '不明';

    // 枠順別 (内枠: 1-3, 中枠: 4-6, 外枠: 7-8)
    const frame = race.frameNumber;
    let frameKey = '';
    if (frame >= 1 && frame <= 3) frameKey = '内枠(1-3)';
    else if (frame >= 4 && frame <= 6) frameKey = '中枠(4-6)';
    else if (frame >= 7) frameKey = '外枠(7-8)';

    // 頭数別 (少頭数: ～11頭, 中頭数: 12-15頭, 多頭数: 16頭～)
    const headCount = race.headCount;
    let fieldSizeKey = '';
    if (headCount > 0) {
      if (headCount <= 11) fieldSizeKey = '少頭数(～11頭)';
      else if (headCount <= 15) fieldSizeKey = '中頭数(12-15頭)';
      else fieldSizeKey = '多頭数(16頭～)';
    }

    // カウント更新
    const updateGroup = (group: StatGroup) => {
      group.races++;
      if (pos === 1) group.wins++;
      if (pos <= 2) group.seconds++;
      if (pos <= 3) group.thirds++;
    };

    updateGroup(stats.total);
    if (isTurf) updateGroup(stats.turf);
    if (isDirt) updateGroup(stats.dirt);

    if (distKey) {
      if (!stats.byDistance[distKey]) {
        stats.byDistance[distKey] = createEmptyStats();
      }
      updateGroup(stats.byDistance[distKey]);
    }

    if (!stats.byCondition[condKey]) {
      stats.byCondition[condKey] = createEmptyStats();
    }
    updateGroup(stats.byCondition[condKey]);

    // 枠順別
    if (frameKey) {
      if (!stats.byFrame[frameKey]) {
        stats.byFrame[frameKey] = createEmptyStats();
      }
      updateGroup(stats.byFrame[frameKey]);
    }

    // 頭数別
    if (fieldSizeKey) {
      if (!stats.byFieldSize[fieldSizeKey]) {
        stats.byFieldSize[fieldSizeKey] = createEmptyStats();
      }
      updateGroup(stats.byFieldSize[fieldSizeKey]);
    }
  }

  // 率を計算
  const calcRates = (group: StatGroup) => {
    if (group.races > 0) {
      group.winRate = Math.round((group.wins / group.races) * 1000) / 10;
      group.placeRate = Math.round((group.seconds / group.races) * 1000) / 10;
      group.showRate = Math.round((group.thirds / group.races) * 1000) / 10;
    }
  };

  calcRates(stats.total);
  calcRates(stats.turf);
  calcRates(stats.dirt);
  Object.values(stats.byDistance).forEach(calcRates);
  Object.values(stats.byCondition).forEach(calcRates);
  Object.values(stats.byFrame).forEach(calcRates);
  Object.values(stats.byFieldSize).forEach(calcRates);

  return stats;
}

/**
 * 統合馬プロファイルデータを取得
 * 
 * データソース優先順位:
 * 1. TARGET JV-Data (高速) - 基本情報
 * 2. JSON/MD - 過去レース詳細、ユーザーメモ
 */
export async function getIntegratedHorseData(horseId: string): Promise<IntegratedHorseData | null> {
  const totalStart = Date.now();
  
  try {
    let basic: HorseBasicInfo;
    let userMemo = '';
    let horseName = '';
    let targetKettoNum = '';  // TARGET KettoNum（血統登録番号）

    // 0. 馬名を取得（TARGET検索のため）
    // 優先順位: 1. MDファイル, 2. integrated_*.json
    const profilePath = findHorseProfilePath(horseId);
    let knownHorseName = '';
    
    // MDファイルから馬名を取得
    if (profilePath && fs.existsSync(profilePath)) {
      const content = fs.readFileSync(profilePath, 'utf-8');
      const basicFromMd = extractBasicInfoFromMd(content, horseId);
      knownHorseName = basicFromMd.name;
      userMemo = extractUserMemoFromMd(content);
    }
    
    // MDにない場合はintegrated_*.jsonから馬名を取得
    if (!knownHorseName && isIndexAvailable()) {
      const raceFiles = getRaceFilesForHorse(horseId);
      if (raceFiles.length > 0) {
        try {
          const content = fs.readFileSync(raceFiles[0], 'utf-8');
          const data = JSON.parse(content);
          for (const entry of data.entries || []) {
            const entryHorseId = String(entry.horse_id || entry.horse_profile_id || '');
            if (entryHorseId === horseId && entry.horse_name) {
              knownHorseName = entry.horse_name;
              console.log(`[IntegratedHorseReader] Got horse name from integrated JSON: ${knownHorseName}`);
              break;
            }
          }
        } catch (e) {
          // ignore
        }
      }
    }

    // 1. TARGET JV-Dataから基本情報を取得
    // IDで検索、見つからなければ馬名でも検索
    const targetStart = Date.now();
    const targetData = await findHorseFromTarget(horseId, knownHorseName);
    const targetElapsed = Date.now() - targetStart;
    if (targetElapsed > 500) {
      console.log(`[IntegratedHorseReader] TARGET lookup took ${targetElapsed}ms`);
    }
    
    if (targetData) {
      const age = calculateHorseAge(targetData.birthDate);
      basic = {
        id: horseId,
        name: targetData.name,
        age: `${targetData.sex}${age}`,
        trainer: targetData.trainerName,
        trainerId: '',
        trainerLink: '',
        trainerTozai: '',
        trainerJvnCode: '',
        trainerComment: '',
        jockey: '',  // TARGETには騎手情報なし
        totalRaces: 0,
        updatedAt: '',
      };
      horseName = targetData.name;
      targetKettoNum = targetData.horseId;  // 血統登録番号（10桁）
      console.log(`[IntegratedHorseReader] Found horse: ${horseName} (KettoNum=${targetKettoNum})`);
    } else {
      // 2. TARGETにない場合は既知の馬名を使用
      if (knownHorseName) {
        basic = {
          id: horseId,
          name: knownHorseName,
          age: '',
          trainer: '',
          trainerId: '',
          trainerLink: '',
          trainerTozai: '',
          trainerJvnCode: '',
          trainerComment: '',
          jockey: '',
          totalRaces: 0,
          updatedAt: '',
        };
        horseName = knownHorseName;
        
        // MDから詳細情報を再取得（あれば）
        if (profilePath && fs.existsSync(profilePath)) {
          const content = fs.readFileSync(profilePath, 'utf-8');
          basic = extractBasicInfoFromMd(content, horseId);
        }
      } else {
        // フォールバック: 直近のintegrated_*.jsonから馬名を検索（初出走馬対応）
        const recentData = findHorseNameFromRecentRaces(horseId);
        if (recentData) {
          console.log(`[IntegratedHorseReader] Found horse from recent races: ${recentData.horseName} (KettoNum=${recentData.kettoNum})`);
          horseName = recentData.horseName;
          targetKettoNum = recentData.kettoNum;

          // 馬名が見つかったのでTARGETから再検索
          const retryTarget = await findHorseFromTarget(horseId, recentData.horseName);
          if (retryTarget) {
            const age = calculateHorseAge(retryTarget.birthDate);
            basic = {
              id: horseId,
              name: retryTarget.name,
              age: `${retryTarget.sex}${age}`,
              trainer: retryTarget.trainerName,
              trainerId: '',
              trainerLink: '',
              trainerTozai: '',
              trainerJvnCode: '',
              trainerComment: '',
              jockey: '',
              totalRaces: 0,
              updatedAt: '',
            };
            horseName = retryTarget.name;
            targetKettoNum = retryTarget.horseId;
          } else {
            basic = {
              id: horseId,
              name: recentData.horseName,
              age: '',
              trainer: '',
              trainerId: '',
              trainerLink: '',
              trainerTozai: '',
              trainerJvnCode: '',
              trainerComment: '',
              jockey: '',
              totalRaces: 0,
              updatedAt: '',
            };
          }
        } else {
          // いずれのソースにもない場合は最小限の情報で初期化
          basic = {
            id: horseId,
            name: '',
            age: '',
            trainer: '',
            trainerId: '',
            trainerLink: '',
            trainerTozai: '',
            trainerJvnCode: '',
            trainerComment: '',
            jockey: '',
            totalRaces: 0,
            updatedAt: '',
          };
        }
      }
    }

    // 3. MDから更新日時を取得（TARGETで取得した場合）
    if (targetData && profilePath && fs.existsSync(profilePath)) {
      const content = fs.readFileSync(profilePath, 'utf-8');
      const updateMatch = content.match(/\*最終更新:\s*([^*]+)\*/);
      if (updateMatch) {
        basic.updatedAt = updateMatch[1].trim();
      }
    }

    // 4. 過去レースデータを収集
    // TARGET SE_DATAには血統登録番号（10桁）、競馬ブックには競馬ブックID（7桁）を使用
    const pastRaces = await collectPastRaces(horseId, horseName, 30, targetKettoNum);
    basic.totalRaces = pastRaces.length;

    // 騎手情報・調教師情報を最新レースから補完
    if (pastRaces.length > 0) {
      const latestRace = pastRaces[0];
      
      // 騎手情報補完
      if (!basic.jockey && latestRace.jockey) {
        basic.jockey = latestRace.jockey;
      }
      
      // 調教師情報補完（競馬ブックデータから取得）
      if (!basic.trainerId && latestRace.trainerId) {
        basic.trainerId = latestRace.trainerId;
        basic.trainerLink = latestRace.trainerLink || '';
        basic.trainerTozai = latestRace.trainerTozai || '';
        // 調教師名がTARGETデータと異なる場合は競馬ブックのものを使用
        if (latestRace.trainer && !basic.trainer) {
          basic.trainer = latestRace.trainer;
        }
      }
      
      // 調教師インデックスからJRA-VANコードとコメントを取得
      if (basic.trainerId) {
        const trainerInfo = getTrainerInfo(basic.trainerId);
        if (trainerInfo) {
          basic.trainerJvnCode = trainerInfo.jvnCode;
          basic.trainerComment = trainerInfo.comment;
          // 所属情報が未設定の場合はインデックスから補完
          if (!basic.trainerTozai && trainerInfo.tozai) {
            basic.trainerTozai = trainerInfo.tozai;
          }
        }
      }
    }

    // 5. 統計を計算
    const stats = calculateStats(pastRaces);

    const totalElapsed = Date.now() - totalStart;
    if (totalElapsed > 1000) {
      console.log(`[IntegratedHorseReader] getIntegratedHorseData total: ${totalElapsed}ms (${pastRaces.length} races)`);
    }

    return {
      basic,
      pastRaces,
      stats,
      userMemo,
    };
  } catch (error) {
    console.error('[IntegratedHorseReader] データ取得エラー:', error);
    return null;
  }
}

/**
 * 馬名で検索して馬IDリストを返す
 */
export async function searchHorsesByName(query: string): Promise<Array<{ id: string; name: string; age: string }>> {
  const results: Array<{ id: string; name: string; age: string }> = [];

  if (!fs.existsSync(HORSES_DIR)) {
    return results;
  }

  const normalizedQuery = query.toLowerCase();
  const files = fs.readdirSync(HORSES_DIR);

  for (const file of files) {
    if (!file.endsWith('.md')) continue;

    const match = file.match(/^(\d+)_(.+)\.md$/);
    if (!match) continue;

    const [, id, name] = match;

    if (name.toLowerCase().includes(normalizedQuery)) {
      // 性齢を抽出
      const filePath = path.join(HORSES_DIR, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const ageMatch = content.match(/性齢[:\s]*\*?\*?(\S+)\*?\*?/);
      const age = ageMatch ? ageMatch[1] : '';

      results.push({ id, name, age });
    }

    if (results.length >= 50) break;
  }

  return results;
}
