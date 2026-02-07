/**
 * 日別詳細API
 * 
 * GET /api/bankroll/daily/20260125
 * 
 * TARGET購入データとintegrated_*.jsonのレース情報を結合して返す
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// レース情報の型
interface RaceInfo {
  race_id: string;  // integrated形式のレースID
  post_time: string;
  race_name: string;
  distance: number;
  track: string;
  grade: string;
}

// race_info.jsonの構造
interface RaceInfoEntry {
  race_no: string;
  race_name: string;
  course: string;
  race_id: string;
}

interface RaceInfoJson {
  date: string;
  kaisai_data: Record<string, RaceInfoEntry[]>;
}

// 場所名からJV形式の場コードに変換
const VENUE_TO_JV_CODE: Record<string, string> = {
  '札幌': '01',
  '函館': '02',
  '福島': '03',
  '新潟': '04',
  '東京': '05',
  '中山': '06',
  '中京': '07',
  '京都': '08',
  '阪神': '09',
  '小倉': '10',
};

/**
 * race_info.jsonとintegrated_*.jsonからレース情報を取得
 */
async function loadRaceInfoMap(dateStr: string): Promise<Map<string, RaceInfo>> {
  const raceInfoMap = new Map<string, RaceInfo>();
  const dataRoot = process.env.KEIBA_DATA_ROOT_DIR;
  if (!dataRoot) {
    throw new Error('KEIBA_DATA_ROOT_DIR が設定されていません');
  }
  const year = dateStr.slice(0, 4);
  const month = dateStr.slice(4, 6);
  const day = dateStr.slice(6, 8);
  
  // race_info.jsonを読み込む
  const raceInfoPath = path.join(dataRoot, 'races', year, month, day, 'race_info.json');
  
  try {
    const raceInfoContent = await fs.readFile(raceInfoPath, 'utf-8');
    const raceInfoJson: RaceInfoJson = JSON.parse(raceInfoContent);
    
    // 各開催のレースを処理
    for (const [kaisaiName, races] of Object.entries(raceInfoJson.kaisai_data)) {
      // 開催名から場所を抽出（例: "1回東京1日目" → "東京"）
      const venueMatch = kaisaiName.match(/(\d+)回(.+?)(\d+)日目/);
      if (!venueMatch) continue;
      
      const venue = venueMatch[2];
      
      for (const race of races) {
        const raceNum = parseInt(race.race_no.replace('R', ''));
        const integratedRaceId = race.race_id;
        
        // キー: "場所-レース番号"
        const key = `${venue}-${raceNum}`;
        
        // integrated_*.jsonから詳細を取得
        const integratedPath = path.join(
          dataRoot,
          'races',
          year,
          month,
          day,
          'temp',
          `integrated_${integratedRaceId}.json`
        );
        
        let postTime = '';
        let raceName = race.race_name || '';
        let distance = 0;
        let track = '';
        let grade = '';
        
        try {
          const integratedContent = await fs.readFile(integratedPath, 'utf-8');
          const integratedData = JSON.parse(integratedContent);
          
          if (integratedData.race_info) {
            postTime = integratedData.race_info.post_time || '';
            raceName = integratedData.race_info.race_name || 
                       integratedData.race_info.race_condition || 
                       race.race_name || '';
            distance = integratedData.race_info.distance || 0;
            track = integratedData.race_info.track || '';
            grade = integratedData.race_info.grade || '';
          }
        } catch {
          // integrated_*.jsonがない場合はrace_info.jsonの情報を使用
          const courseMatch = race.course?.match(/([芝ダ])[\・・](\d+)m/);
          if (courseMatch) {
            track = courseMatch[1] === '芝' ? '芝' : 'ダ';
            distance = parseInt(courseMatch[2]);
          }
        }
        
        raceInfoMap.set(key, {
          race_id: integratedRaceId,
          post_time: postTime,
          race_name: raceName,
          distance,
          track,
          grade,
        });
      }
    }
  } catch (error) {
    console.error('[loadRaceInfoMap] Error:', error);
  }
  
  return raceInfoMap;
}

/**
 * Pythonスクリプトを実行してJSONを取得
 */
function executePythonScript(
  scriptPath: string,
  args: string[],
  cwd?: string
): Promise<any> {
  return new Promise((resolve, reject) => {
    const pythonPath = process.env.PYTHON_PATH || 'python';
    const scriptFullPath = path.resolve(scriptPath);
    const workingDir = cwd || process.cwd();

    const child = spawn(pythonPath, [scriptFullPath, ...args], {
      cwd: workingDir,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdout = '';
    let stderr = '';

    child.stdout?.on('data', (data: Buffer) => {
      stdout += data.toString('utf-8');
    });

    child.stderr?.on('data', (data: Buffer) => {
      stderr += data.toString('utf-8');
    });

    child.on('close', (code: number | null) => {
      if (code !== 0) {
        reject(new Error(`プロセス終了コード: ${code}\n${stderr}`));
        return;
      }

      try {
        const jsonStr = stdout.trim();
        if (!jsonStr) {
          reject(new Error('スクリプトからの出力がありません'));
          return;
        }

        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
          reject(new Error('JSON出力が見つかりません'));
          return;
        }

        const result = JSON.parse(jsonMatch[0]);
        resolve(result);
      } catch (error) {
        reject(new Error(`JSON解析エラー: ${error}\n出力: ${stdout}`));
      }
    });

    child.on('error', (error: Error) => {
      reject(error);
    });
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date: dateStr } = await params;

    if (!dateStr || dateStr.length !== 8) {
      return NextResponse.json(
        { error: '日付形式が不正です。YYYYMMDD形式で指定してください。' },
        { status: 400 }
      );
    }

    const scriptPath = path.join(
      process.cwd(),
      '..',
      'KeibaCICD.AI',
      'tools',
      'target_reader.py'
    );

    // TARGETデータを取得
    const result = await executePythonScript(scriptPath, ['--date', dateStr]);

    // レース情報マップを読み込み（race_info.json + integrated_*.json）
    const raceInfoMap = await loadRaceInfoMap(dateStr);

    // レース情報を結合
    if (result.races && Array.isArray(result.races)) {
      for (const race of result.races) {
        // キー: "場所-レース番号" でマッチング
        const key = `${race.venue}-${race.race_number}`;
        const raceInfo = raceInfoMap.get(key);
        
        if (raceInfo) {
          race.post_time = raceInfo.post_time;
          race.race_name = raceInfo.race_name;
          race.distance = raceInfo.distance > 0 
            ? `${raceInfo.track}${raceInfo.distance}m` 
            : '';
          race.grade = raceInfo.grade;
        }
      }
      
      // 発走時刻順でソート
      result.races.sort((a: any, b: any) => {
        const timeA = a.post_time || '99:99';
        const timeB = b.post_time || '99:99';
        return timeA.localeCompare(timeB);
      });
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('[BankrollDailyAPI] Error:', error);
    return NextResponse.json(
      {
        error: '日別詳細の取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
