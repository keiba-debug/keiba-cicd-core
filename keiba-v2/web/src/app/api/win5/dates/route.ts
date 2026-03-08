/**
 * WIN5 利用可能日付 API
 * GET /api/win5/dates
 *
 * - dates: win5_picks.json が存在する日付（生成済み、新しい順）
 * - pendingDates: predictions.json はあるが win5_picks.json がない日付（未生成、新しい順）
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export async function GET() {
  const racesRoot = path.join(DATA3_ROOT, 'races');
  const dates: string[] = [];
  const pendingDates: string[] = [];

  try {
    const years = fs.readdirSync(racesRoot).filter(y => /^\d{4}$/.test(y)).sort().reverse();
    for (const yyyy of years) {
      const yearDir = path.join(racesRoot, yyyy);
      const months = fs.readdirSync(yearDir).filter(m => /^\d{2}$/.test(m)).sort().reverse();
      for (const mm of months) {
        const monthDir = path.join(yearDir, mm);
        const days = fs.readdirSync(monthDir).filter(d => /^\d{2}$/.test(d)).sort().reverse();
        for (const dd of days) {
          const dayDir = path.join(monthDir, dd);
          const picksPath = path.join(dayDir, 'win5_picks.json');
          const predsPath = path.join(dayDir, 'predictions.json');
          if (fs.existsSync(picksPath)) {
            dates.push(`${yyyy}-${mm}-${dd}`);
          } else if (fs.existsSync(predsPath)) {
            pendingDates.push(`${yyyy}-${mm}-${dd}`);
          }
        }
      }
    }
  } catch {
    // ignore
  }

  return NextResponse.json({ dates, pendingDates });
}
