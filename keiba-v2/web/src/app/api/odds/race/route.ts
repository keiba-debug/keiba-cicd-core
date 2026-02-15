/**
 * オッズ取得API
 *
 * GET /api/odds/race?raceId=2026013105010101
 * GET /api/odds/race?date=2026-01-31&track=東京&raceNumber=1
 *
 * RT_DATA から単複枠オッズを取得
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  getRaceOddsFromRt,
  isRtDataAvailable,
  calculateOddsChanges,
  getOddsTimeSeries,
  getJiOddsTimeSeries,
  calculateJiOddsChanges,
} from '@/lib/data/rt-data-reader';
import { lookupRace } from '@/lib/data/race-lookup';
import {
  getHorseInfoByUmaban,
  lookupHorseInfo,
  resolveKeibabookRaceId,
  getRaceConditionInfo,
} from '@/lib/data/race-horse-names';
import { analyzeOddsPattern } from '@/lib/data/rt-data-types';
import type { HorseOdds } from '@/lib/data/rt-data-types';
import { getDbLatestOdds, extractTimeLabel } from '@/lib/data/db-odds';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

function normalizeDate(dateStr: string): string | null {
  const m1 = dateStr.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if (m1) {
    return `${m1[1]}${m1[2].padStart(2, '0')}${m1[3].padStart(2, '0')}`;
  }
  const m2 = dateStr.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (m2) return dateStr;
  return null;
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const raceId = searchParams.get('raceId');
  const date = searchParams.get('date');
  const track = searchParams.get('track');
  const raceNumber = searchParams.get('raceNumber');

  let targetRaceId: string | null = raceId ?? null;

  if (!targetRaceId && date && track && raceNumber) {
    const yyyymmdd = normalizeDate(date);
    if (!yyyymmdd) {
      return NextResponse.json(
        { error: 'Invalid date format. Use YYYYMMDD or YYYY/MM/DD' },
        { status: 400 }
      );
    }
    const result = await lookupRace({
      date: date.includes('/') ? date : `${date.slice(0, 4)}/${date.slice(4, 6)}/${date.slice(6, 8)}`,
      track,
      raceNumber: parseInt(raceNumber, 10),
    });
    targetRaceId = result?.raceId ?? null;
  }

  if (!targetRaceId || targetRaceId.length !== 16) {
    return NextResponse.json(
      {
        error: 'raceId required',
        example: '/api/odds/race?raceId=2026013105010101',
        or: '/api/odds/race?date=2026-01-31&track=東京&raceNumber=1',
      },
      { status: 400 }
    );
  }

  // 馬情報（DB/RTパス共通）
  const horseInfo = getHorseInfoByUmaban(targetRaceId);

  // keibabookRaceId（共通）
  const year = targetRaceId.substring(0, 4);
  const month = targetRaceId.substring(4, 6);
  const day = targetRaceId.substring(6, 8);
  const dayPath = path.join(DATA3_ROOT, 'races', year, month, day);
  const keibabookRaceId = resolveKeibabookRaceId(targetRaceId, dayPath);

  // レース条件（共通）
  const raceCondition = getRaceConditionInfo(targetRaceId);

  // --- 1. DB優先 ---
  const dbOdds = await getDbLatestOdds(targetRaceId);
  if (dbOdds.source !== 'none' && dbOdds.horses.length > 0) {
    const horses: HorseOdds[] = dbOdds.horses.map((h) => {
      const ub = String(h.umaban);
      const info = lookupHorseInfo(horseInfo, ub);
      return {
        umaban: ub,
        winOdds: h.winOdds,
        placeOddsMin: h.placeOddsMin,
        placeOddsMax: h.placeOddsMax,
        ninki: h.ninki,
        horseName: info?.horseName,
        waku: info?.waku,
        honshiMark: info?.honshiMark,
        jockey: info?.jockey,
        aiIndex: info?.aiIndex,
        rating: info?.rating,
        lastResult: info?.lastResult,
        finishPosition: info?.finishPosition,
        finishTime: info?.finishTime,
        finalOdds: info?.finalOdds,
        finalNinki: info?.finalNinki,
        oddsTrend: h.oddsTrend ?? undefined,
        firstOdds: h.firstWinOdds,
        oddsChange: (h.winOdds != null && h.firstWinOdds != null)
          ? h.winOdds - h.firstWinOdds : null,
        oddsChangePercent: (h.winOdds != null && h.firstWinOdds != null && h.firstWinOdds > 0)
          ? ((h.winOdds - h.firstWinOdds) / h.firstWinOdds) * 100 : null,
      };
    });

    const analysis = analyzeOddsPattern(horses);

    const timeSeriesSummary = dbOdds.snapshotCount >= 2 ? {
      firstTime: dbOdds.firstSnapshotTime ? extractTimeLabel(dbOdds.firstSnapshotTime) : '',
      lastTime: dbOdds.snapshotTime ? extractTimeLabel(dbOdds.snapshotTime) : '',
      snapshotCount: dbOdds.snapshotCount,
      source: 'DB' as const,
    } : undefined;

    return NextResponse.json({
      raceId: targetRaceId,
      source: 'DB',
      horses,
      keibabookRaceId: keibabookRaceId ?? undefined,
      raceCondition: raceCondition ?? undefined,
      analysis: analysis.pattern !== 'normal' ? analysis : undefined,
      timeSeriesSummary,
    });
  }

  // --- 2. RT_DATAフォールバック ---
  if (!isRtDataAvailable()) {
    return NextResponse.json(
      { error: 'No odds data available', raceId: targetRaceId, hint: 'DBにもRT_DATAにもデータがありません' },
      { status: 404 }
    );
  }

  const odds = getRaceOddsFromRt(targetRaceId);
  if (!odds) {
    return NextResponse.json(
      {
        error: 'Odds not found',
        raceId: targetRaceId,
        hint: '該当レースの RT_DATA ファイルが存在しないか、レース前です',
      },
      { status: 404 }
    );
  }

  // 馬名・枠番等を付与
  if (Object.keys(horseInfo).length > 0) {
    odds.horses = odds.horses.map((h) => {
      const info = lookupHorseInfo(horseInfo, h.umaban);
      return {
        ...h,
        horseName: info?.horseName,
        waku: info?.waku,
        honshiMark: info?.honshiMark,
        jockey: info?.jockey,
        aiIndex: info?.aiIndex,
        rating: info?.rating,
        lastResult: info?.lastResult,
        finishPosition: info?.finishPosition,
        finishTime: info?.finishTime,
        finalOdds: info?.finalOdds,
        finalNinki: info?.finalNinki,
      };
    });
  }

  const analysis = analyzeOddsPattern(odds.horses);

  // 時系列変動情報（JI_2026優先→RT_DATA）
  let timeSeries = getJiOddsTimeSeries(targetRaceId);
  let oddsChanges = calculateJiOddsChanges(targetRaceId);
  let timeSeriesSource: 'JI' | 'RT' | undefined;

  if (timeSeries.length >= 2) {
    timeSeriesSource = 'JI';
  } else {
    timeSeries = getOddsTimeSeries(targetRaceId);
    oddsChanges = calculateOddsChanges(targetRaceId);
    if (timeSeries.length >= 2) {
      timeSeriesSource = 'RT';
    }
  }

  if (oddsChanges.length > 0) {
    const changeMap = new Map(oddsChanges.map((c) => [c.umaban, c]));
    odds.horses = odds.horses.map((h) => {
      const change = changeMap.get(h.umaban) ?? changeMap.get(h.umaban.replace(/^0+/, ''));
      if (change) {
        return {
          ...h,
          oddsTrend: change.trend,
          oddsChange: change.change,
          oddsChangePercent: change.changePercent,
          firstOdds: change.firstOdds,
        };
      }
      return h;
    });
  }

  const timeSeriesSummary =
    timeSeries.length >= 2
      ? {
          firstTime: timeSeries[0].timeLabel,
          lastTime: timeSeries[timeSeries.length - 1].timeLabel,
          snapshotCount: timeSeries.length,
          source: timeSeriesSource,
        }
      : undefined;

  return NextResponse.json({
    ...odds,
    keibabookRaceId: keibabookRaceId ?? undefined,
    raceCondition: raceCondition ?? undefined,
    analysis: analysis.pattern !== 'normal' ? analysis : undefined,
    timeSeriesSummary,
  });
}
