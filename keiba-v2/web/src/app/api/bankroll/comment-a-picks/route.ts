/**
 * コメAI picks (深読み三点の選定源) の当日Ａ印を返す API
 *
 * GET /api/bankroll/comment-a-picks?date=YYYY-MM-DD
 * → comment_llm/live/picks_YYYY-MM-DD.json の confidence=="高" (Ａ印) のみ抽出。
 *   ファイル不存在/Ａ印ゼロは races: [] (深読み三点スリーブの no-op と同じ扱い)。
 *   選定・R4判定の canonical は ml/strategies/comment_a_live.py select_comment_a —
 *   web 側は ExecuteTab が predictions と突合して同ロジックを TS で再現する。
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface RawPick {
  umaban?: number;
  name?: string;
  odds?: number;
  rank?: number;
  confidence?: string;
  reason?: string;
}

interface RawRace {
  race_id?: string;
  venue?: string;
  rno?: number;
  picks?: RawPick[];
}

export async function GET(request: NextRequest) {
  const date = request.nextUrl.searchParams.get('date');
  if (!date || date.split('-').length !== 3) {
    return NextResponse.json({ error: 'date parameter required (YYYY-MM-DD)' }, { status: 400 });
  }

  const filePath = path.join(DATA3_ROOT, 'comment_llm', 'live', `picks_${date}.json`);
  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ date, races: [] });
  }

  try {
    const races: RawRace[] = JSON.parse(fs.readFileSync(filePath, 'utf-8')) || [];
    const out = [];
    for (const r of races) {
      if (!r?.race_id) continue;
      const aPicks = (r.picks || [])
        .filter((p) => p?.confidence === '高' && p.umaban != null)
        .map((p) => ({
          umaban: p.umaban,
          name: p.name ?? '',
          rank: p.rank ?? null,
          reason: p.reason ?? '',
        }));
      if (aPicks.length > 0) {
        out.push({ race_id: String(r.race_id), picks: aPicks });
      }
    }
    return NextResponse.json({ date, races: out });
  } catch {
    // 壊れた picks は空扱い (安全側・Python 側 _picks_by_race と同じ)
    return NextResponse.json({ date, races: [] });
  }
}
