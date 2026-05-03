/**
 * My印からの推奨買い目抽出 API
 *
 * GET /api/my-bets/[raceId]?markSet=1
 *
 * 処理:
 *   1. raceId(16桁) から日付・場所・kai・nichi・raceNumber を抽出
 *   2. predictions.json から出走馬リスト + ML予測を取得
 *   3. My印を取得 (getRaceMarks)
 *   4. 単勝/複勝オッズ (getDbLatestOdds) + 複合オッズ (getDbAllCombinationOdds)
 *   5. EV計算 (evaluateAllCandidates) + 全戦略実行 (runAllStrategies)
 *   6. JSON返却
 */

import { NextRequest, NextResponse } from 'next/server';
import path from 'path';
import { promises as fsp } from 'fs';
import { DATA3_ROOT } from '@/lib/config';
import { getRaceMarks } from '@/lib/data/target-mark-reader';
import { getDbLatestOdds } from '@/lib/data/db-odds';
import { getDbAllCombinationOdds } from '@/lib/data/db-odds-combo';
import {
  normalizeHorses,
  evaluateAllCandidates,
  HorseInput,
} from '@/lib/my-bets/ev-calculator';
import {
  buildRaceMarksContext,
  runAllStrategies,
} from '@/lib/my-bets/strategy-presets';

// 16桁RACE_CODE: YYYYMMDD JJ KK NN RR
//                0    4   8 10 12 14
const VENUE_CODE_TO_NAME: Record<string, string> = {
  '01': '札幌',
  '02': '函館',
  '03': '福島',
  '04': '新潟',
  '05': '東京',
  '06': '中山',
  '07': '中京',
  '08': '京都',
  '09': '阪神',
  '10': '小倉',
};

interface ParsedRaceId {
  year: number;
  month: number;
  day: number;
  date: string; // YYYY-MM-DD
  venueCode: string;
  venueName: string;
  kai: number;
  nichi: number;
  raceNumber: number;
}

function parseRaceId(raceId: string): ParsedRaceId | null {
  if (!/^\d{16}$/.test(raceId)) return null;
  const year = parseInt(raceId.slice(0, 4), 10);
  const month = parseInt(raceId.slice(4, 6), 10);
  const day = parseInt(raceId.slice(6, 8), 10);
  const venueCode = raceId.slice(8, 10);
  const kai = parseInt(raceId.slice(10, 12), 10);
  const nichi = parseInt(raceId.slice(12, 14), 10);
  const raceNumber = parseInt(raceId.slice(14, 16), 10);
  const venueName = VENUE_CODE_TO_NAME[venueCode];
  if (!venueName) return null;
  return {
    year,
    month,
    day,
    date: `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`,
    venueCode,
    venueName,
    kai,
    nichi,
    raceNumber,
  };
}

interface PredictionEntry {
  umaban: number;
  horse_name: string;
  odds?: number | null;
  popularity?: number | null;
  pred_proba_p?: number;
  pred_proba_w_cal?: number | null;
}

interface PredictionRace {
  race_id: string;
  date: string;
  venue_name: string;
  race_number: number;
  race_name?: string;
  num_runners?: number;
  entries: PredictionEntry[];
}

interface PredictionsLive {
  date: string;
  races: PredictionRace[];
}

async function loadPredictionRace(
  parsed: ParsedRaceId,
  raceId: string
): Promise<PredictionRace | null> {
  const filePath = path.join(
    DATA3_ROOT,
    'races',
    String(parsed.year),
    String(parsed.month).padStart(2, '0'),
    String(parsed.day).padStart(2, '0'),
    'predictions.json'
  );
  try {
    const content = await fsp.readFile(filePath, 'utf-8');
    const data = JSON.parse(content) as PredictionsLive;
    return data.races.find((r) => r.race_id === raceId) ?? null;
  } catch {
    return null;
  }
}

