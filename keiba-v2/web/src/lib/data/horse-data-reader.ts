/**
 * 馬データリーダー — JRA-VANベース3層アーキテクチャ
 *
 * Layer 1 (JRA-VAN Base):
 *   - Horse master JSON (data3/masters/horses/{ketto_num}.json) ← 高速
 *   - UM binary (C:/TFJV/UM_DATA) ← フォールバック
 *   - SE binary (C:/TFJV/SE_DATA) ← 過去レース成績
 *
 * Layer 2 (race_*.json + kb_ext Enrichment): optional, graceful degradation
 *   - race_*.json → 距離/馬場/頭数/前3F/レース名/クラス
 *   - kb_ext_{race_id}.json → 印/短評/調教矢印/厩舎コメント/寸評
 *   - training_summary.json → 調教タイム詳細
 *
 * Layer 3 (User Data):
 *   - TARGET UMA_COM → ユーザーコメント
 */

import fs from 'fs';
import { promises as fsp } from 'fs';
import path from 'path';
import { findHorseFromTarget, calculateHorseAge } from './target-horse-reader';
import { getHorseRaceResultsFromTarget, isTargetSeDataAvailable, type TargetRaceResult } from './target-race-result-reader';
import { getRaceFilesForHorse, isIndexAvailable } from './horse-race-index';
import { getTrainerInfo } from './trainer-index';
import { DATA3_ROOT } from '@/lib/config';
import { getDbRaceInfoByDate, trackTypeToJapanese, type DbRaceInfo } from './db-race';

import type {
  HorseBasicInfo,
  HorseRaceResult,
  HorseStats,
  StatGroup,
  IntegratedHorseData,
} from './integrated-horse-reader';

// ============================================================
// キャッシュ
// ============================================================

// horse_name_index.json キャッシュ
let horseNameIndexCache: Record<string, string> | null = null;

// training_summary.json キャッシュ（日付 → 馬名 → 調教データ）
interface TrainingSummaryEntry {
  detail?: string;
  lapRank?: string;
  finalSpeed?: string;
}
const trainingSummaryCache = new Map<string, Map<string, TrainingSummaryEntry>>();


// ============================================================
// ID解決
// ============================================================

/**
 * 馬名インデックスを読み込み（キャッシュ付き）
 * 構造: { metadata: {...}, name_to_id: { "ドウデュース": "2019105283", ... } }
 */
function loadHorseNameIndex(): Record<string, string> {
  if (horseNameIndexCache) return horseNameIndexCache;

  const indexPath = path.join(DATA3_ROOT, 'indexes', 'horse_name_index.json');
  if (!fs.existsSync(indexPath)) {
    console.warn('[HorseDataReader] horse_name_index.json not found');
    return {};
  }

  try {
    const content = fs.readFileSync(indexPath, 'utf-8');
    const data = JSON.parse(content);
    horseNameIndexCache = data.name_to_id || {};
    return horseNameIndexCache ?? {};
  } catch (e) {
    console.error('[HorseDataReader] Failed to load horse_name_index.json:', e);
    return {};
  }
}

/**
 * IDを10桁ketto_numに解決
 *
 * 受け入れるフォーマット:
 * - 10桁 ketto_num → そのまま
 * - 7桁 keibabook ID → 先頭0埋めで10桁化
 * - 馬名（文字列） → horse_name_index.json で検索
 */
export function resolveToKettoNum(id: string): string | null {
  // 10桁 ketto_num
  if (/^\d{10}$/.test(id)) {
    return id;
  }

  // 7桁以下の数字 → 先頭0埋めで10桁化
  if (/^\d{1,9}$/.test(id)) {
    const padded = id.padStart(10, '0');
    // master JSON存在確認
    const masterPath = path.join(DATA3_ROOT, 'masters', 'horses', `${padded}.json`);
    if (fs.existsSync(masterPath)) {
      return padded;
    }
    // master JSONがなくてもパディングして返す（UM binary検索のため）
    return padded;
  }

  // 馬名 → horse_name_index で逆引き
  const nameIndex = loadHorseNameIndex();
  const kettoNum = nameIndex[id];
  if (kettoNum) {
    return kettoNum;
  }

  return null;
}

// ============================================================
// Layer 1: JRA-VAN Base
// ============================================================

