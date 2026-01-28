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
import { getTrainingSummaryMap } from '@/lib/data/training-summary-reader';
import {
  RaceHeader,
  RaceDetailContent,
} from '@/components/race-v2';
import {
  generatePaddockUrl,
  generateRaceUrl,
  generatePatrolUrl,
  getKaisaiInfoFromRaceInfo,
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
  const title = `${displayTrack}${race_info.race_number}R ${race_info.race_name || ''}`.trim();
  
  return {
    title: `${title} | KeibaCICD`,
    description: `${date} ${title} - ${race_info.race_condition || ''}`,
  };
}

export default async function RaceDetailPage({ params }: PageParams) {
  const { date, track: encodedTrack, id } = await params;
  const track = decodeURIComponent(encodedTrack);
  
  // レースIDからレース番号を抽出
  const currentRaceNumber = parseInt(id.slice(-2), 10);

  // データ取得
  const [raceData, navigation, raceInfo, trainingSummaryMap] = await Promise.all([
    getIntegratedRaceData(date, track, id),
    getRaceNavigation(date, track, currentRaceNumber),
    getRaceInfo(date),
    getTrainingSummaryMap(date),
  ]);
  
  if (!raceData) {
    notFound();
  }

  // 結果があるかどうか
  const showResults = hasRaceResults(raceData);

  // JRAビュアーURL生成
  let paddockUrl: string | null = null;
  let raceUrl: string | null = null;
  let patrolUrl: string | null = null;
  
  if (raceInfo) {
    const kaisaiInfo = getKaisaiInfoFromRaceInfo(raceInfo.kaisai_data, id);
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
    }
  }

  // 外部リンクURL生成
  const [year, month, dayStr] = date.split('-');
  const keibabookUrl = `https://p.keibabook.co.jp/cyuou/syutsuba/${year}${month}${dayStr}${id.slice(-4, -2)}${id.slice(-2).padStart(2, '0')}`;
  const netkeibaRaceId = id;
  const netkeibaUrl = `https://race.netkeiba.com/race/shutuba.html?race_id=${netkeibaRaceId}&rf=race_submenu`;
  const netkeibaBbsUrl = `https://yoso.netkeiba.com/?pid=race_board&id=c${netkeibaRaceId}`;

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
      />

      {/* メインコンテンツ */}
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* 表示モード切替 + コンテンツ */}
        <RaceDetailContent 
          raceData={raceData}
          showResults={showResults}
          trainingSummaryMap={trainingSummaryMap}
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
