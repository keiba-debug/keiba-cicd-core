#!/usr/bin/env node
/**
 * ナビゲーションインデックス生成スクリプト
 * 
 * レースページの前後ナビゲーション用インデックスを事前生成し、
 * ファイルシステムアクセスを削減してパフォーマンスを向上させる。
 * 
 * Usage:
 *   node scripts/generate-navigation-index.mjs --date 2026-01-31
 *   node scripts/generate-navigation-index.mjs --start 2026-01-25 --end 2026-01-31
 */

import fs from 'fs';
import path from 'path';

// 環境変数からデータルートを取得
const DATA_ROOT = process.env.DATA_ROOT|| 'Z:/KEIBA-CICD/data2';
const RACES_PATH = path.join(DATA_ROOT, 'races');

// 競馬場の順序
const TRACKS = ['札幌', '函館', '新潟', '福島', '東京', '中山', '中京', '京都', '阪神', '小倉'];

/**
 * kaisai_keyから競馬場名を抽出
 */
function extractTrackFromKaisaiKey(kaisaiKey) {
  for (const track of TRACKS) {
    if (kaisaiKey.includes(track)) {
      return track;
    }
  }
  return null;
}

/**
 * 指定日のナビゲーションインデックスを生成
 */
function generateNavigationIndex(date) {
  const [year, month, day] = date.split('-');
  const dayPath = path.join(RACES_PATH, year, month, day);

  if (!fs.existsSync(dayPath)) {
    console.log(`  [SKIP] ディレクトリが存在しません: ${dayPath}`);
    return null;
  }

  // race_info.json または nittei_*.json を読み込み
  let kaisaiData = null;

  // race_info.json を試す
  const raceInfoPath = path.join(dayPath, 'race_info.json');
  if (fs.existsSync(raceInfoPath)) {
    try {
      const content = fs.readFileSync(raceInfoPath, 'utf-8');
      const data = JSON.parse(content);
      kaisaiData = data.kaisai_data;
    } catch (e) {
      console.log(`  [WARN] race_info.json パースエラー: ${e}`);
    }
  }

  // nittei_*.json を試す
  if (!kaisaiData) {
    const tempPath = path.join(dayPath, 'temp');
    if (fs.existsSync(tempPath)) {
      const dateStr = date.replace(/-/g, '');
      const nitteiPath = path.join(tempPath, `nittei_${dateStr}.json`);
      if (fs.existsSync(nitteiPath)) {
        try {
          const content = fs.readFileSync(nitteiPath, 'utf-8');
          const data = JSON.parse(content);
          kaisaiData = data.kaisai_data;
        } catch (e) {
          console.log(`  [WARN] nittei_*.json パースエラー: ${e}`);
        }
      }
    }
  }

  if (!kaisaiData) {
    console.log(`  [SKIP] kaisai_data が見つかりません: ${date}`);
    return null;
  }

  // 全レースを収集
  const allRaces = [];
  const trackMap = new Map();

  for (const [kaisaiKey, races] of Object.entries(kaisaiData)) {
    const trackName = extractTrackFromKaisaiKey(kaisaiKey);
    if (!trackName) continue;

    for (const race of races) {
      const raceNumber = parseInt(race.race_no.replace('R', ''), 10);
      const startTime = race.start_time || '99:99';

      allRaces.push({
        track: trackName,
        raceNumber,
        raceId: race.race_id,
        startTime,
        raceName: race.race_name || `${raceNumber}R`,
      });

      // トラック別データを蓄積
      if (!trackMap.has(trackName)) {
        trackMap.set(trackName, { raceByNumber: {}, firstRaceId: race.race_id });
      }
      const trackData = trackMap.get(trackName);
      trackData.raceByNumber[raceNumber] = race.race_id;
      if (raceNumber === 1) {
        trackData.firstRaceId = race.race_id;
      }
    }
  }

  // tracks配列を構築（TRACKS順にソート）
  const tracks = [];
  for (const [trackName, data] of trackMap.entries()) {
    tracks.push({
      name: trackName,
      firstRaceId: data.firstRaceId,
      raceByNumber: data.raceByNumber,
    });
  }
  tracks.sort((a, b) => {
    const indexA = TRACKS.indexOf(a.name);
    const indexB = TRACKS.indexOf(b.name);
    return indexA - indexB;
  });

  // 時刻順にソート
  const timeToMinutes = (time) => {
    if (!time || time === '99:99') return 9999;
    const [hours, minutes] = time.split(':').map(Number);
    return hours * 60 + minutes;
  };

  allRaces.sort((a, b) => {
    const timeA = timeToMinutes(a.startTime);
    const timeB = timeToMinutes(b.startTime);
    if (timeA !== timeB) return timeA - timeB;
    return a.raceNumber - b.raceNumber;
  });

  return {
    date,
    generatedAt: new Date().toISOString(),
    tracks,
    allRacesByTime: allRaces,
  };
}

/**
 * インデックスをファイルに保存
 */
function saveNavigationIndex(date, index) {
  const [year, month, day] = date.split('-');
  const tempPath = path.join(RACES_PATH, year, month, day, 'temp');

  if (!fs.existsSync(tempPath)) {
    fs.mkdirSync(tempPath, { recursive: true });
  }

  const outputPath = path.join(tempPath, 'navigation_index.json');
  try {
    fs.writeFileSync(outputPath, JSON.stringify(index, null, 2), 'utf-8');
    console.log(`  [OK] ${outputPath}`);
    return true;
  } catch (e) {
    console.error(`  [ERROR] 保存失敗: ${e}`);
    return false;
  }
}

/**
 * 日付範囲を生成
 */
function getDateRange(start, end) {
  const dates = [];
  const startDate = new Date(start);
  const endDate = new Date(end);

  const current = new Date(startDate);
  while (current <= endDate) {
    dates.push(current.toISOString().split('T')[0]);
    current.setDate(current.getDate() + 1);
  }

  return dates;
}

// メイン処理
function main() {
  const args = process.argv.slice(2);
  let dates = [];

  // 引数パース
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--date' && args[i + 1]) {
      dates = [args[i + 1]];
      break;
    }
    if (args[i] === '--start' && args[i + 1] && args[i + 2] === '--end' && args[i + 3]) {
      dates = getDateRange(args[i + 1], args[i + 3]);
      break;
    }
  }

  if (dates.length === 0) {
    console.error('Usage:');
    console.error('  node scripts/generate-navigation-index.mjs --date 2026-01-31');
    console.error('  node scripts/generate-navigation-index.mjs --start 2026-01-25 --end 2026-01-31');
    process.exit(1);
  }

  console.log(`=== ナビゲーションインデックス生成 ===`);
  console.log(`DATA_ROOT: ${DATA_ROOT}`);
  console.log(`対象日数: ${dates.length}`);
  console.log('');

  let successCount = 0;
  for (const date of dates) {
    console.log(`[${date}]`);
    const index = generateNavigationIndex(date);
    if (index) {
      if (saveNavigationIndex(date, index)) {
        successCount++;
      }
    }
  }

  console.log('');
  console.log(`=== 完了: ${successCount}/${dates.length} 日 ===`);
}

main();
