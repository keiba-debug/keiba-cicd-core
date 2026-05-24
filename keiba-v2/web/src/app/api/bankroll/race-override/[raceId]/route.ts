/**
 * レース上書き API (per_race_max_yen を 1 レース単位で上書き)
 *
 * PUT  /api/bankroll/race-override/{raceId}   { per_race_max_yen, reason }
 * DELETE /api/bankroll/race-override/{raceId}
 *
 * 設計背景: docs/auto-purchase/10_BANKROLL_CONTROL.md §3, §4.2
 * 「このレースは1万単で勝負」のような個別判断を、reason 必須で記録する。
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  updateConfigLocked,
  isValidRaceId,
  type RaceOverride,
} from '@/lib/bankroll/limit-resolver';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface PutBody {
  per_race_max_yen?: number;
  reason?: string;
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ raceId: string }> }
) {
  const { raceId } = await params;
  if (!isValidRaceId(raceId)) {
    return NextResponse.json({ error: 'invalid raceId (16-digit required)' }, { status: 400 });
  }

  let body: PutBody;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 });
  }

  const amount = body.per_race_max_yen;
  const reason = (body.reason ?? '').trim();
  if (typeof amount !== 'number' || !Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json({ error: 'per_race_max_yen must be positive number' }, { status: 400 });
  }
  if (!reason) {
    // 10 §7 #4: reason 必須 (UI バリデーション + サーバ強制)
    return NextResponse.json({ error: 'reason is required (10_BANKROLL_CONTROL §4.2)' }, { status: 400 });
  }

  const override: RaceOverride = {
    per_race_max_yen: Math.floor(amount),
    reason,
    created_at: new Date().toISOString(),
  };

  try {
    await updateConfigLocked(
      (before) => {
        const after = JSON.parse(JSON.stringify(before)) as typeof before;
        after.race_overrides = after.race_overrides ?? {};
        after.race_overrides[raceId] = override;
        return after;
      },
      `race_override_put:${raceId}`
    );
  } catch (e) {
    console.error('[race-override] write failed:', e);
    return NextResponse.json(
      { error: 'failed to write config', details: String(e) },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, raceId, override });
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ raceId: string }> }
) {
  const { raceId } = await params;
  if (!isValidRaceId(raceId)) {
    return NextResponse.json({ error: 'invalid raceId (16-digit required)' }, { status: 400 });
  }

  let removedOverride: RaceOverride | undefined;
  try {
    const after = await updateConfigLocked(
      (before) => {
        const next = JSON.parse(JSON.stringify(before)) as typeof before;
        if (next.race_overrides && raceId in next.race_overrides) {
          removedOverride = next.race_overrides[raceId];
          delete next.race_overrides[raceId];
        }
        return next;
      },
      `race_override_delete:${raceId}`
    );
    // lock 内で実際に消えたかは removedOverride で判別
    if (!removedOverride) {
      return NextResponse.json({ success: true, raceId, removed: false });
    }
    void after; // history は updateConfigLocked が記録済
  } catch (e) {
    console.error('[race-override] write failed:', e);
    return NextResponse.json(
      { error: 'failed to write config', details: String(e) },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, raceId, removed: true, removedOverride });
}
