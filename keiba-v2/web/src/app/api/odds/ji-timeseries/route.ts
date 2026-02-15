/**
 * 時系列オッズ取得API
 *
 * GET /api/odds/ji-timeseries?raceId=2026013105010101
 *
 * データソース優先順位:
 * 1. mykeibadb (odds1_tansho_jikeiretsu) ← 最新・推奨
 * 2. JI_2026 JTファイル ← フォールバック
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  getJiOddsTimeSeries,
  isRtDataAvailable,
  calculateLastMinuteChanges,
} from '@/lib/data/rt-data-reader';
import {
  getHorseInfoByUmaban,
  lookupHorseInfo,
} from '@/lib/data/race-horse-names';
import { getDbOddsAllTimeSeries } from '@/lib/data/db-odds';
import type { DbOddsSnapshot } from '@/lib/data/db-odds';

/** DB版: 直前変動を計算 */
function calcDbLastMinuteChanges(snapshots: DbOddsSnapshot[]) {
  if (snapshots.length < 5) return [];

  const last = snapshots[snapshots.length - 1];
  const lastTimeLabel = last.timeLabel; // "HH:mm"
  const lastMinutes = parseTimeToMinutes(lastTimeLabel);

  // 10分前のスナップショットを探す
  let before: DbOddsSnapshot | null = null;
  for (let i = snapshots.length - 2; i >= 0; i--) {
    const mins = parseTimeToMinutes(snapshots[i].timeLabel);
    const diff = lastMinutes - mins;
    if (diff >= 8 && diff <= 15) {
      before = snapshots[i];
      break;
    }
  }
  // 時刻ベースで見つからなければインデックスベース
  if (!before && snapshots.length > 10) {
    before = snapshots[snapshots.length - 11];
  } else if (!before && snapshots.length > 3) {
    before = snapshots[Math.floor(snapshots.length / 2)];
  }
  if (!before) return [];

  const allUmaban = new Set([...Object.keys(before.odds), ...Object.keys(last.odds)]);
  const changes: Array<{
    umaban: string;
    beforeOdds: number | null;
    finalOdds: number | null;
    change: number | null;
    changePercent: number | null;
    level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown';
  }> = [];

  for (const umaban of allUmaban) {
    const beforeOdds = before.odds[umaban] ?? null;
    const finalOdds = last.odds[umaban] ?? null;
    let change: number | null = null;
    let changePercent: number | null = null;
    let level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown' = 'unknown';

    if (beforeOdds != null && beforeOdds > 0 && finalOdds != null && finalOdds > 0) {
      change = finalOdds - beforeOdds;
      changePercent = (change / beforeOdds) * 100;
      if (changePercent <= -15) level = 'hot';
      else if (changePercent <= -5) level = 'warm';
      else if (changePercent >= 10) level = 'cold';
      else level = 'stable';
    }
    changes.push({ umaban, beforeOdds, finalOdds, change, changePercent, level });
  }
  return changes.sort((a, b) => (parseInt(a.umaban, 10) || 99) - (parseInt(b.umaban, 10) || 99));
}

function parseTimeToMinutes(timeLabel: string): number {
  const m = timeLabel.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return 0;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const raceId = searchParams.get('raceId');

  if (!raceId || raceId.length !== 16) {
    return NextResponse.json(
      {
        error: 'raceId required (16 digits)',
        example: '/api/odds/ji-timeseries?raceId=2026013105010101',
      },
      { status: 400 }
    );
  }

  // 馬情報を取得（共通）
  const horseInfo = getHorseInfoByUmaban(raceId);

  // --- 1. DB優先 ---
  const dbResult = await getDbOddsAllTimeSeries(raceId);
  if (dbResult.source === 'db-timeseries' && dbResult.snapshotCount > 0) {
    const allSnapshots = dbResult.snapshots;

    // サンプリング（最大50件）
    let sampled = allSnapshots;
    if (allSnapshots.length > 50) {
      const step = Math.ceil(allSnapshots.length / 50);
      sampled = allSnapshots.filter((_, i) => i % step === 0 || i === allSnapshots.length - 1);
    }

    // 全馬番抽出
    const allUmaban = new Set<string>();
    for (const s of allSnapshots) {
      for (const ub of Object.keys(s.odds)) allUmaban.add(ub);
    }

    // 直前変動計算
    const lastMinuteChanges = calcDbLastMinuteChanges(allSnapshots);

    // 馬情報付与
    const horses = Array.from(allUmaban)
      .sort((a, b) => parseInt(a, 10) - parseInt(b, 10))
      .map((ub) => {
        const info = lookupHorseInfo(horseInfo, ub);
        const change = lastMinuteChanges.find(
          (c) => c.umaban === ub || c.umaban === ub.replace(/^0+/, '')
        );
        return {
          umaban: ub,
          horseName: info?.horseName || `${ub}番`,
          waku: info?.waku,
          finishPosition: info?.finishPosition,
          lastMinute: change || null,
        };
      });

    return NextResponse.json({
      raceId,
      source: 'db',
      snapshotCount: allSnapshots.length,
      sampledCount: sampled.length,
      firstTime: dbResult.firstTime,
      lastTime: dbResult.lastTime,
      horses,
      timeSeries: sampled,
      lastMinuteChanges,
    });
  }

  // --- 2. JIファイルフォールバック ---
  if (!isRtDataAvailable()) {
    return NextResponse.json(
      { error: 'No odds data available', raceId, hint: 'DBにもJIファイルにもデータがありません' },
      { status: 404 }
    );
  }

  const timeSeries = getJiOddsTimeSeries(raceId);
  if (timeSeries.length === 0) {
    return NextResponse.json(
      { error: 'Time series data not found', raceId, hint: 'DBにもJIファイルにも時系列データがありません' },
      { status: 404 }
    );
  }

  const allUmaban = new Set<string>();
  for (const snapshot of timeSeries) {
    for (const ub of Object.keys(snapshot.odds)) allUmaban.add(ub);
  }

  const horses = Array.from(allUmaban)
    .sort((a, b) => parseInt(a, 10) - parseInt(b, 10))
    .map((ub) => {
      const info = lookupHorseInfo(horseInfo, ub);
      return {
        umaban: ub,
        horseName: info?.horseName || `${ub}番`,
        waku: info?.waku,
        finishPosition: info?.finishPosition,
      };
    });

  let sampledTimeSeries = timeSeries;
  if (timeSeries.length > 50) {
    const step = Math.ceil(timeSeries.length / 50);
    sampledTimeSeries = timeSeries.filter((_, i) => i % step === 0 || i === timeSeries.length - 1);
  }

  const lastMinuteChanges = calculateLastMinuteChanges(raceId);

  const horsesWithChanges = horses.map((h) => {
    const change = lastMinuteChanges.find(
      (c) => c.umaban === h.umaban || c.umaban === h.umaban.replace(/^0+/, '')
    );
    return { ...h, lastMinute: change || null };
  });

  return NextResponse.json({
    raceId,
    source: 'file',
    snapshotCount: timeSeries.length,
    sampledCount: sampledTimeSeries.length,
    firstTime: timeSeries[0]?.timeLabel || '',
    lastTime: timeSeries[timeSeries.length - 1]?.timeLabel || '',
    horses: horsesWithChanges,
    timeSeries: sampledTimeSeries,
    lastMinuteChanges,
  });
}