/** race_*.json から出走馬リストを取る (predictions.json が無い場合のフォールバック) */
async function loadRaceJsonEntries(
  parsed: ParsedRaceId,
  raceId: string
): Promise<{ umaban: number; horse_name: string }[] | null> {
  const filePath = path.join(
    DATA3_ROOT,
    'races',
    String(parsed.year),
    String(parsed.month).padStart(2, '0'),
    String(parsed.day).padStart(2, '0'),
    `race_${raceId}.json`
  );
  try {
    const content = await fsp.readFile(filePath, 'utf-8');
    interface RaceJson {
      entries?: { umaban: number; horse_name: string }[];
    }
    const data = JSON.parse(content) as RaceJson;
    if (!data.entries) return null;
    return data.entries.map((e) => ({
      umaban: e.umaban,
      horse_name: e.horse_name,
    }));
  } catch {
    return null;
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ raceId: string }> }
) {
  const { raceId } = await params;
  const url = new URL(req.url);
  const markSet = parseInt(url.searchParams.get('markSet') ?? '1', 10);

  const parsed = parseRaceId(raceId);
  if (!parsed) {
    return NextResponse.json({ error: 'invalid raceId' }, { status: 400 });
  }

  // 並列でデータ取得
  const [predictionRace, marks, latestOdds, comboOdds] = await Promise.all([
    loadPredictionRace(parsed, raceId),
    Promise.resolve(
      getRaceMarks(
        parsed.year,
        parsed.kai,
        parsed.nichi,
        parsed.raceNumber,
        parsed.venueName,
        markSet
      )
    ),
    getDbLatestOdds(raceId),
    getDbAllCombinationOdds(raceId),
  ]);

  // 出走馬リスト確定 (predictions優先、なければrace_json)
  let entries: PredictionEntry[];
  if (predictionRace?.entries && predictionRace.entries.length > 0) {
    entries = predictionRace.entries;
  } else {
    const fallback = await loadRaceJsonEntries(parsed, raceId);
    if (!fallback || fallback.length === 0) {
      return NextResponse.json(
        { error: 'race entries not found', raceId },
        { status: 404 }
      );
    }
    entries = fallback.map((e) => ({
      umaban: e.umaban,
      horse_name: e.horse_name,
    }));
  }

  // tansho/fukushoマップ構築
  const tanshoMap = new Map<number, { odds: number; ninki: number | null }>();
  const fukushoMap = new Map<
    number,
    { oddsMin: number; oddsMax: number; ninki: number | null }
  >();
  for (const h of latestOdds.horses) {
    if (h.winOdds !== null) {
      tanshoMap.set(h.umaban, { odds: h.winOdds, ninki: h.ninki });
    }
    if (h.placeOddsMin !== null) {
      fukushoMap.set(h.umaban, {
        oddsMin: h.placeOddsMin,
        oddsMax: h.placeOddsMax ?? h.placeOddsMin,
        ninki: h.ninki,
      });
    }
  }

  // 印マップ
  const horseToMark: Record<number, string> = {};
  if (marks?.horseMarks) {
    for (const [umaStr, mark] of Object.entries(marks.horseMarks)) {
      horseToMark[parseInt(umaStr, 10)] = mark;
    }
  }

  // HorseInput構築
  const horseInputs: HorseInput[] = entries.map((e) => {
    const t = tanshoMap.get(e.umaban);
    const f = fukushoMap.get(e.umaban);
    return {
      umaban: e.umaban,
      mark: horseToMark[e.umaban] ?? '',
      mlWinProba: e.pred_proba_w_cal ?? null,
      mlPlaceProba: e.pred_proba_p ?? null,
      winOdds: t?.odds ?? e.odds ?? null,
      placeOddsMin: f?.oddsMin ?? null,
      placeOddsMax: f?.oddsMax ?? null,
    };
  });

  const normalized = normalizeHorses(horseInputs);

  const candidates = evaluateAllCandidates(
    normalized,
    {
      ...comboOdds,
      tansho: tanshoMap,
      fukusho: fukushoMap,
    },
    horseToMark
  );

  const ctx = buildRaceMarksContext(horseToMark, entries.length);
  const strategies = runAllStrategies(ctx, candidates);

  // 馬名マップ（UI表示用）
  const horseNames: Record<number, string> = {};
  for (const e of entries) horseNames[e.umaban] = e.horse_name;

  return NextResponse.json({
    raceId,
    date: parsed.date,
    venue: parsed.venueName,
    raceNumber: parsed.raceNumber,
    raceName: predictionRace?.race_name ?? null,
    markSet,
    horseNames,
    horseToMark,
    markCounts: {
      '◎': ctx.byMark['◎'].length,
      '○': ctx.byMark['○'].length,
      '▲': ctx.byMark['▲'].length,
      '△': ctx.byMark['△'].length,
      '★': ctx.byMark['★'].length,
      '穴': ctx.byMark['穴'].length,
      '無印': entries.length - ctx.markedCount,
    },
    oddsAvailable: {
      tansho: tanshoMap.size,
      fukusho: fukushoMap.size,
      ...comboOdds.counts,
    },
    candidates: {
      total: candidates.length,
      // 全候補は重い → 上位50件のみ含める
      topByEv: [...candidates].sort((a, b) => b.ev - a.ev).slice(0, 50),
    },
    strategies,
  });
}
