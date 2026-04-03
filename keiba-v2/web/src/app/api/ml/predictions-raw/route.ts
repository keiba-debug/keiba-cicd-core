/**
 * ML predictions.json を直接返す API
 *
 * GET /api/ml/predictions-raw?date=YYYY-MM-DD
 * GET /api/ml/predictions-raw?date=YYYY-MM-DD&version=polaris-2.0
 * → races/YYYY/MM/DD/predictions.json (or predictions_{version}.json) の内容を返す
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const date = request.nextUrl.searchParams.get('date');
  const version = request.nextUrl.searchParams.get('version');
  if (!date) {
    return NextResponse.json({ error: 'date parameter required (YYYY-MM-DD)' }, { status: 400 });
  }

  const parts = date.split('-');
  if (parts.length !== 3) {
    return NextResponse.json({ error: 'Invalid date format. Use YYYY-MM-DD' }, { status: 400 });
  }

  const dayDir = path.join(DATA3_ROOT, 'races', parts[0], parts[1], parts[2]);
  const fileName = version ? `predictions_${version}.json` : 'predictions.json';
  const filePath = path.join(dayDir, fileName);

  if (!fs.existsSync(filePath)) {
    return NextResponse.json(
      { error: `${fileName} not found for ${date}` },
      { status: 404 },
    );
  }

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);

    // race JSONから着順データを補完
    const finishMap: Record<string, Record<number, number>> = {};
    try {
      const raceFiles = fs.readdirSync(dayDir).filter((f: string) => /^race_\d+\.json$/.test(f));
      for (const rf of raceFiles) {
        const rc = JSON.parse(fs.readFileSync(path.join(dayDir, rf), 'utf-8'));
        const raceId = rc.race_id;
        if (raceId && rc.entries) {
          const map: Record<number, number> = {};
          for (const e of rc.entries) {
            if (e.umaban != null && e.finish_position != null) {
              map[e.umaban] = e.finish_position;
            }
          }
          if (Object.keys(map).length > 0) {
            finishMap[raceId] = map;
          }
        }
      }
    } catch { /* 着順取得失敗は無視 */ }
    data.finish_positions = finishMap;

    // bets.json から買い目データをマージ（最新版のみ、バージョン指定時はスキップ）
    if (!version) {
      const betsPath = path.join(dayDir, 'bets.json');
      try {
        if (fs.existsSync(betsPath)) {
          const betsContent = fs.readFileSync(betsPath, 'utf-8');
          const betsData = JSON.parse(betsContent);
          data.recommendations = betsData.recommendations;
          data.multi_leg_recommendations = betsData.multi_leg_recommendations;
          data.sanrentan_formation = betsData.sanrentan_formation;
          data.sanrentan_distortion = betsData.sanrentan_distortion;
          data.bets_generated_at = betsData.bets_generated_at;
          data.predict_only = false;
        } else if (!data.recommendations) {
          data.predict_only = true;
        }
      } catch { /* bets.json 読み込み失敗は無視 */ }
    } else {
      data.predict_only = true;
    }

    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: `Failed to read ${fileName}`, detail: String(err) },
      { status: 500 },
    );
  }
}
