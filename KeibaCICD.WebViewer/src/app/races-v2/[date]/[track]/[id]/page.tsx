/**
 * レース詳細ページ（新方式）
 * JSON → 直接表示のシンプルなフロー
 */

import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Link from 'next/link';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import {
  getIntegratedRaceData,
  hasRaceResults,
} from '@/lib/data/integrated-race-reader';
import { getRaceNavigation, getRaceInfo } from '@/lib/data';
import { getTrainingSummaryMap, getPreviousTrainingBatch } from '@/lib/data/training-summary-reader';
import { getCourseRpciInfo } from '@/lib/data/rpci-standards-reader';
import { getRatingStandards } from '@/lib/data/rating-standards-reader';
import { getBabaCondition, trackToSurface } from '@/lib/data/baba-reader';
import { getRaceAllComments, getHorseCommentsBatch, type RaceHorseComment, type HorseComment } from '@/lib/data/target-comment-reader';
import { getRaceMarks, type RaceMarks } from '@/lib/data/target-mark-reader';
import { getRecentFormBatch, type RecentFormData } from '@/lib/data/target-race-result-reader';
import { resolveKeibabookRaceId } from '@/lib/data/race-horse-names';
import {
  RaceHeader,
  RaceDetailContent,
} from '@/components/race-v2';
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
  const raceData = await getIntegratedRaceData(date, track, id);
  
  if (!raceData) {
    return { title: 'レースが見つかりません' };
  }
  
  const { race_info } = raceData;
  // URLパラメータのtrackを優先（JSONデータは不正確な場合がある）
  const displayTrack = decodeURIComponent(track);
  
  // 日付を短い形式に変換（2026-01-31 → 1/31）
  const [, month, day] = date.split('-');
  const shortDate = `${parseInt(month)}/${parseInt(day)}`;
  
  // レース名があれば表示、なければ距離等
  const raceName = race_info.race_name || race_info.race_condition || '';
  const title = `${displayTrack}${race_info.race_number}R ${raceName}`.trim();
  
  return {
    title: `${title} (${shortDate})`,
    description: `${date} ${title} - ${race_info.race_condition || ''}`,
  };
}

