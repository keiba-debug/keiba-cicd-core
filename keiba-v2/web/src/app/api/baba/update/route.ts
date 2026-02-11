/**
 * 馬場状態（クッション値・含水率）更新API
 * POST /api/baba/update
 * 
 * リクエストボディ:
 * {
 *   date: string;        // 日付（YYYY-MM-DD）
 *   track: string;       // 競馬場名（東京、京都、小倉など）
 *   kai: number;         // 回次
 *   nichi: number;       // 日次
 *   cushion?: number;    // クッション値（芝のみ）
 *   moistureGTurf?: number;  // 含水率ゴール前（芝）
 *   moistureGDirt?: number;  // 含水率ゴール前（ダート）
 *   moisture4Turf?: number;  // 含水率4コーナー（芝）
 *   moisture4Dirt?: number;  // 含水率4コーナー（ダート）
 * }
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

// 競馬場名 → 場コード
const TRACK_TO_VENUE: Record<string, string> = {
  '札幌': '01', '函館': '02', '福島': '03', '新潟': '04', '東京': '05',
  '中山': '06', '中京': '07', '京都': '08', '阪神': '09', '小倉': '10',
};

// BABAデータディレクトリ（DATA_ROOT/baba）
function getBabaDir(): string {
  const dataRoot = process.env.DATA_ROOT || 'C:/KEIBA-CICD/data2';
  return path.join(dataRoot, 'baba');
}

interface BabaUpdateRequest {
  date: string;
  track: string;
  kai: number;
  nichi: number;
  cushion?: number;
  moistureGTurf?: number;
  moistureGDirt?: number;
  moisture4Turf?: number;
  moisture4Dirt?: number;
}

/**
 * レースIDとRX_IDのベース部分を構築（レース番号なし）
 */
function buildRxIdBase(year: number, venueCode: string, kai: number, nichi: number): string {
  const year2 = String(year).substring(2, 4);
  return `RX${venueCode}${year2}${kai}${nichi}`;
}

/**
 * CSVファイルを更新
 * 既存の行を更新するか、新規行を追加する
 */
function updateCsvFile(
  filePath: string,
  rxIdBase: string,
  surfaceCode: string,
  value: number,
  displayLabel: string
): { updated: number; added: number } {
  let updated = 0;
  let added = 0;

  // ファイルが存在しない場合は作成
  if (!fs.existsSync(filePath)) {
    // 親ディレクトリを作成
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(filePath, '', 'utf-8');
  }

  // 既存のファイルを読み込み
  let content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split(/\r?\n/);
  const newLines: string[] = [];
  const processedRxIds = new Set<string>();

  // レース番号01〜12のRX_IDを対象
  const targetRxIds = new Set<string>();
  for (let r = 1; r <= 12; r++) {
    const raceNo = String(r).padStart(2, '0');
    targetRxIds.add(`${rxIdBase}${raceNo}`);
  }

  // 既存行を処理
  for (const line of lines) {
    if (!line.trim()) continue;

    const parts = line.split(',').map(p => p.replace(/^"|"$/g, '').trim());
    if (parts.length < 2) {
      newLines.push(line);
      continue;
    }

    const rxId = parts[1];
    const existingValueStr = parts[2] || '';
    
    // 対象RX_IDかつ同じ芝/ダ種別の行を更新
    if (targetRxIds.has(rxId)) {
      const existingSurfaceCode = existingValueStr.substring(0, 2);
      if (existingSurfaceCode === surfaceCode || existingValueStr === '') {
        // 値を更新
        const valueStr = formatValue(surfaceCode, value);
        const newLine = `"${parts[0]}","${rxId}","${valueStr}"`;
        newLines.push(newLine);
        processedRxIds.add(rxId);
        updated++;
      } else {
        // 異なる芝/ダ種別の行はそのまま保持
        newLines.push(line);
      }
    } else {
      newLines.push(line);
    }
  }

  // 追加が必要な行を追加
  for (let r = 1; r <= 12; r++) {
    const raceNo = String(r).padStart(2, '0');
    const rxId = `${rxIdBase}${raceNo}`;
    if (!processedRxIds.has(rxId)) {
      // 新規行を追加
      const valueStr = formatValue(surfaceCode, value);
      const label = `${displayLabel}${String(r).padStart(2, '0')}R`;
      newLines.push(`"${label}","${rxId}","${valueStr}"`);
      added++;
    }
  }

  // ファイルに書き込み
  fs.writeFileSync(filePath, newLines.join('\n') + '\n', 'utf-8');

  return { updated, added };
}

/**
 * 値をフォーマット（"00 9.6" や "0D 1.2" の形式）
 */
function formatValue(surfaceCode: string, value: number): string {
  // 整数部と小数部に分けてフォーマット
  const formatted = value.toFixed(1);
  return `${surfaceCode}${formatted.padStart(4, ' ')}`;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json() as BabaUpdateRequest;
    const { date, track, kai, nichi, cushion, moistureGTurf, moistureGDirt, moisture4Turf, moisture4Dirt } = body;

    // バリデーション
    if (!date || !track || kai == null || nichi == null) {
      return NextResponse.json(
        { ok: false, error: 'date, track, kai, nichi は必須です' },
        { status: 400 }
      );
    }

    const venueCode = TRACK_TO_VENUE[track];
    if (!venueCode) {
      return NextResponse.json(
        { ok: false, error: `不明な競馬場: ${track}` },
        { status: 400 }
      );
    }

    const [yearStr] = date.split('-');
    const year = parseInt(yearStr, 10);
    if (Number.isNaN(year)) {
      return NextResponse.json(
        { ok: false, error: '不正な日付形式' },
        { status: 400 }
      );
    }

    const babaDir = getBabaDir();
    const rxIdBase = buildRxIdBase(year, venueCode, kai, nichi);
    const displayLabel = `${year}年${kai}回${track}${nichi}日目`;

    const results: Record<string, { updated: number; added: number }> = {};

    // クッション値の更新（芝のみ）
    if (cushion != null) {
      const cushionFile = path.join(babaDir, `cushion${year}.csv`);
      results.cushion = updateCsvFile(cushionFile, rxIdBase, '00', cushion, displayLabel);
    }

    // 含水率（ゴール前）の更新
    const moistureGFile = path.join(babaDir, `moistureG_${year}.csv`);
    if (moistureGTurf != null) {
      results.moistureGTurf = updateCsvFile(moistureGFile, rxIdBase, '00', moistureGTurf, displayLabel);
    }
    if (moistureGDirt != null) {
      results.moistureGDirt = updateCsvFile(moistureGFile, rxIdBase, '0D', moistureGDirt, displayLabel);
    }

    // 含水率（4コーナー）の更新
    const moisture4File = path.join(babaDir, `moisture4_${year}.csv`);
    if (moisture4Turf != null) {
      results.moisture4Turf = updateCsvFile(moisture4File, rxIdBase, '00', moisture4Turf, displayLabel);
    }
    if (moisture4Dirt != null) {
      results.moisture4Dirt = updateCsvFile(moisture4File, rxIdBase, '0D', moisture4Dirt, displayLabel);
    }

    return NextResponse.json({
      ok: true,
      message: '馬場状態を更新しました',
      rxIdBase,
      results,
    });

  } catch (err) {
    console.error('BABA update error:', err);
    return NextResponse.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      },
      { status: 500 }
    );
  }
}
