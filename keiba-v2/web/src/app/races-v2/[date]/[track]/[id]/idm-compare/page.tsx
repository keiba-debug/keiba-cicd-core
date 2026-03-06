/**
 * IDM比較ページ
 * レース全出走馬のIDM成長曲線を重ねて比較
 */

import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Link from 'next/link';
import { ChevronLeft } from 'lucide-react';
import { getIntegratedRaceData } from '@/lib/data/integrated-race-reader';
import { getV4RaceData } from '@/lib/data/v4-race-reader';
import { getKbExtData } from '@/lib/data/v4-keibabook-reader';
import { adaptV4ToIntegrated } from '@/lib/data/v4-race-adapter';
import { getHorseFullData } from '@/lib/data/horse-data-reader';
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

// エポック月 (YYYY*12 + monthIndex) — X軸用
function calcDateNum(raceDate: string): number {
  const clean = raceDate.replace(/[/-]/g, '');
  const y = parseInt(clean.slice(0, 4), 10);
  const m = parseInt(clean.slice(4, 6), 10);
  return y * 12 + (m - 1);
}

// ── トレンド判定 ──

function calcTrend(idmValues: number[]): 'up' | 'flat' | 'down' {
  if (idmValues.length < 3) return 'flat';
  const recent3 = idmValues.slice(-3);
  const prior = idmValues.slice(-6, -3);
  if (prior.length === 0) return 'flat';
  const recentAvg = recent3.reduce((s, v) => s + v, 0) / recent3.length;
  const priorAvg = prior.reduce((s, v) => s + v, 0) / prior.length;
  const diff = recentAvg - priorAvg;
  if (diff > 2) return 'up';
  if (diff < -2) return 'down';
  return 'flat';
}

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
    title: `IDM比較 ${displayTrack}${raceNumber}R ${raceName} (${shortDate})`,
  };
}

// ── ページ本体 ──

export default async function IDMComparePage({ params }: PageParams) {
  const { date, track: encodedTrack, id } = await params;
  const track = decodeURIComponent(encodedTrack);

  // レースデータ取得（既存パターン）
  const raceId16 = resolveRaceId16(date, track, id);
  const [integratedData] = await Promise.all([
    getIntegratedRaceData(date, track, id),
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
      horses.push({
        horseId: entry.horse_id,
        horseName: entry.horse_name,
        horseNumber: entry.horse_number,
        waku: parseInt(entry.entry_data?.waku || '0', 10),
        birthDate: '',
        idmPoints: [],
        latestIdm: null,
        maxIdm: null,
        avgIdm: null,
        avg3: null,
        avg5: null,
        raceCount: 0,
        trend: 'flat',
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

    horses.push({
      horseId: entry.horse_id,
      horseName: entry.horse_name,
      horseNumber: entry.horse_number,
      waku: parseInt(entry.entry_data?.waku || '0', 10),
      birthDate,
      idmPoints,
      latestIdm,
      maxIdm,
      avgIdm,
      avg3,
      avg5,
      raceCount: idmPoints.length,
      trend: calcTrend(idmValues),
    });
  }

  // 馬番順ソート
  horses.sort((a, b) => a.horseNumber - b.horseNumber);

  const backUrl = `/races-v2/${date}/${encodeURIComponent(track)}/${id}`;

  return (
    <div className="container max-w-7xl mx-auto px-4 py-6">
      {/* ヘッダー */}
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
          📊 IDM比較 — {raceTitle}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {date} ・ {horses.filter(h => h.idmPoints.length > 0).length}/{horses.length}頭のIDMデータあり
        </p>
      </div>

      {/* チャート + テーブル */}
      <IDMComparisonChart horses={horses} raceName={raceTitle} />
    </div>
  );
}