/**
 * Horse master JSONから基本情報を取得（高速パス）
 */
async function getProfileFromMasterJSON(kettoNum: string): Promise<HorseBasicInfo | null> {
  const masterPath = path.join(DATA3_ROOT, 'masters', 'horses', `${kettoNum}.json`);
  try {
    const content = await fsp.readFile(masterPath, 'utf-8');
    const data = JSON.parse(content);
    const age = calculateHorseAge(data.birth_date || '');
    return {
      id: kettoNum,
      name: data.name || '',
      age: `${data.sex_name || ''}${age}`,
      trainer: data.trainer_name || '',
      trainerId: '',
      trainerLink: '',
      trainerTozai: data.tozai_name || '',
      trainerJvnCode: data.trainer_code || '',
      trainerComment: '',
      jockey: '',
      totalRaces: 0,
      updatedAt: '',
    };
  } catch {
    return null;
  }
}

/**
 * UM binaryから基本情報を取得（フォールバック）
 */
async function getProfileFromUMBinary(kettoNum: string, horseName?: string): Promise<HorseBasicInfo | null> {
  const targetData = await findHorseFromTarget(kettoNum, horseName);
  if (!targetData) return null;

  const age = calculateHorseAge(targetData.birthDate);
  return {
    id: targetData.horseId,
    name: targetData.name,
    age: `${targetData.sex}${age}`,
    trainer: targetData.trainerName,
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

/**
 * Layer 1: 馬基本情報を取得
 * 優先順位: Horse master JSON → UM binary
 */
async function getHorseBaseProfile(kettoNum: string): Promise<HorseBasicInfo | null> {
  // 1st: Horse master JSON (高速)
  const fromJSON = await getProfileFromMasterJSON(kettoNum);
  if (fromJSON) return fromJSON;

  // 2nd: UM binary (フォールバック)
  return await getProfileFromUMBinary(kettoNum);
}

/**
 * TARGET SE_DATAからHorseRaceResult形式に変換
 */
function targetResultToHorseRaceResult(target: TargetRaceResult): HorseRaceResult {
  const dateStr = target.raceDate;
  const formattedDate = dateStr.length === 8
    ? `${dateStr.substring(0, 4)}/${dateStr.substring(4, 6)}/${dateStr.substring(6, 8)}`
    : dateStr;

  const corners = [target.corner1, target.corner2, target.corner3, target.corner4]
    .filter(c => c > 0)
    .join('-');

  return {
    date: formattedDate,
    track: target.venue,
    raceId: target.raceId,
    raceNumber: target.raceNumber,
    raceName: '',
    targetRaceId: target.raceId,
    raceClass: '',
    distance: '',
    condition: '',
    headCount: 0,
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
    first3f: '',
    last3f: target.last3f,
    corner4Pos: target.corner4 > 0 ? String(target.corner4) : '',
    cornerPositions: corners,
    odds: String(target.odds),
    // Layer 2で上書き
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
 * Layer 1: SE_DATAから過去レース成績を取得
 */
async function getCareerResults(kettoNum: string, maxRaces: number = 30): Promise<HorseRaceResult[]> {
  if (!isTargetSeDataAvailable()) return [];

  try {
    const targetResults = await getHorseRaceResultsFromTarget(kettoNum);
    const results: HorseRaceResult[] = [];
    for (const tr of targetResults) {
      if (results.length >= maxRaces) break;
      results.push(targetResultToHorseRaceResult(tr));
    }
    return results;
  } catch (e) {
    console.error('[HorseDataReader] SE_DATA error:', e);
    return [];
  }
}

// ============================================================
// Layer 2: keibabook Enrichment
// ============================================================

/**
 * 指定日の training_summary.json を読み込み
 */
async function loadTrainingSummary(datePath: string): Promise<Map<string, TrainingSummaryEntry>> {
  if (trainingSummaryCache.has(datePath)) {
    return trainingSummaryCache.get(datePath)!;
  }

  const result = new Map<string, TrainingSummaryEntry>();
  try {
    const [year, month, day] = datePath.split('/');
    const filePath = path.join(DATA3_ROOT, 'races', year, month, day, 'temp', 'training_summary.json');
    const content = await fsp.readFile(filePath, 'utf-8');
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
  } catch {
    // ファイルが存在しない場合は空
  }

  trainingSummaryCache.set(datePath, result);
  return result;
}

// race_*.json キャッシュ（ファイルパス → パース済みデータ）
const raceJsonCache = new Map<string, Record<string, unknown>>();

/**
 * race_*.json と kb_ext_*.json の2段階で付加情報を抽出
 *
 * Step 1: race_*.json からレースレベル情報を取得
 *   - distance, track_type, track_condition, num_runners, pace.s3, race_name, grade
 *   - entries[] から ketto_num で馬を特定 → umaban を取得
 *
 * Step 2: kb_ext_{race_id}.json から馬固有情報を取得
 *   - entries[str(umaban)] → honshi_mark, training_data, short_comment, etc.
 */
async function extractRaceAndKbEnrichment(
  raceFilePath: string,
  kettoNum: string,
): Promise<Partial<HorseRaceResult> | null> {
  try {
    // Step 1: race_*.json を読み込み（キャッシュ付き）
    let raceData: Record<string, unknown>;
    if (raceJsonCache.has(raceFilePath)) {
      raceData = raceJsonCache.get(raceFilePath)!;
    } else {
      const content = await fsp.readFile(raceFilePath, 'utf-8');
      raceData = JSON.parse(content);
      raceJsonCache.set(raceFilePath, raceData);
    }

    const raceId = raceData.race_id as string || '';
    const entries = raceData.entries as Array<Record<string, unknown>> || [];

    // ketto_numで馬を検索してumabanを取得
    const horseEntry = entries.find(
      e => String(e.ketto_num || '') === kettoNum || String(e.horse_id || '') === kettoNum
    );
    if (!horseEntry) return null;

    const umaban = horseEntry.umaban as number;
    let trackType = raceData.track_type as string || '';
    let distance = raceData.distance as number || 0;
    let trackCondition = raceData.track_condition as string || '';
    let raceName = raceData.race_name as string || '';
    const pace = raceData.pace as Record<string, unknown> || {};

    // DB補完: race_*.jsonのtrack_type/distanceが空の場合、RACE_SHOSAIから取得
    if ((!trackType || !distance) && raceId) {
      const datePrefix = raceId.substring(0, 8); // YYYYMMDD
      const dbInfo = await getDbRaceInfoByDate(datePrefix);
      const dbRace = dbInfo.get(raceId);
      if (dbRace) {
        if (!trackType) trackType = dbRace.trackType;
        if (!distance) distance = dbRace.distance;
        if (!trackCondition) {
          trackCondition = trackType === 'turf' ? dbRace.shibaBaba
            : trackType === 'dirt' ? dbRace.dirtBaba : '';
        }
        if (!raceName) raceName = dbRace.raceName;
      }
    }

    // 距離表示文字列を組み立て: "芝1600" / "ダ1200"
    let distanceStr = '';
    if (distance > 0) {
      const prefix = trackTypeToJapanese(trackType);
      distanceStr = `${prefix}${distance}`;
    }

    const enrichment: Partial<HorseRaceResult> = {
      raceId,
      raceName,
      raceClass: raceData.grade as string || '',
      distance: distanceStr,
      condition: trackCondition,
      headCount: raceData.num_runners as number || entries.length,
      first3f: pace.s3 ? String(pace.s3) : '',
      // JRDB指標（race_*.jsonのentryから取得）
      jrdb_pre_idm: horseEntry.jrdb_pre_idm as number ?? null,
      jrdb_sogo_idx: horseEntry.jrdb_sogo_idx as number ?? null,
      jrdb_training_idx: horseEntry.jrdb_training_idx as number ?? null,
      jrdb_stable_idx: horseEntry.jrdb_stable_idx as number ?? null,
      jrdb_gekisou_idx: horseEntry.jrdb_gekisou_idx as number ?? null,
      jrdb_idm: horseEntry.jrdb_idm as number ?? null,
    };

    // Step 2: kb_ext_{race_id}.json を検索
    const pathMatch = raceFilePath.match(/races[/\\](\d{4})[/\\](\d{2})[/\\](\d{2})/);
    if (pathMatch && raceId) {
      const [, year, month, day] = pathMatch;
      const kbExtPath = path.join(DATA3_ROOT, 'keibabook', year, month, day, `kb_ext_${raceId}.json`);

      try {
        const kbContent = await fsp.readFile(kbExtPath, 'utf-8');
        const kbData = JSON.parse(kbContent);
        const kbEntries = kbData.entries as Record<string, Record<string, unknown>> || {};
        const kbEntry = kbEntries[String(umaban)];

        if (kbEntry) {
          const trainingData = kbEntry.training_data as Record<string, string> || {};
          const stableComment = kbEntry.stable_comment as Record<string, string> || {};
          const previousRace = kbEntry.previous_race_interview as Record<string, string> || {};

          enrichment.honshiMark = kbEntry.honshi_mark as string || '';
          enrichment.shortComment = kbEntry.short_comment as string || '';
          enrichment.trainingArrow = kbEntry.training_arrow as string || '';
          enrichment.trainingComment = trainingData.short_review || '';
          enrichment.attackExplanation = trainingData.attack_explanation || '';
          enrichment.stableComment = stableComment.comment || '';
          enrichment.sunpyou = kbEntry.sunpyo as string || '';
          // 前半3F: kb_extの個馬first_3fをフォールバック（race JSONのpace.s3が優先）
          if (!enrichment.first3f && kbEntry.first_3f) {
            enrichment.first3f = String(kbEntry.first_3f);
          }
          // seiseki直接データ優先、syoin(前走インタビュー)にフォールバック
          enrichment.resultComment = (kbEntry.interview as string) || previousRace.interview || '';
          enrichment.resultMemo = (kbEntry.next_race_memo as string) || previousRace.next_race_memo || '';
        }
      } catch {
        // kb_ext not found — graceful degradation
      }
    }

    return enrichment;
  } catch {
    return null;
  }
}

/**
 * Layer 2: race_*.json + kb_ext enrichmentを全レースに適用
 *
 * @param baseRaces Layer 1のSE_DATA結果
 * @param kettoNum 10桁ketto_num（horse_race_index検索用）
 * @param horseName 馬名（training_summary検索用）
 */
async function enrichWithKeibabook(
  baseRaces: HorseRaceResult[],
  kettoNum: string,
  horseName: string
): Promise<HorseRaceResult[]> {
  if (baseRaces.length === 0) return baseRaces;

  // horse_race_index からレースファイル一覧を取得
  const enrichByMatchKey = new Map<string, Partial<HorseRaceResult>>();
  const enrichByRaceId = new Map<string, Partial<HorseRaceResult>>();

  if (isIndexAvailable()) {
    const raceFiles = getRaceFilesForHorse(kettoNum);

    for (const filePath of raceFiles) {
      const enrichment = await extractRaceAndKbEnrichment(filePath, kettoNum);
      if (enrichment && enrichment.raceId) {
        enrichByRaceId.set(enrichment.raceId, enrichment);
        // race_*.json から日付とrace_numberを取得してマッチキーを作成
        const raceData = raceJsonCache.get(filePath);
        if (raceData) {
          const dateStr = raceData.date as string || ''; // "2025-01-05"
          const venueName = raceData.venue_name as string || '';
          const raceNumber = raceData.race_number as number || 0;
          if (dateStr && venueName) {
            const matchKey = `${dateStr.replace(/-/g, '')}|${venueName}|${raceNumber}`;
            enrichByMatchKey.set(matchKey, enrichment);
          }
        }
      }
    }
  }

  // SE_DATAベースの各レースにenrichmentをマージ
  for (let i = 0; i < baseRaces.length; i++) {
    const race = baseRaces[i];
    // date="2025/01/05", track="中山", raceNumber=1
    const matchKey = `${race.date.replace(/\//g, '')}|${race.track}|${race.raceNumber}`;
    let enrichment = enrichByMatchKey.get(matchKey) || enrichByRaceId.get(race.raceId);

    // フォールバック: インデックスに無いレースは直接ファイルパスを構築
    // SE raceId(12桁): YYYY + kai(2) + venue(2) + nichi(2) + raceNo(2)
    // ファイル raceId(16桁): YYYYMMDD + venue(2) + kai(2) + nichi(2) + raceNo(2)
    if (!enrichment && race.raceId && race.date) {
      const [y, m, d] = race.date.split('/');
      if (y && m && d && race.raceId.length === 12) {
        const kai = race.raceId.substring(4, 6);
        const venue = race.raceId.substring(6, 8);
        const nichi = race.raceId.substring(8, 10);
        const raceNo = race.raceId.substring(10, 12);
        const fileRaceId = `${y}${m}${d}${venue}${kai}${nichi}${raceNo}`;
        const raceFilePath = path.join(DATA3_ROOT, 'races', y, m, d, `race_${fileRaceId}.json`);

        enrichment = await extractRaceAndKbEnrichment(raceFilePath, kettoNum) ?? undefined;
      }
    }

    if (enrichment) {
      baseRaces[i] = {
        ...race,
        raceId: enrichment.raceId || race.raceId,
        raceName: enrichment.raceName || race.raceName,
        raceClass: enrichment.raceClass || race.raceClass,
        distance: enrichment.distance || race.distance,
        condition: enrichment.condition || race.condition,
        headCount: enrichment.headCount || race.headCount,
        first3f: enrichment.first3f || race.first3f,
        honshiMark: enrichment.honshiMark ?? race.honshiMark,
        shortComment: enrichment.shortComment ?? race.shortComment,
        trainingArrow: enrichment.trainingArrow ?? race.trainingArrow,
        trainingComment: enrichment.trainingComment ?? race.trainingComment,
        attackExplanation: enrichment.attackExplanation ?? race.attackExplanation,
        stableComment: enrichment.stableComment ?? race.stableComment,
        sunpyou: enrichment.sunpyou ?? race.sunpyou,
        resultMemo: enrichment.resultMemo ?? race.resultMemo,
        resultComment: enrichment.resultComment ?? race.resultComment,
        // JRDB指標
        jrdb_pre_idm: enrichment.jrdb_pre_idm ?? race.jrdb_pre_idm,
        jrdb_sogo_idx: enrichment.jrdb_sogo_idx ?? race.jrdb_sogo_idx,
        jrdb_training_idx: enrichment.jrdb_training_idx ?? race.jrdb_training_idx,
        jrdb_stable_idx: enrichment.jrdb_stable_idx ?? race.jrdb_stable_idx,
        jrdb_gekisou_idx: enrichment.jrdb_gekisou_idx ?? race.jrdb_gekisou_idx,
        jrdb_idm: enrichment.jrdb_idm ?? race.jrdb_idm,
      };
    }
  }

  // training_summary.json から調教タイム詳細を追加
  for (const result of baseRaces) {
    const trainingSummary = await loadTrainingSummary(result.date);
    const trainingEntry = trainingSummary.get(horseName);
    if (trainingEntry) {
      result.trainingDetail = trainingEntry.detail || '';
      result.trainingLapRank = trainingEntry.lapRank || '';
      result.trainingFinalSpeed = trainingEntry.finalSpeed || '';
    }
  }

  return baseRaces;
}

// ============================================================
// 統計計算
// ============================================================

/**
 * 過去レースから成績統計を計算
 */
function calculateStats(pastRaces: HorseRaceResult[]): HorseStats {
  const createEmpty = (): StatGroup => ({
    races: 0, wins: 0, seconds: 0, thirds: 0, winRate: 0, placeRate: 0, showRate: 0,
  });

  const stats: HorseStats = {
    total: createEmpty(),
    turf: createEmpty(),
    dirt: createEmpty(),
    byDistance: {},
    byCondition: {},
    byFrame: {},
    byFieldSize: {},
  };

  for (const race of pastRaces) {
    const pos = parseInt(race.finishPosition, 10);
    if (isNaN(pos)) continue;

    const isTurf = race.distance.includes('芝');
    const isDirt = race.distance.includes('ダ') || race.distance.includes('D');

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

    const condKey = race.condition || '不明';

    const frame = race.frameNumber;
    let frameKey = '';
    if (frame >= 1 && frame <= 3) frameKey = '内枠(1-3)';
    else if (frame >= 4 && frame <= 6) frameKey = '中枠(4-6)';
    else if (frame >= 7) frameKey = '外枠(7-8)';

    const headCount = race.headCount;
    let fieldSizeKey = '';
    if (headCount > 0) {
      if (headCount <= 11) fieldSizeKey = '少頭数(～11頭)';
      else if (headCount <= 15) fieldSizeKey = '中頭数(12-15頭)';
      else fieldSizeKey = '多頭数(16頭～)';
    }

    const update = (g: StatGroup) => {
      g.races++;
      if (pos === 1) g.wins++;
      if (pos <= 2) g.seconds++;
      if (pos <= 3) g.thirds++;
    };

    update(stats.total);
    if (isTurf) update(stats.turf);
    if (isDirt) update(stats.dirt);

    if (distKey) {
      if (!stats.byDistance[distKey]) stats.byDistance[distKey] = createEmpty();
      update(stats.byDistance[distKey]);
    }
    if (!stats.byCondition[condKey]) stats.byCondition[condKey] = createEmpty();
    update(stats.byCondition[condKey]);
    if (frameKey) {
      if (!stats.byFrame[frameKey]) stats.byFrame[frameKey] = createEmpty();
      update(stats.byFrame[frameKey]);
    }
    if (fieldSizeKey) {
      if (!stats.byFieldSize[fieldSizeKey]) stats.byFieldSize[fieldSizeKey] = createEmpty();
      update(stats.byFieldSize[fieldSizeKey]);
    }
  }

  const calcRates = (g: StatGroup) => {
    if (g.races > 0) {
      g.winRate = Math.round((g.wins / g.races) * 1000) / 10;
      g.placeRate = Math.round((g.seconds / g.races) * 1000) / 10;
      g.showRate = Math.round((g.thirds / g.races) * 1000) / 10;
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

// ============================================================
// メインAPI
// ============================================================

/**
 * 馬の全データを取得（3層統合）
 *
 * 受け入れるID: 10桁ketto_num / 7桁keibabook ID / 馬名
 */
export async function getHorseFullData(id: string): Promise<IntegratedHorseData | null> {
  const totalStart = Date.now();

  try {
    // 0. ID解決
    const kettoNum = resolveToKettoNum(id);
    if (!kettoNum) {
      console.warn(`[HorseDataReader] Cannot resolve ID: ${id}`);
      return null;
    }

    // --- Layer 1: JRA-VAN Base ---

    // 1. 馬基本情報
    let basic = await getHorseBaseProfile(kettoNum);
    if (!basic) {
      // 最終手段: keibabookIDで直接UM検索
      const fromUM = await getProfileFromUMBinary(kettoNum, undefined);
      if (!fromUM) {
        console.warn(`[HorseDataReader] Horse not found: ${kettoNum}`);
        return null;
      }
      basic = fromUM;
    }

    const horseName = basic.name;

    // 2. 過去レース成績
    let pastRaces = await getCareerResults(kettoNum);

    // SE_DATAが空の場合、race_*.jsonからレース情報のみで構築（フォールバック）
    if (pastRaces.length === 0 && isIndexAvailable()) {
      const raceFiles = getRaceFilesForHorse(kettoNum);
      for (const filePath of raceFiles) {
        if (pastRaces.length >= 30) break;
        const enrichment = await extractRaceAndKbEnrichment(filePath, kettoNum);
        if (enrichment) {
          // race_*.jsonからフル情報を組み立て
          const raceData = raceJsonCache.get(filePath);
          if (raceData) {
            const dateStr = raceData.date as string || '';
            const [y, m, d] = dateStr.split('-');
            const entries = raceData.entries as Array<Record<string, unknown>> || [];
            const entry = entries.find(e => String(e.ketto_num || '') === kettoNum);
            if (entry) {
              const corners = (entry.corners as number[] || []).filter(c => c > 0).join('-');
              pastRaces.push({
                date: `${y}/${m}/${d}`,
                track: raceData.venue_name as string || '',
                raceId: enrichment.raceId || '',
                raceNumber: raceData.race_number as number || 0,
                raceName: enrichment.raceName || '',
                raceClass: enrichment.raceClass || '',
                distance: enrichment.distance || '',
                condition: enrichment.condition || '',
                headCount: enrichment.headCount || 0,
                horseNumber: entry.umaban as number || 0,
                frameNumber: entry.wakuban as number || 0,
                weight: String(entry.futan || ''),
                horseWeight: String(entry.horse_weight || ''),
                horseWeightDiff: entry.horse_weight_diff ? String(entry.horse_weight_diff) : '',
                jockey: entry.jockey_name as string || '',
                finishPosition: String(entry.finish_position || ''),
                popularity: String(entry.popularity || ''),
                time: entry.time as string || '',
                timeDiff: '',
                first3f: enrichment.first3f || '',
                last3f: entry.last_3f ? String(entry.last_3f) : '',
                corner4Pos: '',
                cornerPositions: corners,
                odds: String(entry.odds || ''),
                honshiMark: enrichment.honshiMark || '',
                shortComment: enrichment.shortComment || '',
                trainingArrow: enrichment.trainingArrow || '',
                trainingComment: enrichment.trainingComment || '',
                attackExplanation: enrichment.attackExplanation || '',
                stableComment: enrichment.stableComment || '',
                paddockMark: '',
                paddockComment: '',
                resultMemo: enrichment.resultMemo || '',
                resultComment: enrichment.resultComment || '',
                sunpyou: enrichment.sunpyou || '',
              });
            }
          }
        }
      }
    }

    // --- Layer 2: race_*.json + kb_ext Enrichment ---
    // horse_race_indexは10桁ketto_numでキーイング
    pastRaces = await enrichWithKeibabook(pastRaces, kettoNum, horseName);

    // 日付降順ソート
    pastRaces.sort((a, b) => b.date.localeCompare(a.date));

    // --- 統計計算 ---
    const stats = calculateStats(pastRaces);
    basic.totalRaces = pastRaces.length;

    // --- 調教師情報を最新レースから補完 ---
    if (pastRaces.length > 0) {
      const latest = pastRaces[0];

      if (!basic.jockey && latest.jockey) {
        basic.jockey = latest.jockey;
      }

      if (!basic.trainerId && latest.trainerId) {
        basic.trainerId = latest.trainerId;
        basic.trainerLink = latest.trainerLink || '';
        if (latest.trainerTozai && !basic.trainerTozai) {
          basic.trainerTozai = latest.trainerTozai;
        }
        if (latest.trainer && !basic.trainer) {
          basic.trainer = latest.trainer;
        }
      }

      if (basic.trainerId || basic.trainerJvnCode) {
        const trainerInfo = getTrainerInfo(basic.trainerId);
        if (trainerInfo) {
          basic.trainerJvnCode = trainerInfo.jvnCode || basic.trainerJvnCode;
          basic.trainerComment = trainerInfo.comment;
          if (!basic.trainerTozai && trainerInfo.tozai) {
            basic.trainerTozai = trainerInfo.tozai;
          }
        }
      }
    }

    const totalElapsed = Date.now() - totalStart;
    if (totalElapsed > 500) {
      console.log(`[HorseDataReader] getHorseFullData total: ${totalElapsed}ms (${pastRaces.length} races)`);
    }

    return {
      basic,
      pastRaces,
      stats,
      userMemo: '', // Layer 3はページ側で取得
    };
  } catch (error) {
    console.error('[HorseDataReader] データ取得エラー:', error);
    return null;
  }
}

// ============================================================
// 馬検索（horse_name_index.json活用）
// ============================================================

/**
 * 馬名で検索（horse_name_indexベース、20万件対応）
 */
export async function searchHorsesByNameIndex(
  query: string,
  limit: number = 50
): Promise<Array<{ id: string; name: string; age: string }>> {
  const nameIndex = loadHorseNameIndex();
  const normalizedQuery = query.toLowerCase();
  const results: Array<{ id: string; name: string; age: string }> = [];

  for (const [name, kettoNum] of Object.entries(nameIndex)) {
    if (name.toLowerCase().includes(normalizedQuery)) {
      // Horse master JSONから年齢を取得
      let age = '';
      try {
        const masterPath = path.join(DATA3_ROOT, 'masters', 'horses', `${kettoNum}.json`);
        const content = await fsp.readFile(masterPath, 'utf-8');
        const data = JSON.parse(content);
        const ageNum = calculateHorseAge(data.birth_date || '');
        age = `${data.sex_name || ''}${ageNum}`;
      } catch {
        // master JSONがない場合は年齢なし
      }

      results.push({ id: kettoNum, name, age });
      if (results.length >= limit) break;
    }
  }

  return results;
}
