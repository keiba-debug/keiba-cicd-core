/**
 * WIN5 利用可能日付 API
 * GET /api/win5/dates
 *
 * win5_picks.json が存在する日付の一覧を返す（新しい順）
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export async function GET() {
  const racesRoot = path.join(DATA3_ROOT, 'races');
  const dates: string[] = [];

  try {
    const years = fs.readdirSync(racesRoot).filter(y => /^\d{4}$/.test(y)).sort().reverse();
    for (const yyyy of years) {
      const yearDir = path.join(racesRoot, yyyy);
      const months = fs.readdirSync(yearDir).filter(m => /^\d{2}$/.test(m)).sort().reverse();
      for (const mm of months) {
        const monthDir = path.join(yearDir, mm);
        const days = fs.readdirSync(monthDir).filter(d => /^\d{2}$/.test(d)).sort().reverse();
        for (const dd of days) {
          const picksPath = path.join(monthDir, dd, 'win5_picks.json');
          if (fs.existsSync(picksPath)) {
            dates.push(`${yyyy}-${mm}-${dd}`);
          }
        }
      }
    }
  } catch {
    // ignore
  }

  return NextResponse.json({ dates });
}
