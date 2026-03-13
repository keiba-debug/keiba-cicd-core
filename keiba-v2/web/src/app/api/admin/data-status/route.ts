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
  kbRate: number;           // kb_ext ファイル存在割合 (0-100)
  hasResults: boolean;      // finish_position が1件以上ある
  hasPredictions: boolean;  // predictions.json が存在
  predictionsAt?: string;   // predictions.json の created_at
  jrdbRate: number;         // JRDB登録済みレース割合 (0-100)
  babaStatus: 'ok' | 'partial' | 'none' | null; // 馬場データ（含水率/クッション値）状況
}

/**
 * 馬場CSVをパースしてbaba keyのSetを返す
 * CSV形式: "日本語説明","RX{JJ}{YY}{K}{N}{RR}","{prefix}{value}"
 * RXキーのみASCIIなので latin1 で読んで解析
 */
function parseBabaCSV(filePath: string): Set<string> {
  const keys = new Set<string>();
  if (!fs.existsSync(filePath)) return keys;
  try {
    const content = fs.readFileSync(filePath, 'latin1');
    for (const line of content.split('\n')) {
      const parts = line.split('","');
      if (parts.length < 3) continue;
      const csvId = parts[1].replace(/"/g, '').trim(); // e.g. RX06261101
      if (csvId.length < 10 || !csvId.startsWith('RX')) continue;
      const place = csvId.substring(2, 4);
      const year = `20${csvId.substring(4, 6)}`;
      const kai = String(parseInt(csvId.substring(6, 7), 10));
      const nichi = String(parseInt(csvId.substring(7, 8), 10));
      const raceNum = csvId.substring(8, 10);
      keys.add(`${year}_${place}_${kai}_${nichi}_${raceNum}`);
    }
  } catch { /* ignore */ }
  return keys;
}

/** race_id (16桁) → baba lookup key */
function raceToBabaKey(raceId: string): string {
  const year = raceId.substring(0, 4);
  const place = raceId.substring(8, 10);
  const kai = String(parseInt(raceId.substring(10, 12), 10));
  const nichi = String(parseInt(raceId.substring(12, 14), 10));
  const raceNum = raceId.substring(14, 16);
  return `${year}_${place}_${kai}_${nichi}_${raceNum}`;
}

/** 指定年の馬場データキーセットをロード（cushion + moisture） */
function loadBabaKeys(years: number[]): Set<string> {
  const babaDir = path.join(DATA3_ROOT, 'analysis', 'baba');
  const allKeys = new Set<string>();
  for (const year of years) {
    for (const name of [`cushion${year}.csv`, `moistureG_${year}.csv`]) {
      for (const k of parseBabaCSV(path.join(babaDir, name))) {
        allKeys.add(k);
      }
    }
  }
  return allKeys;
}

/** keibabook/YYYY/MM/DD/ の kb_ext ファイル数を返す */
function countKbExt(dateStr: string): number {
  const [year, month, day] = dateStr.split('-');
  const kbDir = path.join(DATA3_ROOT, 'keibabook', year, month, day);
  if (!fs.existsSync(kbDir)) return 0;
  return fs.readdirSync(kbDir).filter((f) => /^kb_ext_\d{16}\.json$/.test(f)).length;
}

function parseRacesDir(
  dateStr: string,
  babaKeys: Set<string>,
): {
  raceJsonCount: number;
  hasResults: boolean;
  hasPredictions: boolean;
  predictionsAt?: string;
  jrdbRate: number;
  babaStatus: 'ok' | 'partial' | 'none' | null;
} {
  const [year, month, day] = dateStr.split('-');
  const raceDir = path.join(DATA3_ROOT, 'races', year, month, day);

  if (!fs.existsSync(raceDir)) {
    return { raceJsonCount: 0, hasResults: false, hasPredictions: false, jrdbRate: 0, babaStatus: null };
  }

  let raceJsonCount = 0;
  let hasResults = false;
  let hasPredictions = false;
  let predictionsAt: string | undefined;
  let jrdbCount = 0;    // JRDB設定済みレース数
  let babaCount = 0;    // baba設定済みレース数

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
    const raceId = file.replace('race_', '').replace('.json', '');

    // baba: CSVキーの存在確認
    if (babaKeys.size > 0 && babaKeys.has(raceToBabaKey(raceId))) {
      babaCount++;
    }

    // race JSON を読む（成績 + JRDB判定）
    try {
      const raw = fs.readFileSync(path.join(raceDir, file), 'utf-8');
      const data = JSON.parse(raw);
      const entries: Array<{
        finish_position?: number | null;
        jrdb_pre_idm?: number | null;
      }> = data?.entries || [];

      if (!hasResults && entries.some((e) => typeof e.finish_position === 'number' && e.finish_position > 0)) {
        hasResults = true;
      }
      if (entries.some((e) => typeof e.jrdb_pre_idm === 'number' && e.jrdb_pre_idm > 0)) {
        jrdbCount++;
      }
    } catch { /* ignore */ }
  }

  const jrdbRate = raceJsonCount > 0 ? Math.round((jrdbCount / raceJsonCount) * 100) : 0;
  let babaStatus: 'ok' | 'partial' | 'none' | null = null;
  if (raceJsonCount > 0) {
    if (babaCount === raceJsonCount) babaStatus = 'ok';
    else if (babaCount > 0) babaStatus = 'partial';
    else babaStatus = 'none';
  }

  return { raceJsonCount, hasResults, hasPredictions, predictionsAt, jrdbRate, babaStatus };
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

    // 対象年の馬場データをまとめてロード（日付ループの外で1回だけ）
    const years = [...new Set(targetDates.map((d) => parseInt(d.substring(0, 4), 10)))];
    const babaKeys = loadBabaKeys(years);

    const result: DateDataStatus[] = targetDates.map((date) => {
      const entry = indexData[date];
      const indexCount = entry.tracks.reduce((sum, t) => sum + t.races.length, 0);

      const { raceJsonCount, hasResults, hasPredictions, predictionsAt, jrdbRate, babaStatus } =
        parseRacesDir(date, babaKeys);

      const kbCount = countKbExt(date);
      const kbRate = raceJsonCount > 0 ? Math.round((kbCount / raceJsonCount) * 100) : 0;

      return {
        date,
        indexCount,
        raceJsonCount,
        kbRate,
        hasResults,
        hasPredictions,
        predictionsAt,
        jrdbRate,
        babaStatus,
      };
    });

    return NextResponse.json({ dates: result });
  } catch (error) {
    console.error('[DataStatus] Error:', error);
    return NextResponse.json({ dates: [], error: String(error) }, { status: 500 });
  }
}
