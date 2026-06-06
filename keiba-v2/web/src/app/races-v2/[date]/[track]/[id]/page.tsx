/**
 * レース詳細ページ（新方式）
 * JSON → 直接表示のシンプルなフロー
 */

import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Link from 'next/link';
import { ChevronLeft, ChevronRight, Wallet } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  getIntegratedRaceData,
  hasRaceResults,
} from '@/lib/data/integrated-race-reader';
import { getV4RaceData } from '@/lib/data/v4-race-reader';
import { getKbExtData } from '@/lib/data/v4-keibabook-reader';
import { DATA3_ROOT } from '@/lib/config';
import { adaptV4ToIntegrated } from '@/lib/data/v4-race-adapter';
import { getRaceNavigation, getRaceInfo } from '@/lib/data';
import { getTrainingSummaryMap, getPreviousTrainingBatch } from '@/lib/data/training-summary-reader';
import { getCourseRpciInfo } from '@/lib/data/rpci-standards-reader';
import { getRatingStandards } from '@/lib/data/rating-standards-reader';
import { getBabaCondition, trackToSurface } from '@/lib/data/baba-reader';
import { getRaceAllComments, getHorseCommentsBatch, type RaceHorseComment, type HorseComment } from '@/lib/data/target-comment-reader';
import { getRaceMarks, type RaceMarks } from '@/lib/data/target-mark-reader';
import { getRecentFormBatch, type RecentFormData } from '@/lib/data/target-race-result-reader';
import { getRaceTrendIndex, lookupRaceTrend } from '@/lib/data/race-trend-reader';
import { loadTrainerPatterns, evaluatePatternMatch, type TrainerPatternMatch } from '@/lib/data/trainer-patterns-reader';
import { getTrainerInfo } from '@/lib/data/trainer-index';
import { resolveKeibabookRaceId } from '@/lib/data/race-horse-names';
import { getMlPredictions, getClosingRaceProba, getRaceConfidence } from '@/lib/data/ml-prediction-reader';
import { getCheckUmaMap, type CheckUmaEntry } from '@/lib/data/target-checkuma-reader';
import { getTrackBias } from '@/lib/data/jrdb-kaa-reader';
import {
  RaceHeader,
  RaceDetailContent,
} from '@/components/race-v2';
import { NiigataChokuBanner } from '@/components/race-v2/NiigataChokuBanner';
import { RaceHeaderSpecialistLink } from '@/components/race-v2/RaceHeaderSpecialistLink';
import { RefreshButton } from '@/components/ui/refresh-button';
import {
  generatePaddockUrl,
  generateRaceUrl,
  generatePatrolUrl,
  getKaisaiInfoFromRaceInfo,
  getKaisaiInfoFromRaceInfoWithFallback,
} from '@/lib/jra-viewer-url';

interface PageParams {
  params: Promise<{
    date: string;
    track: string;
    id: string;
  }>;
}

// 出走表は常に最新の predictions.json を読み込む (キャッシュさせない)
export const dynamic = 'force-dynamic';

