/**
 * 指数表ページ
 * レース全出走馬のIDM成長曲線を重ねて比較
 */

import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Link from 'next/link';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { getIntegratedRaceData } from '@/lib/data/integrated-race-reader';
import { getV4RaceData } from '@/lib/data/v4-race-reader';
import { getKbExtData } from '@/lib/data/v4-keibabook-reader';
import { adaptV4ToIntegrated } from '@/lib/data/v4-race-adapter';
import { getHorseFullData } from '@/lib/data/horse-data-reader';
import { getPredictionsByDate } from '@/lib/data/predictions-reader';
import { getIDMStandards, resolveIDMGradeKey, getWinnerIDMByRaceName } from '@/lib/data/idm-standards-reader';
import { getRaceNavigation } from '@/lib/data';
import { IDMComparisonChart, type HorseIDMData } from '@/components/race-v2/IDMComparisonChart';

interface PageParams {
  params: Promise<{
    date: string;
    track: string;
    id: string;
  }>;
}

// ── 年齢計算（IDMTimelineChartと同一ロジック） ──

function calcAgeMonths(birthDate: string, raceDate: string): number {
  const by = parseInt(birthDate.slice(0, 4), 10);
  const bm = parseInt(birthDate.slice(4, 6), 10);
  const bd = parseInt(birthDate.slice(6, 8), 10);
  const clean = raceDate.replace(/[/-]/g, '');
  const ry = parseInt(clean.slice(0, 4), 10);
  const rm = parseInt(clean.slice(4, 6), 10);
  const rd = parseInt(clean.slice(6, 8), 10);
  return (ry - by) * 12 + (rm - bm) + (rd - bd) / 31;
}

// エポック日 (2000-01-01からの日数) — X軸用
// 月単位だと同月2走が重なるため日単位にする
function calcDateNum(raceDate: string): number {
  const clean = raceDate.replace(/[/-]/g, '');
  const y = parseInt(clean.slice(0, 4), 10);
  const m = parseInt(clean.slice(4, 6), 10) - 1;
  const d = parseInt(clean.slice(6, 8), 10);
  const ms = Date.UTC(y, m, d);
  const epoch = Date.UTC(2000, 0, 1);
  return Math.round((ms - epoch) / 86400000);
}

// ── トレンド判定 ──

function calcTrend(idmValues: number[]): 'up' | 'flat' | 'down' {
  if (idmValues.length < 2) return 'flat';
  const latest = idmValues[idmValues.length - 1];
  // 直前2-3走の平均と最新値を比較
  const prevSlice = idmValues.slice(-4, -1); // 最大3走
  const prevAvg = prevSlice.reduce((s, v) => s + v, 0) / prevSlice.length;
  const diff = latest - prevAvg;
  if (diff > 3) return 'up';
  if (diff < -3) return 'down';
  return 'flat';
}

// ── 競馬場背景カラー（タブ用） ──

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

// ── レースID変換 ──

const venueToJvCode: Record<string, string> = {
  '札幌': '01', '函館': '02', '福島': '03', '新潟': '04', '東京': '05',
  '中山': '06', '中京': '07', '京都': '08', '阪神': '09', '小倉': '10',
};

function resolveRaceId16(date: string, track: string, id: string): string {
  const dateCompact = date.replace(/-/g, '');
  if (id.length === 16 && id.startsWith(dateCompact)) {
    return id;
  }
  const jvVenueCode = venueToJvCode[track] || id.slice(6, 8);
  return `${dateCompact}${jvVenueCode}${id.slice(4, 6)}${id.slice(8, 10)}${id.slice(10, 12)}`;
}

// ── メタデータ ──

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { date, track, id } = await params;
  const displayTrack = decodeURIComponent(track);
  const [, month, day] = date.split('-');
  const shortDate = `${parseInt(month)}/${parseInt(day)}`;

  const integratedData = await getIntegratedRaceData(date, track, id);
  const raceId16 = resolveRaceId16(date, displayTrack, id);
  const v4Race = getV4RaceData(raceId16);

  let raceName = '';
  let raceNumber = '';
  if (integratedData) {
    raceName = integratedData.race_info.race_name || '';
    raceNumber = String(integratedData.race_info.race_number);
  } else if (v4Race) {
    raceName = v4Race.race_name || '';
    raceNumber = String(v4Race.race_number);
  }

  return {
    title: `指数表 ${displayTrack}${raceNumber}R ${raceName} (${shortDate})`,
  };
}

// ── ページ本体 ──

