/**
 * 調教サマリー読み込みユーティリティ
 * 
 * Z:\KEIBA-CICD\data2\races\{year}\{month}\{day}\temp\training_summary.json
 * を読み込み、馬名をキーにしたマップを返す
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import { getHorseRaceResultsFromTarget } from './target-race-result-reader';
import {
  generateTrainingSummary,
  isTrainingDataAvailable,
  getTrainingDateRanges,
  type TrainingSummary,
} from './target-training-reader';

const DATA_ROOT = DATA3_ROOT;

// 前走調教キャッシュ（日付 -> 馬名 -> 調教データ）
const previousTrainingCache = new Map<string, Record<string, TrainingSummaryData>>();

export interface TrainingSummaryData {
  lapRank?: string;
  timeRank?: string;
  detail?: string;
  horseName?: string;
  kettoNum?: string;
  trainerName?: string;
  // 最終追い切り（当週水・木）
  finalLocation?: string;   // 坂 / コ
  finalSpeed?: string;      // ◎ = 好タイム
  finalLap?: string;        // S+ / A- など
  finalTime4F?: number;
  finalLap1?: number;
  // 土日追い切り（前週土・日、両方あればタイムが早いほう）
  weekendLocation?: string;
  weekendSpeed?: string;
  weekendLap?: string;
  weekendTime4F?: number;
  weekendLap1?: number;
  // 1週前追い切り（前週水・木）
  weekAgoLocation?: string;
  weekAgoSpeed?: string;
  weekAgoLap?: string;
  weekAgoTime4F?: number;
  weekAgoLap1?: number;
  // 前走調教情報
  previousRaceDate?: string;    // 前走日付（YYYY-MM-DD形式）
  previousDetail?: string;      // 前走調教詳細
  previousLapRank?: string;     // 前走ラップランク
  previousFinalSpeed?: string;  // 前走最終追切スピード
}

export interface TrainingSummaryFile {
  meta: {
    date: string;
    created_at: string;
    ranges: {
      finalStart: string;
      finalEnd: string;
      weekAgoStart: string;
      weekAgoEnd: string;
    };
    count: number;
  };
  summaries: Record<string, TrainingSummaryData>;
}

/**
 * 指定日の調教サマリーを読み込む
 * @param date 日付（YYYY-MM-DD形式）
 * @returns 馬名をキーにした調教サマリーマップ
 */
export async function getTrainingSummaryMap(date: string): Promise<Record<string, TrainingSummaryData>> {
  try {
    // 日付をパース（YYYY-MM-DD → year, month, day）
    const [year, month, day] = date.split('-');
    if (!year || !month || !day) {
      return {};
    }

    const filePath = path.join(
      DATA_ROOT,
      'races',
      year,
      month,
      day,
      'temp',
      'training_summary.json'
    );

    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      const data: TrainingSummaryFile = JSON.parse(content);
      console.log(`[TrainingSummaryReader] Loaded ${Object.keys(data.summaries).length} summaries from ${filePath}`);
      return data.summaries;
    }

    // ファイルがない場合: CK_DATAからオンデマンド生成
    if (!isTrainingDataAvailable()) {
      console.log(`[TrainingSummaryReader] File not found and CK_DATA unavailable: ${filePath}`);
      return {};
    }

    const dateStr = `${year}${month}${day}`;
    console.log(`[TrainingSummaryReader] Auto-generating training summary for ${dateStr}...`);
    const summaries = await generateTrainingSummary(dateStr);

    if (summaries.length === 0) {
      console.log(`[TrainingSummaryReader] No training data found for ${dateStr}`);
      return {};
    }

    // 馬名をキーにしたマップ形式に変換
    const summaryMap: Record<string, TrainingSummaryData> = {};
    for (const s of summaries) {
      summaryMap[s.horseName] = s as TrainingSummaryData;
    }

    // 次回用にファイル保存
    const targetDir = path.join(DATA_ROOT, 'races', year, month, day, 'temp');
    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }
    const outputData: TrainingSummaryFile = {
      meta: {
        date: dateStr,
        created_at: new Date().toISOString(),
        ranges: getTrainingDateRanges(dateStr),
        count: summaries.length,
      },
      summaries: summaryMap,
    };
    fs.writeFileSync(filePath, JSON.stringify(outputData, null, 2), 'utf-8');
    console.log(`[TrainingSummaryReader] Auto-generated and saved ${summaries.length} summaries to ${filePath}`);

    return summaryMap;
  } catch (error) {
    console.error('[TrainingSummaryReader] Error:', error);
    return {};
  }
}