// 競馬場背景カラー（タブ用）
const getTrackBgClass = (trackName: string) => {
  const map: Record<string, string> = {
    '中山': 'bg-[var(--color-venue-nakayama)]',
    '京都': 'bg-[var(--color-venue-kyoto)]',
    '小倉': 'bg-[var(--color-venue-kokura)]',
    '東京': 'bg-[var(--color-venue-tokyo)]',
    '阪神': 'bg-[var(--color-venue-hanshin)]',
  };
  return map[trackName] || 'bg-primary';
};

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { date, track, id } = await params;
  const displayTrack = decodeURIComponent(track);
  const [, month, day] = date.split('-');
  const shortDate = `${parseInt(month)}/${parseInt(day)}`;

  // integrated data → v4 data のフォールバック
  const integratedData = await getIntegratedRaceData(date, track, id);

  let raceName = '';
  let raceNumber = '';
  let raceCondition = '';

  if (integratedData) {
    raceName = integratedData.race_info.race_name || integratedData.race_info.race_condition || '';
    raceNumber = String(integratedData.race_info.race_number);
    raceCondition = integratedData.race_info.race_condition || '';
  } else {
    // v4 race JSONから直接タイトル情報を取得
    const dateCompact = date.replace(/-/g, '');
    const venueToJvCode: Record<string, string> = {
      '札幌': '01', '函館': '02', '福島': '03', '新潟': '04', '東京': '05',
      '中山': '06', '中京': '07', '京都': '08', '阪神': '09', '小倉': '10',
    };
    let raceId16: string;
    if (id.length === 16 && id.startsWith(dateCompact)) {
      raceId16 = id;
    } else {
      const jvVenueCode = venueToJvCode[displayTrack] || id.slice(6, 8);
      raceId16 = `${dateCompact}${jvVenueCode}${id.slice(4, 6)}${id.slice(8, 10)}${id.slice(10, 12)}`;
    }
    const v4Race = getV4RaceData(raceId16);
    if (v4Race) {
      raceName = v4Race.race_name || '';
      raceNumber = String(v4Race.race_number);
    } else {
      return { title: 'レースが見つかりません' };
    }
  }

  const title = `${displayTrack}${raceNumber}R ${raceName}`.trim();

  return {
    title: `${title} (${shortDate})`,
    description: `${date} ${title} - ${raceCondition}`,
  };
}

