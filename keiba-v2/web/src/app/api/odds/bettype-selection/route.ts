/**
 * 券種選択ビュー API (Session 140 / bettype-selection-roadmap Phase 3)
 *
 * GET /api/odds/bettype-selection?raceId=2026053005021102
 *
 * 軸◎から「どの券種を買うか / 降りるか」を決めた結果 (selected/skipped + 判断理由) を返す。
 * データは Python (bettype_selection.py) が書いた JSON artifact を読むだけ (SoT=Python)。
 */
import { NextRequest, NextResponse } from 'next/server';
import { getBettingSelectionByRace } from '@/lib/data/betting-selection-reader';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const raceId = req.nextUrl.searchParams.get('raceId');
  if (!raceId || raceId.length !== 16 || !/^\d{16}$/.test(raceId)) {
    return NextResponse.json({ error: 'valid 16-digit raceId required' }, { status: 400 });
  }

  const date = `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`;
  const result = getBettingSelectionByRace(raceId);
  if (!result) {
    return NextResponse.json(
      {
        error: 'artifact not generated (or race not in artifact)',
        hint: `python -m ml.strategies.bettype_selection --date ${date}`,
      },
      { status: 404 },
    );
  }

  // selection 本体 + 生成メタ (戦略・ev_floor・taste・鮮度) を返す
  return NextResponse.json(result);
}