export default async function IDMComparePage({ params }: PageParams) {
  const { date, track: encodedTrack, id } = await params;
  const track = decodeURIComponent(encodedTrack);

  // レースデータ取得（既存パターン）
  const raceId16 = resolveRaceId16(date, track, id);
  const currentRaceNumber = parseInt(id.slice(-2), 10);

  const [integratedData, navigation] = await Promise.all([
    getIntegratedRaceData(date, track, id),
    getRaceNavigation(date, track, currentRaceNumber),
  ]);

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

  const raceNumber = raceData.race_info.race_number;
  const raceName = raceData.race_info.race_name || raceData.race_info.race_condition || '';
  const raceTitle = `${track}${raceNumber}R ${raceName}`;

  // predictions.json から ARd・オッズ取得
  const predictions = getPredictionsByDate(date);
  const predRace = predictions?.races.find(r => r.race_id === raceId16);
  const predMap = new Map<number, {
    odds: number;
    arDeviation: number | null;
    predProbaP: number | null;
    predProbaW: number | null;
    marketSignal: string | null;
  }>();
  if (predRace) {
    for (const e of predRace.entries) {
      predMap.set(e.umaban, {
        odds: e.odds,
        arDeviation: e.ar_deviation ?? null,
        predProbaP: e.pred_proba_p != null ? Math.round(e.pred_proba_p * 1000) / 10 : null,
        predProbaW: e.pred_proba_w != null ? Math.round(e.pred_proba_w * 1000) / 10 : null,
        marketSignal: e.market_signal ?? null,
      });
    }
  }

  // 全馬の過去走データを並列取得
  const horseDataResults = await Promise.all(
    raceData.entries.map(async (entry) => {
      try {
        const data = await getHorseFullData(entry.horse_id);
        return { entry, data };
      } catch {
        return { entry, data: null };
      }
    })
  );

  // HorseIDMData に変換
  const horses: HorseIDMData[] = [];
  for (const { entry, data } of horseDataResults) {
    const birthDate = data?.basic?.birthDate;
    if (!birthDate || birthDate.length < 8 || !data) {
      // IDMデータなしの馬もテーブルには表示
      const pred0 = predMap.get(entry.horse_number);
      horses.push({
        horseId: entry.horse_id,
        horseName: entry.horse_name,
        horseNumber: entry.horse_number,
        waku: parseInt(entry.entry_data?.waku || '0', 10),
        birthDate: '',
        idmPoints: [],
        latestIdm: null,
        maxIdm: null,
        max5Idm: null,
        avgIdm: null,
        avg3: null,
        avg5: null,
        raceCount: 0,
        trend: 'flat',
        odds: pred0?.odds ?? null,
        arDeviation: pred0?.arDeviation ?? null,
        predProbaP: pred0?.predProbaP ?? null,
        predProbaW: pred0?.predProbaW ?? null,
        marketSignal: pred0?.marketSignal ?? null,
      });
      continue;
    }

    // 過去走からIDMポイント抽出
    const idmPoints: HorseIDMData['idmPoints'] = [];
    const idmValues: number[] = [];

    // pastRacesは新しい順 → 古い順に反転
    const sorted = data.pastRaces.slice().reverse();
    for (const r of sorted) {
      const idm = r.jrdb_idm && r.jrdb_idm !== 0 ? r.jrdb_idm : null;
      if (idm == null) continue;

      const ageMonths = calcAgeMonths(birthDate, r.date);
      idmValues.push(idm);
      idmPoints.push({
        ageMonths,
        dateNum: calcDateNum(r.date),
        idm,
        date: r.date,
        track: r.track,
        raceName: r.raceName || `${r.raceNumber}R`,
        finishPosition: r.finishPosition,
      });
    }

    const latestIdm = idmValues.length > 0 ? idmValues[idmValues.length - 1] : null;
    const maxIdm = idmValues.length > 0 ? Math.max(...idmValues) : null;
    const max5Idm = idmValues.length > 0 ? Math.max(...idmValues.slice(-5)) : null;
    const avgIdm = idmValues.length > 0
      ? idmValues.reduce((s, v) => s + v, 0) / idmValues.length
      : null;
    // 近N走平均（idmValuesは古い順なのでslice(-N)で直近N走）
    const avg3 = idmValues.length >= 3
      ? idmValues.slice(-3).reduce((s, v) => s + v, 0) / 3
      : idmValues.length > 0
        ? idmValues.reduce((s, v) => s + v, 0) / idmValues.length
        : null;
    const avg5 = idmValues.length >= 5
      ? idmValues.slice(-5).reduce((s, v) => s + v, 0) / 5
      : idmValues.length > 0
        ? idmValues.reduce((s, v) => s + v, 0) / idmValues.length
        : null;

    const pred = predMap.get(entry.horse_number);
    horses.push({
      horseId: entry.horse_id,
      horseName: entry.horse_name,
      horseNumber: entry.horse_number,
      waku: parseInt(entry.entry_data?.waku || '0', 10),
      birthDate,
      idmPoints,
      latestIdm,
      maxIdm,
      max5Idm,
      avgIdm,
      avg3,
      avg5,
      raceCount: idmPoints.length,
      trend: calcTrend(idmValues),
      odds: pred?.odds ?? null,
      arDeviation: pred?.arDeviation ?? null,
      predProbaP: pred?.predProbaP ?? null,
      predProbaW: pred?.predProbaW ?? null,
      marketSignal: pred?.marketSignal ?? null,
    });
  }

  // 馬番順ソート
  horses.sort((a, b) => a.horseNumber - b.horseNumber);

  // IDM基準値（勝ち馬平均）
  // 1) 重賞は同一レース名基準を優先 → 2) クラス別基準にフォールバック
  const idmStandards = getIDMStandards();
  let winnerIdmStandard: number | null = null;
  let gradeLabel = '';
  if (idmStandards) {
    // 同一レース名基準（重賞用）— race_name (例: "Ｇ２フィリーズＲ (牝)") で検索
    const pureRaceName = raceData.race_info.race_name || '';
    const raceNameStd = getWinnerIDMByRaceName(pureRaceName);
    if (raceNameStd?.winner_mean != null) {
      winnerIdmStandard = raceNameStd.winner_mean;
      gradeLabel = `過去${raceNameStd.count}回`;
    }

    // フォールバック: クラス別基準
    if (winnerIdmStandard == null) {
      let grade = raceData.race_info.grade || '';
      if (!grade) {
        const text = `${raceData.race_info.race_name} ${raceData.race_info.race_condition || ''}`;
        if (/Ｇ１|G1/i.test(text)) grade = 'G1';
        else if (/Ｇ２|G2/i.test(text)) grade = 'G2';
        else if (/Ｇ３|G3/i.test(text)) grade = 'G3';
        else if (/Listed|リステッド/.test(text)) grade = 'Listed';
        else if (/オープン|OP/.test(text)) grade = 'OP';
        else if (/3勝|３勝/.test(text)) grade = '3勝クラス';
        else if (/2勝|２勝/.test(text)) grade = '2勝クラス';
        else if (/1勝|１勝/.test(text)) grade = '1勝クラス';
        else if (/新馬/.test(text)) grade = '新馬';
        else if (/未勝利/.test(text)) grade = '未勝利';
      }
      if (grade) {
        const ages = raceData.entries
          .map(e => {
            const m = e.entry_data?.age?.match(/\d+/);
            return m ? parseInt(m[0], 10) : 0;
          })
          .filter(a => a > 0);
        let ageClass = '';
        if (ages.length > 0) {
          const maxAge = Math.max(...ages);
          const minAge = Math.min(...ages);
          if (maxAge === 2) ageClass = '2歳';
          else if (minAge <= 3 && maxAge === 3) ageClass = '3歳';
          else ageClass = '古馬';
        }
        const gradeKey = resolveIDMGradeKey(grade, ageClass);
        const standard = idmStandards.by_grade[gradeKey];
        if (standard?.winner) {
          winnerIdmStandard = standard.winner.mean;
          gradeLabel = gradeKey;
        }
      }
    }
  }

  const backUrl = `/races-v2/${date}/${encodeURIComponent(track)}/${id}`;

  // 競馬場切り替え時に同じレース番号を維持するためのヘルパー
  const getTrackRaceId = (targetTrack: string, raceNum: number): string => {
    if (!navigation) return '';
    const trackInfo = navigation.tracks.find((t) => t.name === targetTrack);
    if (!trackInfo) return '';
    const byNumber = trackInfo.raceByNumber?.[raceNum];
    if (byNumber) return byNumber;
    const raceByNumber = trackInfo.raceByNumber || {};
    const availableNumbers = Object.keys(raceByNumber).map(Number).filter((n) => !Number.isNaN(n));
    if (availableNumbers.length > 0) {
      availableNumbers.sort((a, b) => a - b);
      const closest = availableNumbers.reduce((prev, curr) =>
        Math.abs(curr - raceNum) < Math.abs(prev - raceNum) ? curr : prev
      );
      return raceByNumber[closest] || trackInfo.firstRaceId;
    }
    return trackInfo.firstRaceId;
  };

  return (
    <div className="container max-w-7xl mx-auto px-4 py-6">
      {/* レースナビゲーション */}
      {navigation && (
        <div className="mb-4 p-3 bg-card rounded-xl border shadow-sm">
          <div className="flex items-center gap-3">
            {/* 前のレースボタン */}
            {navigation.prevRace ? (
              <Link
                href={`/races-v2/${date}/${encodeURIComponent(navigation.prevRace.track)}/${navigation.prevRace.raceId}/idm-compare`}
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
                    href={`/races-v2/${date}/${encodeURIComponent(t.name)}/${targetRaceId}/idm-compare`}
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
                    href={`/races-v2/${date}/${encodeURIComponent(track)}/${r.raceId}/idm-compare`}
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

            {/* 次のレースボタン */}
            {navigation.nextRace ? (
              <Link
                href={`/races-v2/${date}/${encodeURIComponent(navigation.nextRace.track)}/${navigation.nextRace.raceId}/idm-compare`}
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

      {/* レース詳細に戻るリンク */}
      <div className="flex items-center gap-3 mb-6">
        <Link
          href={backUrl}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
          レース詳細に戻る
        </Link>
      </div>

      <div className="mb-6">
        <h1 className="text-xl font-bold">
          📊 指数表 — {raceTitle}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {date} ・ {horses.filter(h => h.idmPoints.length > 0).length}/{horses.length}頭のIDMデータあり
        </p>
      </div>

      {/* チャート + テーブル */}
      <IDMComparisonChart
        horses={horses}
        raceName={raceTitle}
        winnerIdmStandard={winnerIdmStandard}
        gradeLabel={gradeLabel}
      />
    </div>
  );
}
