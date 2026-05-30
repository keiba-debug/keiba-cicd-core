/**
 * 券種効率ビュー API (Session 138 / bettype-selection-roadmap Phase 2)
 *
 * GET /api/odds/bettype-efficiency?raceId=2026053005021101
 *
 * ハーヴィル確率 × 市場オッズ で各券種プランの
 * (的中確率, 合成オッズ, 期待リターン) を返す。 合成オッズ<単オッズ を可視化する。
 * データは Python (bettype_efficiency.py) が書いた JSON artifact を読むだけ。
 */
import { NextRequest, NextResponse } from 'next/server';
import { getBetTypeEfficiencyByDate } from '@/lib/data/bettype-efficiency-reader';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const raceId = req.nextUrl.searchParams.get('raceId');
  if (!raceId || raceId.length !== 16 || !/^\d{16}$/.test(raceId)) {
    return NextResponse.json({ error: 'valid 16-digit raceId required' }, { status: 400 });
  }

  const date = `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`;
  const file = getBetTypeEfficiencyByDate(date);
  if (!file) {
    return NextResponse.json(
      {
        error: 'artifact not generated',
        hint: `python -m ml.strategies.bettype_efficiency --date ${date}`,
      },
      { status: 404 },
    );
  }

  const race = file.races.find((r) => String(r.race_id) === String(raceId));
  if (!race) {
    return NextResponse.json({ error: 'race not found in artifact' }, { status: 404 });
  }

  // generated_at を返してフロントで鮮度 (オッズの古さ) を表示できるようにする
  return NextResponse.json({ race, generated_at: file.generated_at });
}