export default async function RaceDetailPage({ params }: PageParams) {
  const { date, track: encodedTrack, id } = await params;
  const track = decodeURIComponent(encodedTrack);
  
  // レースIDからレース番号を抽出
  const currentRaceNumber = parseInt(id.slice(-2), 10);

  // データ取得（1段階目: 依存関係のないデータを並列取得）
  const [raceData, navigation, raceInfo, trainingSummaryMap, ratingStandards] = await Promise.all([
    getIntegratedRaceData(date, track, id),
    getRaceNavigation(date, track, currentRaceNumber),
    getRaceInfo(date),
    getTrainingSummaryMap(date),
    getRatingStandards(),  // 依存なし → 1段階目に移動
  ]);
  
  if (!raceData) {
    notFound();
  }

  // 2段階目: raceData/trainingSummaryMapに依存するデータを並列取得
  const horsesForPrevTraining = Object.entries(trainingSummaryMap)
    .filter(([_, data]) => data.kettoNum)
    .map(([horseName, data]) => ({
      horseName,
      kettoNum: data.kettoNum!
    }));
  
  const [rpciInfo, previousTrainingMap] = await Promise.all([
    // RPCI基準値情報（raceDataに依存）
    getCourseRpciInfo(
      track,
      raceData.race_info.track || '',
      raceData.race_info.distance || 0
    ),
    // 前走調教データ（trainingSummaryMapに依存）
    horsesForPrevTraining.length > 0
      ? getPreviousTrainingBatch(horsesForPrevTraining, date)
      : Promise.resolve({}),
  ]);

  // 結果があるかどうか
  const showResults = hasRaceResults(raceData);

  // JRAビュアーURL生成
  let paddockUrl: string | null = null;
  let raceUrl: string | null = null;
  let patrolUrl: string | null = null;
  
  let babaInfo: import('@/lib/data/baba-reader').BabaCondition | null = null;
  let targetComments: {
    predictions: Map<number, RaceHorseComment>;
    results: Map<number, RaceHorseComment>;
  } = { predictions: new Map(), results: new Map() };
  
  // TARGET馬印（My印, My印2）
  let targetMarks: RaceMarks | null = null;
  let targetMarks2: RaceMarks | null = null;
  
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
      
      // TARGETコメント取得（レース別コメント）
      targetComments = getRaceAllComments(
        track,
        date.split('-')[0], // year (4桁)
        kaisaiInfo.kai,
        kaisaiInfo.nichi,
        currentRaceNumber
      );
      
      // TARGET馬印取得（My印1, My印2）
      const yearNum = parseInt(date.split('-')[0], 10);
      const marks1 = getRaceMarks(
        yearNum,
        kaisaiInfo.kai,
        kaisaiInfo.nichi,
        currentRaceNumber,
        track,
        1  // 馬印1
      );
      const marks2 = getRaceMarks(
        yearNum,
        kaisaiInfo.kai,
        kaisaiInfo.nichi,
        currentRaceNumber,
        track,
        2  // 馬印2
      );
      
      // それぞれ保存
      targetMarks = marks1;
      targetMarks2 = marks2;
      
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
  // trainingSummaryMapからkettoNum（JRA-VAN 10桁ID）を取得して使用
  // 競馬ブックのhorse_idではなく、kettoNumで検索する必要がある
  const kettoNumList = raceData.entries
    .map(e => {
      // normalizeHorseNameはrace-data.tsからインポート済みと想定
      const normalized = e.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
      const summary = trainingSummaryMap[e.horse_name] || trainingSummaryMap[normalized];
      return summary?.kettoNum;
    })
    .filter((id): id is string => !!id);
  const horseCommentsMap = getHorseCommentsBatch(kettoNumList);

  // 直近戦績取得（SE_DATA）
  // 馬番→kettoNumマッピングを構築
  const horseNumToKettoNum = new Map<number, string>();
  for (const e of raceData.entries) {
    const normalized = e.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
    const summary = trainingSummaryMap[e.horse_name] || trainingSummaryMap[normalized];
    if (summary?.kettoNum) {
      horseNumToKettoNum.set(e.horse_number, summary.kettoNum);
    }
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
        const dayPath = `${process.env.DATA_ROOT || 'C:/KEIBA-CICD/data2'}/races/${d.slice(0, 4)}/${d.slice(4, 6)}/${d.slice(6, 8)}`;
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

  // 外部リンクURL生成
  const [year, month, dayStr] = date.split('-');
  const keibabookUrl = `https://p.keibabook.co.jp/cyuou/syutsuba/${year}${month}${dayStr}${id.slice(-4, -2)}${id.slice(-2).padStart(2, '0')}`;
  // netkeiba race_id: YYYY + 場コード(2) + 回(2) + 日(2) + レース番号(2) = 12桁
  const trackCode = trackCodes[track];
  const netkeibaRaceId = kaisaiInfoForEdit && trackCode
    ? `${year}${trackCode}${String(kaisaiInfoForEdit.kai).padStart(2, '0')}${String(kaisaiInfoForEdit.nichi).padStart(2, '0')}${String(currentRaceNumber).padStart(2, '0')}`
    : null;
  const netkeibaUrl = netkeibaRaceId ? `https://race.netkeiba.com/race/shutuba.html?race_id=${netkeibaRaceId}&rf=race_submenu` : null;
  const netkeibaBbsUrl = netkeibaRaceId ? `https://yoso.netkeiba.com/?pid=race_board&id=c${netkeibaRaceId}` : null;

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
      <div className="flex justify-end mb-2">
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
        jraRaceId={jraRaceId}
      />

      {/* メインコンテンツ */}
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
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
            (targetMarks || targetMarks2)
              ? {
                  horseMarks: targetMarks?.horseMarks || {},
                  horseMarks2: targetMarks2?.horseMarks || {}
                }
              : undefined
          }
          recentFormMap={recentFormMap}
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