export default async function RaceDetailPage({ params }: PageParams) {
  const { date, track: encodedTrack, id } = await params;
  const track = decodeURIComponent(encodedTrack);
  
  // レースIDからレース番号を抽出
  const currentRaceNumber = parseInt(id.slice(-2), 10);

  // race_id判定: 16桁ならそのまま使用、12桁なら変換
  const venueToJvCode: Record<string, string> = {
    '札幌': '01', '函館': '02', '福島': '03', '新潟': '04', '東京': '05',
    '中山': '06', '中京': '07', '京都': '08', '阪神': '09', '小倉': '10',
  };
  const dateCompact = date.replace(/-/g, '');
  let raceId16: string;
  if (id.length === 16 && id.startsWith(dateCompact)) {
    // 既に16桁のv4形式 (YYYYMMDD + VV + KK + NN + RR)
    raceId16 = id;
  } else {
    // 12桁keibabook形式 → 16桁変換
    // 12桁: YYYY + KK(2) + JJ(2) + NN(2) + RR(2)
    const jvVenueCode = venueToJvCode[track] || id.slice(6, 8);
    const kai = id.slice(4, 6);
    const nichi = id.slice(8, 10);
    const raceNum = id.slice(10, 12);
    raceId16 = `${dateCompact}${jvVenueCode}${kai}${nichi}${raceNum}`;
  }

  // データ取得（並列取得: 依存関係のないデータを全て同時に取得）
  const [integratedData, navigation, raceInfo, trainingSummaryMap, ratingStandards, trainerPatterns, mlPredictions, closingRaceProba, raceConfidence] = await Promise.all([
    getIntegratedRaceData(date, track, id),
    getRaceNavigation(date, track, currentRaceNumber),
    getRaceInfo(date),
    getTrainingSummaryMap(date),
    getRatingStandards(),
    loadTrainerPatterns(),
    getMlPredictions(id, raceId16, date),
    getClosingRaceProba(id, raceId16, date),
    getRaceConfidence(id, raceId16, date),
  ]);

  // v4(data3)優先 → data2でエンリッチ → data2フォールバック
  let raceData: import('@/types/race-data').IntegratedRaceData | null = null;
  const v4Race = getV4RaceData(raceId16);
  if (v4Race) {
    const kbExt = getKbExtData(raceId16);
    raceData = adaptV4ToIntegrated(v4Race, kbExt, integratedData);
  } else {
    raceData = integratedData;
  }

  if (!raceData) {
    notFound();
  }

  // 2段階目: raceDataに依存するデータを並列取得
  // 現在のレースの馬のみ前走調教を取得（全馬3700件→レース出走馬~16頭に限定）
  const horsesForPrevTraining: Array<{ horseName: string; kettoNum: string }> = [];
  for (const e of raceData.entries) {
    const normalizedName = e.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
    const summary = trainingSummaryMap[e.horse_name] || trainingSummaryMap[normalizedName];
    if (summary?.kettoNum) {
      horsesForPrevTraining.push({
        horseName: e.horse_name,
        kettoNum: summary.kettoNum,
      });
    }
  }

  // 馬場状態をRPCI基準値用に変換（"良" → "良", それ以外 → "稍重以上"）
  const trackCondition = raceData.race_info.track_condition || '';
  const rpcibabaCondition = trackCondition === '良' ? '良' : trackCondition ? '稍重以上' : undefined;
  const numRunners = raceData.entries.length;

  const [rpciInfo, previousTrainingMap, raceTrendIndex] = await Promise.all([
    getCourseRpciInfo(
      track,
      raceData.race_info.track || '',
      raceData.race_info.distance || 0,
      rpcibabaCondition,
      numRunners,
    ),
    horsesForPrevTraining.length > 0
      ? getPreviousTrainingBatch(horsesForPrevTraining, date)
      : Promise.resolve({}),
    getRaceTrendIndex(),
  ]);

  // 結果があるかどうか
  const showResults = hasRaceResults(raceData);

  // JRAビュアーURL生成
  let paddockUrl: string | null = null;
  let raceUrl: string | null = null;
  let patrolUrl: string | null = null;
  
  let babaInfo: import('@/lib/data/baba-reader').BabaCondition | null = null;
  let trackBias: import('@/lib/data/jrdb-kaa-reader').TrackBias | null = null;
  let targetComments: {
    predictions: Map<number, RaceHorseComment>;
    results: Map<number, RaceHorseComment>;
  } = { predictions: new Map(), results: new Map() };
  
  // TARGET馬印（My印=markSet1 手動, AI印=markSet6 AI予想）
  let targetMarks: RaceMarks | null = null;
  let targetMarksAi: RaceMarks | null = null;
  
  // kaisaiInfo（コメント編集用に外に出す）
  let kaisaiInfoForEdit: { kai: number; nichi: number } | undefined;
  
  // JRA 16桁形式のレースID生成用
  let jraRaceId: string | null = null;
  const trackCodes: Record<string, string> = {
    '札幌': '01', '函館': '02', '福島': '03', '新潟': '04', '東京': '05',
    '中山': '06', '中京': '07', '京都': '08', '阪神': '09', '小倉': '10',
  };
  
  if (raceInfo) {
    const kaisaiInfo =
      getKaisaiInfoFromRaceInfo(raceInfo.kaisai_data, id) ??
      getKaisaiInfoFromRaceInfoWithFallback(
        raceInfo.kaisai_data,
        id,
        track,
        currentRaceNumber
      );
    if (kaisaiInfo) {
      const [year, month, day] = date.split('-').map(Number);
      const urlParams = {
        year,
        month,
        day,
        track: kaisaiInfo.track,
        kai: kaisaiInfo.kai,
        nichi: kaisaiInfo.nichi,
        raceNumber: currentRaceNumber,
      };
      paddockUrl = generatePaddockUrl(urlParams);
      raceUrl = generateRaceUrl(urlParams);
      patrolUrl = generatePatrolUrl(urlParams);
      babaInfo = getBabaCondition(
        id,
        trackToSurface(raceData.race_info.track || ''),
        kaisaiInfo.kai,
        kaisaiInfo.nichi,
        track
      );

      // JRDB KAA トラックバイアス取得
      const venueCode = trackCodes[track];
      if (venueCode) {
        trackBias = getTrackBias(venueCode, date);
      }

      // TARGETコメント取得（レース別コメント）
      targetComments = getRaceAllComments(
        track,
        date.split('-')[0], // year (4桁)
        kaisaiInfo.kai,
        kaisaiInfo.nichi,
        currentRaceNumber
      );
      
      // TARGET馬印取得（My印=markSet1 手動, AI印=markSet6 AI予想）
      const yearNum = parseInt(date.split('-')[0], 10);
      const marks1 = getRaceMarks(
        yearNum,
        kaisaiInfo.kai,
        kaisaiInfo.nichi,
        currentRaceNumber,
        track,
        1  // 馬印1（ふくだ手動）
      );
      const marksAi = getRaceMarks(
        yearNum,
        kaisaiInfo.kai,
        kaisaiInfo.nichi,
        currentRaceNumber,
        track,
        6  // 馬印6（AI予想印）
      );

      // それぞれ保存
      targetMarks = marks1;
      targetMarksAi = marksAi;
      
      // コメント編集用にkaisaiInfoを保持
      kaisaiInfoForEdit = { kai: kaisaiInfo.kai, nichi: kaisaiInfo.nichi };
      
      // JRA 16桁形式のレースID生成
      const trackCode = trackCodes[track];
      if (trackCode) {
        const dateNoDash = date.replace(/-/g, '');
        const raceNo = String(currentRaceNumber).padStart(2, '0');
        const kai = String(kaisaiInfo.kai).padStart(2, '0');
        const nichi = String(kaisaiInfo.nichi).padStart(2, '0');
        jraRaceId = `${dateNoDash}${trackCode}${kai}${nichi}${raceNo}`;
      }
    }
  }

  // TARGETコメント取得（馬コメント）
  // kettoNum（JRA-VAN 10桁ID）を各馬ごとに確定: entry.horse_id (v4 adapter) 優先、trainingSummaryMapフォールバック
  const resolveKettoNum = (e: typeof raceData.entries[number]): string | undefined => {
    if (e.horse_id && /^\d{10}$/.test(e.horse_id)) return e.horse_id;
    const normalized = e.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
    const summary = trainingSummaryMap[e.horse_name] || trainingSummaryMap[normalized];
    return summary?.kettoNum;
  };
  const entryKettoMap: Record<number, string> = {};
  for (const e of raceData.entries) {
    const k = resolveKettoNum(e);
    if (k) entryKettoMap[e.horse_number] = k;
  }
  const kettoNumList = Object.values(entryKettoMap);
  const horseCommentsMap = getHorseCommentsBatch(kettoNumList);

  // チェック馬取得
  const checkUmaRaw = getCheckUmaMap(kettoNumList);
  // 馬番→CheckUmaEntry に変換
  const checkUmaByHorseNum: Record<number, CheckUmaEntry> = {};
  for (const e of raceData.entries) {
    const k = entryKettoMap[e.horse_number];
    if (k) {
      const entry = checkUmaRaw.get(k);
      if (entry) checkUmaByHorseNum[e.horse_number] = entry;
    }
  }

  // 直近戦績取得（SE_DATA）
  // 馬番→kettoNumマッピング（entry.horse_id優先、trainingSummaryMapフォールバック）
  const horseNumToKettoNum = new Map<number, string>();
  for (const [hn, k] of Object.entries(entryKettoMap)) {
    horseNumToKettoNum.set(Number(hn), k);
  }
  const beforeDate = date.replace(/-/g, ''); // YYYYMMDD
  const recentFormRaw = getRecentFormBatch(
    Array.from(horseNumToKettoNum.values()),
    beforeDate,
    5
  );
  // 馬番→RecentFormData[] に変換（リンクURL解決付き）
  const recentFormMap: Record<number, RecentFormData[]> = {};
  for (const [horseNum, kettoNum] of horseNumToKettoNum) {
    const forms = recentFormRaw.get(kettoNum);
    if (forms && forms.length > 0) {
      // 各レースのリンクURLを解決
      for (const form of forms) {
        const d = form.raceDate;
        const dayPath = `${DATA3_ROOT}/races/${d.slice(0, 4)}/${d.slice(4, 6)}/${d.slice(6, 8)}`;
        // JRA-VAN 16桁ID: YYYYMMDD + venueCode(2) + kai(2) + nichi(2) + raceNum(2)
        const jraRaceId = `${d}${form.venueCode}${String(form.kai).padStart(2, '0')}${String(form.nichi).padStart(2, '0')}${String(form.raceNumber).padStart(2, '0')}`;
        const keibabookId = resolveKeibabookRaceId(jraRaceId, dayPath);
        if (keibabookId) {
          const dateStr = `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
          form.href = `/races-v2/${dateStr}/${encodeURIComponent(form.venue)}/${keibabookId}`;
        }
      }
      recentFormMap[horseNum] = forms;
    }
  }

  // レース傾向インデックスを近走データに付与
  if (raceTrendIndex) {
    for (const forms of Object.values(recentFormMap)) {
      for (const form of forms) {
        form.raceTrend = lookupRaceTrend(raceTrendIndex, form.raceId);
      }
    }
  }

  // 調教師パターンマッチング（各馬の調教データ × 調教師の勝負パターン）
  const trainerPatternMatchMap: Record<string, TrainerPatternMatch | null> = {};
  if (trainerPatterns.size > 0) {
    for (const entry of raceData.entries) {
      const normalizedName = entry.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
      const summary = trainingSummaryMap[entry.horse_name] || trainingSummaryMap[normalizedName];
      if (summary && entry.entry_data?.trainer_id) {
        const match = evaluatePatternMatch(entry.entry_data.trainer_id, summary);
        if (match) {
          trainerPatternMatchMap[entry.horse_name] = match;
        }
      }
    }
  }

  // 外部リンクURL生成
  const [year, month, dayStr] = date.split('-');
  // 競馬ブック12桁レースID: YYYYKKJJNNRR (年+回+場所(KB独自)+日+R)
  const keibabookTrackCodes: Record<string, string> = {
    '京都': '00', '阪神': '01', '中京': '02', '小倉': '03',
    '東京': '04', '中山': '05', '福島': '06', '新潟': '07',
    '札幌': '08', '函館': '09',
  };
  const kbCode = keibabookTrackCodes[track];
  const keibabookUrl = kaisaiInfoForEdit && kbCode !== undefined
    ? `https://p.keibabook.co.jp/cyuou/syutuba/${year}${String(kaisaiInfoForEdit.kai).padStart(2, '0')}${kbCode}${String(kaisaiInfoForEdit.nichi).padStart(2, '0')}${String(currentRaceNumber).padStart(2, '0')}`
    : null;
  // netkeiba race_id: YYYY + 場コード(2) + 回(2) + 日(2) + レース番号(2) = 12桁
  const trackCode = trackCodes[track];
  const netkeibaRaceId = kaisaiInfoForEdit && trackCode
    ? `${year}${trackCode}${String(kaisaiInfoForEdit.kai).padStart(2, '0')}${String(kaisaiInfoForEdit.nichi).padStart(2, '0')}${String(currentRaceNumber).padStart(2, '0')}`
    : null;
  const netkeibaUrl = netkeibaRaceId ? `https://race.netkeiba.com/race/shutuba.html?race_id=${netkeibaRaceId}&rf=race_submenu` : null;
  const netkeibaBbsUrl = netkeibaRaceId ? `https://race.netkeiba.com/race/bbs.html?race_id=${netkeibaRaceId}&rf=race_submenu` : null;

  // 競馬場切り替え時に同じレース番号を維持するためのヘルパー
  const getTrackRaceId = (targetTrack: string, raceNumber: number): string => {
    if (!navigation) return '';
    const trackInfo = navigation.tracks.find((t) => t.name === targetTrack);
    if (!trackInfo) return '';

    const byNumber = trackInfo.raceByNumber?.[raceNumber];
    if (byNumber) return byNumber;

    // 念のため近いレース番号へフォールバック
    const raceByNumber = trackInfo.raceByNumber || {};
    const availableNumbers = Object.keys(raceByNumber).map(Number).filter((n) => !Number.isNaN(n));
    if (availableNumbers.length > 0) {
      availableNumbers.sort((a, b) => a - b);
      const closest = availableNumbers.reduce((prev, curr) =>
        Math.abs(curr - raceNumber) < Math.abs(prev - raceNumber) ? curr : prev
      );
      return raceByNumber[closest] || trackInfo.firstRaceId;
    }

    return trackInfo.firstRaceId;
  };

  return (
    <div className="min-h-screen bg-background">
      {/* レースナビゲーション - v1スタイル */}
      {navigation && (
        <div className="mb-4 p-3 bg-card rounded-xl border shadow-sm">
          <div className="flex items-center gap-3">
            {/* 前のレースボタン（出走時刻順・全場） */}
            {navigation.prevRace ? (
              <Link
                href={`/races-v2/${date}/${encodeURIComponent(navigation.prevRace.track)}/${navigation.prevRace.raceId}`}
                className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 active:bg-gray-300 transition-all duration-150 flex items-center justify-center shadow-sm hover:shadow"
                title={`前のレース (${navigation.prevRace.track})`}
              >
                <ChevronLeft className="w-5 h-5 text-gray-600" />
              </Link>
            ) : (
              <span className="w-9 h-9 rounded-full bg-gray-50 text-gray-300 flex items-center justify-center cursor-not-allowed">
                <ChevronLeft className="w-5 h-5" />
              </span>
            )}

            {/* 競馬場タブ */}
            <div className="flex gap-1.5 bg-gray-100 p-1 rounded-lg">
              {navigation.tracks.map((t) => {
                const isActive = t.name === track;
                const targetRaceId = getTrackRaceId(t.name, currentRaceNumber);
                return (
                  <Link
                    key={t.name}
                    href={`/races-v2/${date}/${encodeURIComponent(t.name)}/${targetRaceId}`}
                    className={`px-4 py-2 text-sm font-bold rounded-md transition-all duration-200 ${
                      isActive 
                        ? `${getTrackBgClass(t.name)} text-white shadow-md scale-105` 
                        : 'bg-white hover:bg-gray-50 text-gray-600 hover:text-gray-900 shadow-sm hover:shadow'
                    }`}
                  >
                    {t.name}
                  </Link>
                );
              })}
            </div>

            {/* 区切り線 */}
            <div className="w-px h-8 bg-gray-200" />

            {/* レース番号タブ (1-12) */}
            <div className="flex gap-1 flex-wrap bg-gray-50 p-1.5 rounded-lg">
              {navigation.races.map((r) => {
                const isActive = r.raceId === id;
                return (
                  <Link
                    key={r.raceId}
                    href={`/races-v2/${date}/${encodeURIComponent(track)}/${r.raceId}`}
                    className={`w-8 h-8 text-xs font-bold rounded-md transition-all duration-150 flex items-center justify-center ${
                      isActive 
                        ? 'bg-gray-800 text-white shadow-md scale-110' 
                        : 'bg-white hover:bg-gray-100 text-gray-600 hover:text-gray-900 shadow-sm hover:shadow'
                    }`}
                    title={`${r.raceName} (${r.startTime})`}
                  >
                    {r.raceNumber}
                  </Link>
                );
              })}
            </div>

            {/* 次のレースボタン（出走時刻順・全場） */}
            {navigation.nextRace ? (
              <Link
                href={`/races-v2/${date}/${encodeURIComponent(navigation.nextRace.track)}/${navigation.nextRace.raceId}`}
                className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 active:bg-gray-300 transition-all duration-150 flex items-center justify-center ml-auto shadow-sm hover:shadow"
                title={`次のレース (${navigation.nextRace.track})`}
              >
                <ChevronRight className="w-5 h-5 text-gray-600" />
              </Link>
            ) : (
              <span className="w-9 h-9 rounded-full bg-gray-50 text-gray-300 flex items-center justify-center cursor-not-allowed ml-auto">
                <ChevronRight className="w-5 h-5" />
              </span>
            )}
          </div>
        </div>
      )}

      {/* データ更新ボタン */}
      <div className="flex justify-end gap-2 mb-2">
        {jraRaceId && (
          <Link href={`/my-bets/${jraRaceId}`} target="_blank">
            <Button variant="outline" size="sm">
              <Wallet className="w-4 h-4 mr-1" />
              My印買い目
            </Button>
          </Link>
        )}
        <RefreshButton size="sm" />
      </div>

      {/* レースヘッダー */}
      <RaceHeader
        raceInfo={raceData.race_info}
        meta={raceData.meta}
        raceComment={raceData.race_comment}
        urlDate={date}
        urlTrack={track}
        externalLinks={{
          paddockUrl,
          raceUrl,
          patrolUrl,
          keibabookUrl,
          netkeibaUrl,
          netkeibaBbsUrl,
        }}
        rpciInfo={rpciInfo}
        babaInfo={babaInfo}
        trackBias={trackBias}
        jraRaceId={jraRaceId}
        laps={raceData.laps}
        closingRaceProba={closingRaceProba}
        idmCompareUrl={`/races-v2/${date}/${encodeURIComponent(track)}/${id}/idm-compare`}
      />

      {/* スペシャリストモデルへの目立つ導線 (タイトル直下、千直など適用時のみ) */}
      <RaceHeaderSpecialistLink raceId16={raceId16} date={date} />

      {/* 千直バナー (vega-niigata1000 専用、千直開催時のみ表示) */}
      <NiigataChokuBanner raceId16={raceId16} date={date} />

      {/* メインコンテンツ */}
      <main className="max-w-8xl mx-auto px-4 py-6 space-y-6">
        {/* 表示モード切替 + コンテンツ */}
        <RaceDetailContent 
          raceData={raceData}
          showResults={showResults}
          urlDate={date}
          urlTrack={track}
          trainingSummaryMap={trainingSummaryMap}
          previousTrainingMap={previousTrainingMap}
          rpciInfo={rpciInfo}
          ratingStandards={ratingStandards}
          babaInfo={babaInfo}
          targetComments={{
            predictions: Object.fromEntries(targetComments.predictions),
            results: Object.fromEntries(targetComments.results),
            // 馬コメント（馬番→コメントのマッピング）
            // kettoNumで検索するので、trainingSummaryMapからkettoNumを取得
            horseComments: Object.fromEntries(
              raceData.entries
                .filter(e => {
                  const normalized = e.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
                  const summary = trainingSummaryMap[e.horse_name] || trainingSummaryMap[normalized];
                  return summary?.kettoNum && horseCommentsMap.has(summary.kettoNum);
                })
                .map(e => {
                  const normalized = e.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
                  const summary = trainingSummaryMap[e.horse_name] || trainingSummaryMap[normalized];
                  return [e.horse_number, horseCommentsMap.get(summary!.kettoNum!)!];
                })
            ),
          }}
          kaisaiInfo={kaisaiInfoForEdit}
          targetMarks={
            (targetMarks || targetMarksAi)
              ? {
                  horseMarks: targetMarks?.horseMarks || {},
                  horseMarks2: targetMarksAi?.horseMarks || {}  // AI印(markSet6) を My2枠で表示
                }
              : undefined
          }
          recentFormMap={recentFormMap}
          trainerPatternMatchMap={trainerPatternMatchMap}
          mlPredictions={mlPredictions ?? undefined}
          raceConfidence={raceConfidence ?? undefined}
          checkUmaMap={Object.keys(checkUmaByHorseNum).length > 0 ? checkUmaByHorseNum : undefined}
          kettoNumMap={entryKettoMap}
        />

        {/* データ情報（フッター） */}
        <div className="mt-8 pt-4 border-t text-sm text-gray-500 dark:text-gray-400">
          <div className="flex flex-wrap gap-4">
            <span>レースID: {raceData.meta.race_id}</span>
            <span>生成日時: {formatDateTime(raceData.meta.created_at)}</span>
            <span>更新日時: {formatDateTime(raceData.meta.updated_at)}</span>
            <span>データバージョン: {raceData.meta.data_version}</span>
          </div>
        </div>
      </main>
    </div>
  );
}

/**
 * 日時をフォーマット
 */
function formatDateTime(isoString: string): string {
  if (!isoString) return '-';
  try {
    const date = new Date(isoString);
    return date.toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}
