/**
 * BABA（クッション値・含水率）表示のデバッグAPI
 * GET /api/debug/baba?date=2026-01-25&track=京都&raceId=202601250809
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { getKaisaiInfoFromRaceInfo, getKaisaiInfoFromRaceInfoWithFallback } from '@/lib/jra-viewer-url';
import {
  buildRxId,
  buildRxIdCandidates,
  getBabaForRace,
  trackToSurface,
  getBabaPathForDebug,
  getSampleRxIdsFromBaba,
  getBabaCushionMapSize,
  getBabaDebugCandidatesAndVenues,
} from '@/lib/data/baba-reader';
import { BABA_DATA_PATH, DATA_ROOT } from '@/lib/config';
import { getIntegratedRaceData } from '@/lib/data/integrated-race-reader';

/** race_info.json を直接読み込む（race-reader の remark 依存を避ける） */
async function readRaceInfo(date: string): Promise<{ kaisai_data?: Record<string, Array<{ race_id?: string; race_no?: string }>> } | null> {
  const [y, m, d] = date.split('-');
  if (!y || !m || !d) return null;
  const filePath = path.join(DATA_ROOT, 'races', y, m, d, 'race_info.json');
  if (!fs.existsSync(filePath)) return null;
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content) as { kaisai_data?: Record<string, Array<{ race_id?: string; race_no?: string }>> };
  } catch {
    return null;
  }
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const date = searchParams.get('date') || '';
    const track = decodeURIComponent(searchParams.get('track') || '');
    const raceId = searchParams.get('raceId') || '';

    const [y, m, d] = date.split('-');
    const raceInfoPath = y && m && d ? path.join(DATA_ROOT, 'races', y, m, d, 'race_info.json') : '';

    const diag: Record<string, unknown> = {
      date,
      track,
      raceId,
      dataRoot: DATA_ROOT,
      raceInfoPath,
      raceInfoPathExists: raceInfoPath ? fs.existsSync(raceInfoPath) : false,
      babaConfigPath: BABA_DATA_PATH,
    };

    const pathDebug = getBabaPathForDebug();
    diag.effectiveBabaPath = pathDebug.path;
    diag.effectiveBabaPathExists = pathDebug.exists;

    if (!date || !track || !raceId) {
      return NextResponse.json({
        ok: false,
        message: 'date, track, raceId を指定してください',
        ...diag,
      });
    }

    const raceNumber = parseInt(raceId.slice(-2), 10);
    if (Number.isNaN(raceNumber)) {
      diag.raceNumberParseError = true;
      return NextResponse.json({ ok: false, ...diag });
    }

    // race_info.json（直接読み込み）
    let raceInfo: { kaisai_data?: Record<string, Array<{ race_id?: string; race_no?: string }>> } | null = null;
    try {
      raceInfo = await readRaceInfo(date);
    } catch (e) {
      diag.raceInfoError = String(e);
    }
    diag.raceInfoExists = !!raceInfo;
    diag.kaisaiDataKeys = raceInfo?.kaisai_data ? Object.keys(raceInfo.kaisai_data) : [];

    // kaisaiInfo
    let kaisaiInfo: { kai: number; nichi: number; track: string } | null = null;
    const kaisaiData = raceInfo?.kaisai_data as Record<string, Array<{ race_id: string; race_no?: string }>> | undefined;
    if (kaisaiData) {
      kaisaiInfo =
        getKaisaiInfoFromRaceInfo(kaisaiData, raceId) ??
        getKaisaiInfoFromRaceInfoWithFallback(
          kaisaiData,
          raceId,
          track,
          raceNumber
        );
    }
    diag.kaisaiInfo = kaisaiInfo;

    // RX_ID（URLの競馬場 track を優先して組み立て＝race_id の場コードが誤っている場合に対応）
    const rxId = kaisaiInfo ? buildRxId(raceId, kaisaiInfo.kai, kaisaiInfo.nichi, track) : null;
    diag.rxId = rxId;
    diag.rxIdCandidates = kaisaiInfo ? buildRxIdCandidates(raceId, kaisaiInfo.kai, kaisaiInfo.nichi, track) : [];

    // surface (芝/ダ)
    let surface: 'turf' | 'dirt' = 'turf';
    try {
      const raceData = await getIntegratedRaceData(date, track, raceId);
      surface = trackToSurface(raceData?.race_info?.track || '');
      diag.raceDataTrack = raceData?.race_info?.track;
    } catch {
      diag.raceDataError = true;
    }
    diag.surface = surface;

    // BABA（track を渡して RX_ID を正しい競馬場で組み立て）
    let babaValues: ReturnType<typeof getBabaForRace> = null;
    if (kaisaiInfo) {
      babaValues = getBabaForRace(raceId, surface, kaisaiInfo.kai, kaisaiInfo.nichi, track);
    }
    diag.babaValues = babaValues;
    diag.babaFound = !!babaValues;

    const yearNum = parseInt(raceId.substring(0, 4), 10);
    if (!Number.isNaN(yearNum)) {
      try {
        diag.sampleRxIdsInCsv = getSampleRxIdsFromBaba(yearNum, 5);
        diag.cushionMapSize = getBabaCushionMapSize(yearNum);
        const candidates = (diag.rxIdCandidates as string[]) || [];
        if (candidates.length > 0) {
          const { candidateInMap, venueCodesInCsv } = getBabaDebugCandidatesAndVenues(yearNum, candidates);
          diag.candidateInMap = candidateInMap;
          diag.venueCodesInCsv = venueCodesInCsv;
        }
      } catch {
        diag.sampleRxIdsError = true;
      }
    }

    return NextResponse.json({
      ok: !!babaValues,
      ...diag,
    });
  } catch (err) {
    return NextResponse.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : String(err),
        stack: err instanceof Error ? err.stack : undefined,
      },
      { status: 500 }
    );
  }
}