/**
 * 調教サマリーファイルが存在するかチェック
 */
export function hasTrainingSummary(date: string): boolean {
  try {
    const [year, month, day] = date.split('-');
    if (!year || !month || !day) {
      return false;
    }

    const filePath = path.join(
      DATA_ROOT,
      'races',
      year,
      month,
      day,
      'temp',
      'training_summary.json'
    );

    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

/**
 * 指定日の training_summary.json を同期的に読み込む（キャッシュあり）
 */
function loadTrainingSummarySync(dateYmd: string): Record<string, TrainingSummaryData> {
  // dateYmd形式: YYYYMMDD or YYYY-MM-DD
  const normalized = dateYmd.includes('-') ? dateYmd : 
    `${dateYmd.slice(0, 4)}-${dateYmd.slice(4, 6)}-${dateYmd.slice(6, 8)}`;
  
  if (previousTrainingCache.has(normalized)) {
    return previousTrainingCache.get(normalized)!;
  }
  
  try {
    const [year, month, day] = normalized.split('-');
    const filePath = path.join(
      DATA_ROOT,
      'races',
      year,
      month,
      day,
      'temp',
      'training_summary.json'
    );
    
    if (!fs.existsSync(filePath)) {
      previousTrainingCache.set(normalized, {});
      return {};
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    const data: TrainingSummaryFile = JSON.parse(content);
    previousTrainingCache.set(normalized, data.summaries);
    return data.summaries;
  } catch {
    previousTrainingCache.set(normalized, {});
    return {};
  }
}

/**
 * 前走日付を取得（TARGET SE_DATA インデックス使用）
 * @param kettoNum 血統番号
 * @param currentRaceDate 現在のレース日付（YYYY-MM-DD形式）
 * @returns 前走日付（YYYY-MM-DD形式）またはnull
 */
export async function getPreviousRaceDate(kettoNum: string, currentRaceDate: string): Promise<string | null> {
  if (!kettoNum) return null;
  
  try {
    const results = await getHorseRaceResultsFromTarget(kettoNum);
    if (results.length === 0) return null;
    
    // 現在のレース日付をYYYYMMDD形式に変換
    const currentDateYmd = currentRaceDate.replace(/-/g, '');
    
    // 日付降順でソート
    const sortedResults = results.sort((a, b) => b.raceDate.localeCompare(a.raceDate));
    
    // 現在のレース日付より前のレースを探す
    for (const result of sortedResults) {
      if (result.raceDate < currentDateYmd) {
        // YYYYMMDD を YYYY-MM-DD に変換
        return `${result.raceDate.slice(0, 4)}-${result.raceDate.slice(4, 6)}-${result.raceDate.slice(6, 8)}`;
      }
    }
    
    return null;
  } catch {
    return null;
  }
}

/**
 * 馬名からkettoNumを検索（直近のtraining_summary.jsonをスキャン）
 * horse_name_index.jsonに登録がない初出走馬のフォールバック用
 * @param horseName 馬名
 * @returns kettoNum または null
 */
export function findKettoNumFromRecentTraining(horseName: string): string | null {
  const normalized = horseName.replace(/^[\(（][外地父市][）\)]/g, '');

  // 直近のレース日付ディレクトリを探索（最新から最大10日分）
  const racesDir = path.join(DATA_ROOT, 'races');
  try {
    const years = fs.readdirSync(racesDir).filter(d => /^\d{4}$/.test(d)).sort().reverse();
    let checked = 0;
    for (const year of years) {
      const months = fs.readdirSync(path.join(racesDir, year)).filter(d => /^\d{2}$/.test(d)).sort().reverse();
      for (const month of months) {
        const days = fs.readdirSync(path.join(racesDir, year, month)).filter(d => /^\d{2}$/.test(d)).sort().reverse();
        for (const day of days) {
          if (checked >= 10) return null;
          const dateKey = `${year}-${month}-${day}`;
          const summaries = loadTrainingSummarySync(dateKey);
          const summary = summaries[horseName] || summaries[normalized];
          if (summary?.kettoNum) {
            return summary.kettoNum;
          }
          checked++;
        }
      }
    }
  } catch {
    // ディレクトリが存在しない等
  }
  return null;
}

/**
 * 馬の前走調教データを取得
 * @param horseName 馬名
 * @param kettoNum 血統番号
 * @param currentRaceDate 現在のレース日付（YYYY-MM-DD形式）
 * @returns 前走の調教データ
 */
export async function getPreviousTraining(
  horseName: string, 
  kettoNum: string, 
  currentRaceDate: string
): Promise<TrainingSummaryData | null> {
  const prevDate = await getPreviousRaceDate(kettoNum, currentRaceDate);
  if (!prevDate) return null;
  
  const summaries = loadTrainingSummarySync(prevDate);
  return summaries[horseName] || null;
}

/**
 * 複数馬の前走調教データを一括取得（レースページ用）
 * @param horses 馬情報の配列（horseName, kettoNum）
 * @param currentRaceDate 現在のレース日付（YYYY-MM-DD形式）
 * @returns 馬名をキーにした前走調教マップ
 */
export async function getPreviousTrainingBatch(
  horses: Array<{ horseName: string; kettoNum: string }>,
  currentRaceDate: string
): Promise<Record<string, { date: string; training: TrainingSummaryData }>> {
  const result: Record<string, { date: string; training: TrainingSummaryData }> = {};
  
  // 並列で前走日付を取得
  const prevDates = await Promise.all(
    horses.map(async (h) => ({
      horseName: h.horseName,
      kettoNum: h.kettoNum,
      prevDate: await getPreviousRaceDate(h.kettoNum, currentRaceDate)
    }))
  );

  // デバッグ: 前走日付取得の成功/失敗を確認
  const successCount = prevDates.filter(d => d.prevDate).length;
  const failCount = prevDates.filter(d => !d.prevDate).length;
  console.log(`[DEBUG] Previous race date lookup: ${successCount} success, ${failCount} failed`);

  if (failCount > 0 && failCount <= 5) {
    // 失敗例を5件まで表示
    const failedHorses = prevDates.filter(d => !d.prevDate).slice(0, 5);
    console.log('[DEBUG] Failed horses (sample):', failedHorses.map(h => ({
      name: h.horseName,
      kettoNum: h.kettoNum
    })));
  }

  // 前走日付ごとにグループ化
  const dateGroups = new Map<string, string[]>();
  for (const { horseName, prevDate } of prevDates) {
    if (prevDate) {
      if (!dateGroups.has(prevDate)) {
        dateGroups.set(prevDate, []);
      }
      dateGroups.get(prevDate)!.push(horseName);
    }
  }

  // デバッグ: グループ化された日付を表示
  console.log(`[DEBUG] Date groups: ${dateGroups.size} unique dates`);
  if (dateGroups.size > 0) {
    console.log('[DEBUG] Dates:', Array.from(dateGroups.keys()).sort());
  }

  // 各日付の training_summary.json を読み込み（同期読み込みのみ、オンデマンド生成はしない）
  // 注意: 過去日付のオンデマンド生成は数十日分のCK_DATAパースを引き起こし
  // ページロードが100秒超になるため、既存ファイルのみ参照する
  let totalMatched = 0;
  let totalMissing = 0;
  for (const [date, horseNames] of dateGroups) {
    const summaries = loadTrainingSummarySync(date);
    const summaryCount = Object.keys(summaries).length;

    // デバッグ: ファイル読み込み結果
    console.log(`[DEBUG] Date ${date}: ${summaryCount} summaries loaded, ${horseNames.length} horses to match`);

    let matchedInThisDate = 0;
    const missingHorses: string[] = [];

    for (const horseName of horseNames) {
      if (summaries[horseName]) {
        result[horseName] = {
          date,
          training: summaries[horseName]
        };
        matchedInThisDate++;
      } else {
        missingHorses.push(horseName);
      }
    }

    totalMatched += matchedInThisDate;
    totalMissing += missingHorses.length;

    if (missingHorses.length > 0) {
      console.log(`[DEBUG] Date ${date}: ${missingHorses.length} horses not found in summary`);
      if (missingHorses.length <= 3) {
        console.log('[DEBUG] Missing horses:', missingHorses);
      }
    }
  }

  console.log(`[TrainingSummaryReader] Previous training loaded: ${Object.keys(result).length}/${horses.length} horses`);
  console.log(`[DEBUG] Summary: ${successCount} dates found, ${totalMatched} matched, ${totalMissing} missing from files, ${failCount} no previous race`);
  return result;
}
