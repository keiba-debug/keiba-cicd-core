/**
 * データ登録状況 API
 * 直近N週分の日付ごとのデータ状況を返す
 */
import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

const INDEX_FILE = path.join(DATA3_ROOT, 'indexes', 'race_date_index.json');

export interface DateDataStatus {
  date: string;             // YYYY-MM-DD
  indexCount: number;       // race_date_index のレース数
  raceJsonCount: number;    // race JSON ファイル数
  kbRate: number;           // has_keibabook_ext=true の割合 (0-100)
  hasResults: boolean;      // finish_position が1件以上ある
  hasPredictions: boolean;  // predictions.json が存在
  predictionsAt?: string;   // predictions.json の created_at
}

function parseRacesDir(dateStr: string): {
  raceJsonCount: number;
  kbCount: number;
  hasResults: boolean;
  hasPredictions: boolean;
  predictionsAt?: string;
} {
  const [year, month, day] = dateStr.split('-');
  const raceDir = path.join(DATA3_ROOT, 'races', year, month, day);

  if (!fs.existsSync(raceDir)) {
    return { raceJsonCount: 0, kbCount: 0, hasResults: false, hasPredictions: false };
  }

  let raceJsonCount = 0;
  let kbCount = 0;
  let hasResults = false;
  let hasPredictions = false;
  let predictionsAt: string | undefined;

  const files = fs.readdirSync(raceDir);

  for (const file of files) {
    if (file === 'predictions.json') {
      hasPredictions = true;
      try {
        const raw = fs.readFileSync(path.join(raceDir, file), 'utf-8');
        const data = JSON.parse(raw);
        predictionsAt = data.created_at;
      } catch { /* ignore */ }
      continue;
    }

    // race_XXXXXXXXXXXXXXXX.json (16桁レースID)
    if (!/^race_\d{16}\.json$/.test(file)) continue;

    raceJsonCount++;
    try {
      const raw = fs.readFileSync(path.join(raceDir, file), 'utf-8');
      const data = JSON.parse(raw);

      // has_keibabook_ext
      if (data?.meta?.has_keibabook_ext === true) {
        kbCount++;
      }

      // 成績判定: finish_position が数値で入っている
      if (!hasResults) {
        const entries: Array<{ finish_position?: number | null }> = data?.entries || [];
        if (entries.some((e) => typeof e.finish_position === 'number' && e.finish_position > 0)) {
          hasResults = true;
        }
      }
    } catch { /* ignore */ }
  }

  return { raceJsonCount, kbCount, hasResults, hasPredictions, predictionsAt };
}

export async function GET() {
  try {
    if (!fs.existsSync(INDEX_FILE)) {
      return NextResponse.json({ dates: [], error: 'race_date_index not found' });
    }

    const raw = fs.readFileSync(INDEX_FILE, 'utf-8');
    const indexData = JSON.parse(raw) as Record<
      string,
      { tracks: Array<{ races: unknown[] }> }
    >;

    // 全日付を降順ソート、直近12週（84日）
    const allDates = Object.keys(indexData).sort((a, b) => b.localeCompare(a));
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 84);
    const cutoffStr = cutoff.toISOString().substring(0, 10);

    const targetDates = allDates.filter((d) => d >= cutoffStr);

    const result: DateDataStatus[] = targetDates.map((date) => {
      const entry = indexData[date];
      const indexCount = entry.tracks.reduce((sum, t) => sum + t.races.length, 0);

      const { raceJsonCount, kbCount, hasResults, hasPredictions, predictionsAt } =
        parseRacesDir(date);

      const kbRate = raceJsonCount > 0 ? Math.round((kbCount / raceJsonCount) * 100) : 0;

      return {
        date,
        indexCount,
        raceJsonCount,
        kbRate,
        hasResults,
        hasPredictions,
        predictionsAt,
      };
    });

    return NextResponse.json({ dates: result });
  } catch (error) {
    console.error('[DataStatus] Error:', error);
    return NextResponse.json({ dates: [], error: String(error) }, { status: 500 });
  }
}
