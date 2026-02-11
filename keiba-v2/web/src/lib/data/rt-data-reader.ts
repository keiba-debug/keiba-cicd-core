/**
 * RT_DATA（速報・オッズ）読み込みユーティリティ
 *
 * E:\TFJV\RT_DATA のオッズデータを解析
 * JV-Data O1レコード（単複枠オッズ）形式
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';

const JV_DATA_ROOT = process.env.JV_DATA_ROOT_DIR || 'Y:/';
const RT_DATA_PATH = path.join(JV_DATA_ROOT, 'RT_DATA');

import type { HorseOdds, RaceOdds } from './rt-data-types';
export type { HorseOdds, RaceOdds } from './rt-data-types';
export { getTrackNameFromRaceId } from './rt-data-types';

/** 時系列オッズデータ（1時点分） */
export interface OddsSnapshot {
  /** 発表時刻 (MMDDHHmm形式) */
  happyoTime: string;
  /** 発表時刻の表示用 (HH:mm) */
  timeLabel: string;
  /** 各馬のオッズ (馬番 -> 単勝オッズ) */
  odds: Record<string, number>;
}

/** パース結果（発表時刻付き） */
interface ParsedO1 {
  raceId: string;
  happyoTime: string;
  horses: HorseOdds[];
}

function parseO1RecordWithTime(content: string): ParsedO1 | null {
  const raw = content.replace(/\r/g, '').replace(/\n/g, '').trim();
  if (raw.length < 270 || !raw.startsWith('O1')) return null;

  const raceId = raw.substring(11, 27);
  // O1レコード構造:
  // 0-1: RecordSpec (O1)
  // 2: DataKubun
  // 3-10: Date (8)
  // 11-26: id (16)
  // 27-28: TorokuTosu (2)
  // 29-30: SyussoTosu (2)
  // 31-34: HassouTime (4) - 発走時刻 HHmm
  // 35-42: HappyoTime (8) - 発表時刻 MMDDHHmm
  const happyoTime = raw.substring(35, 43).trim();
  const horses: HorseOdds[] = [];

  for (let i = 0; i < 28; i++) {
    const start = 43 + 8 * i;
    const end = start + 8;
    if (end > raw.length) break;

    const block = raw.substring(start, end);
    const umaban = block.substring(0, 2).trim();
    if (!umaban || umaban === '00') continue;

    const oddsRaw = parseInt(block.substring(2, 6).trim() || '0', 10);
    const ninkiRaw = block.substring(6, 8).trim();
    const winOdds = oddsRaw > 0 ? oddsRaw / 10 : null;
    const ninki = /^\d+$/.test(ninkiRaw) ? parseInt(ninkiRaw, 10) : null;

    horses.push({
      umaban,
      winOdds,
      placeOddsMin: null,
      placeOddsMax: null,
      ninki,
    });
  }

  for (let i = 0; i < 28; i++) {
    const start = 267 + 12 * i;
    const end = start + 12;
    if (end > raw.length) break;

    const block = raw.substring(start, end);
    const umaban = block.substring(0, 2).trim();
    const horse = horses.find((h) => h.umaban === umaban);
    if (!horse) continue;

    const lowRaw = parseInt(block.substring(2, 6).trim() || '0', 10);
    const highRaw = parseInt(block.substring(6, 10).trim() || '0', 10);
    horse.placeOddsMin = lowRaw > 0 ? lowRaw / 10 : null;
    horse.placeOddsMax = highRaw > 0 ? highRaw / 10 : null;
  }

  if (horses.length === 0) return null;

  return { raceId, happyoTime, horses };
}

function parseO1Record(content: string): RaceOdds | null {
  const parsed = parseO1RecordWithTime(content);
  if (!parsed) return null;
  return {
    raceId: parsed.raceId,
    source: 'RT_DATA',
    horses: parsed.horses,
  };
}

function findRtFileForRace(raceId: string): string | null {
  if (raceId.length !== 16) return null;

  const year = raceId.substring(0, 4);
  const mmdd = raceId.substring(4, 8);
  const prefix = `RT${raceId}`;

  const candidates = [
    path.join(RT_DATA_PATH, year, mmdd),
    path.join(RT_DATA_PATH, year),
  ];

  for (const base of candidates) {
    if (!fs.existsSync(base)) continue;
    for (const suffix of ['1', '01']) {
      const fpath = path.join(base, `${prefix}${suffix}.DAT`);
      if (fs.existsSync(fpath)) return fpath;
    }
    const files = fs.readdirSync(base).filter((f) => f.startsWith(prefix) && f.endsWith('.DAT'));
    if (files.length > 0) return path.join(base, files[0]);
  }

  return null;
}

export function getRaceOddsFromRt(raceId: string): RaceOdds | null {
  if (!fs.existsSync(RT_DATA_PATH)) return null;

  const filePath = findRtFileForRace(raceId);
  if (!filePath) return null;

  try {
    const buffer = fs.readFileSync(filePath);
    const content = iconv.decode(buffer, 'Shift_JIS');
    return parseO1Record(content);
  } catch {
    return null;
  }
}

export function listRacesWithOdds(dateYyyymmdd: string): string[] {
  if (dateYyyymmdd.length !== 8 || !fs.existsSync(RT_DATA_PATH)) return [];

  const year = dateYyyymmdd.substring(0, 4);
  const mmdd = dateYyyymmdd.substring(4, 8);
  const prefix = `RT${dateYyyymmdd}`;

  const bases = [
    path.join(RT_DATA_PATH, year, mmdd),
    path.join(RT_DATA_PATH, year),
  ];

  const seen = new Set<string>();

  for (const base of bases) {
    if (!fs.existsSync(base)) continue;
    try {
      const files = fs.readdirSync(base).filter((f) => f.startsWith(prefix) && f.endsWith('.DAT'));
      for (const f of files) {
        const raceId = f.substring(2, 18);
        if (raceId.length === 16) seen.add(raceId);
      }
    } catch {
      // ignore
    }
  }

  return Array.from(seen).sort();
}

export function isRtDataAvailable(): boolean {
  return fs.existsSync(RT_DATA_PATH);
}

// ============================================================
// JI_2026 時系列オッズ（馬単/馬連）
// ============================================================

const JI_DATA_PATH = path.join(JV_DATA_ROOT, 'RT_DATA');

/**
 * JI_2026 の JT ファイル（馬単時系列）を探す
 */
function findJiTimeSeriesFile(raceId: string): string | null {
  if (raceId.length !== 16) return null;

  const year = raceId.substring(0, 4);
  const mmdd = raceId.substring(4, 8);
  const fileName = `JT${raceId}.DAT`;

  const jiPath = path.join(JI_DATA_PATH, `JI_${year}`, mmdd, fileName);
  if (fs.existsSync(jiPath)) return jiPath;

  return null;
}

/**
 * JI 時系列ファイルの1行をパース
 * 位置31-34: タイムスタンプ (HHmm)
 * 位置43-: 単勝オッズデータ（O1と同じフォーマット）
 */
function parseJiTimeSeriesLine(line: string): { time: string; odds: Record<string, number> } | null {
  const raw = line.replace(/\r/g, '').trim();
  if (raw.length < 270 || !raw.startsWith('O1')) return null;

  // 位置31-34: タイムスタンプ (HHmm)
  const time = raw.substring(31, 35);
  if (!/^\d{4}$/.test(time)) return null;

  const odds: Record<string, number> = {};

  // O1レコードの単勝オッズ部分を読み取る（位置43から）
  for (let i = 0; i < 28; i++) {
    const start = 43 + 8 * i;
    const end = start + 8;
    if (end > raw.length) break;

    const block = raw.substring(start, end);
    const umaban = block.substring(0, 2).trim();
    if (!umaban || umaban === '00') continue;

    const oddsRaw = parseInt(block.substring(2, 6).trim() || '0', 10);
    if (oddsRaw > 0) {
      odds[umaban] = oddsRaw / 10;
    }
  }

  return { time, odds };
}

/**
 * JI_2026 から時系列オッズを取得
 * 複数行のファイルから時系列を構築
 */
export function getJiOddsTimeSeries(raceId: string): OddsSnapshot[] {
  const filePath = findJiTimeSeriesFile(raceId);
  if (!filePath) return [];

  try {
    const buffer = fs.readFileSync(filePath);
    const content = iconv.decode(buffer, 'Shift_JIS');
    const lines = content.split('\n').filter((l) => l.trim().length > 0);

    const snapshots: OddsSnapshot[] = [];
    const seen = new Set<string>();

    for (const line of lines) {
      const parsed = parseJiTimeSeriesLine(line);
      if (!parsed || seen.has(parsed.time)) continue;
      seen.add(parsed.time);

      const hh = parsed.time.substring(0, 2);
      const mm = parsed.time.substring(2, 4);

      snapshots.push({
        happyoTime: parsed.time,
        timeLabel: `${hh}:${mm}`,
        odds: parsed.odds,
      });
    }

    // ファイル順（時系列順）を維持（ソートしない）
    // JTファイルは時系列順に行が並んでいるため
    return snapshots;
  } catch {
    return [];
  }
}

/**
 * JI時系列から変動情報を計算
 * 最初の有効なオッズ（0でない）と最新オッズを比較
 */
export function calculateJiOddsChanges(raceId: string): import('./rt-data-types').OddsChangeInfo[] {
  const timeSeries = getJiOddsTimeSeries(raceId);
  if (timeSeries.length < 2) return [];

  // 最初の有効なオッズを持つスナップショットを探す
  // 条件: 3頭以上が0.1倍以上のオッズを持つ
  let first: typeof timeSeries[0] | null = null;
  for (const snapshot of timeSeries) {
    const validOdds = Object.values(snapshot.odds).filter((o) => o >= 1.0);
    if (validOdds.length >= 3) {
      first = snapshot;
      break;
    }
  }

  if (!first) return [];

  const last = timeSeries[timeSeries.length - 1];

  const changes: import('./rt-data-types').OddsChangeInfo[] = [];
  const allUmaban = new Set<string>([
    ...Object.keys(first.odds),
    ...Object.keys(last.odds),
  ]);

  for (const umaban of allUmaban) {
    const firstOdds = first.odds[umaban] ?? null;
    const lastOdds = last.odds[umaban] ?? null;

    let change: number | null = null;
    let changePercent: number | null = null;
    let trend: 'up' | 'down' | 'stable' | 'unknown' = 'unknown';

    if (firstOdds != null && lastOdds != null) {
      change = lastOdds - firstOdds;
      changePercent = (change / firstOdds) * 100;

      if (Math.abs(changePercent) < 5) {
        trend = 'stable';
      } else if (change > 0) {
        trend = 'up'; // オッズ上昇 = 人気低下
      } else {
        trend = 'down'; // オッズ下落 = 人気上昇
      }
    }

    changes.push({
      umaban,
      firstOdds,
      lastOdds,
      change,
      changePercent,
      trend,
    });
  }

  return changes.sort((a, b) => {
    const numA = parseInt(a.umaban, 10) || 99;
    const numB = parseInt(b.umaban, 10) || 99;
    return numA - numB;
  });
}

/** 直前変動情報 */
export interface LastMinuteChange {
  umaban: string;
  /** 10分前のオッズ */
  beforeOdds: number | null;
  /** 最終オッズ */
  finalOdds: number | null;
  /** 変動量 */
  change: number | null;
  /** 変動率(%) */
  changePercent: number | null;
  /** 変動レベル: hot=急上昇人気, warm=やや人気化, cold=人気低下, stable=安定 */
  level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown';
}

/**
 * 締め切り直前（約10分前）からの変動を計算
 * 「直前で人気になった馬」を検出
 */
export function calculateLastMinuteChanges(raceId: string): LastMinuteChange[] {
  const timeSeries = getJiOddsTimeSeries(raceId);
  if (timeSeries.length < 5) return [];

  const last = timeSeries[timeSeries.length - 1];
  const lastTimeNum = parseInt(last.happyoTime, 10);

  // 10分前のスナップショットを探す（HHmm形式なので10分 = 10）
  // ただし日をまたぐ場合があるので、インデックスベースでも探す
  let before: typeof timeSeries[0] | null = null;
  
  // 時刻ベースで10分前を探す
  for (let i = timeSeries.length - 2; i >= 0; i--) {
    const snapshot = timeSeries[i];
    const timeNum = parseInt(snapshot.happyoTime, 10);
    const diff = lastTimeNum - timeNum;
    
    // 10分前後（8-12分）のスナップショットを探す
    if (diff >= 8 && diff <= 15) {
      before = snapshot;
      break;
    }
    // 日をまたぐ場合（例: 0005 - 2355 = -2350 → 実際は10分）
    if (diff < -2300 && diff > -2400) {
      const actualDiff = 2400 + diff;
      if (actualDiff >= 8 && actualDiff <= 15) {
        before = snapshot;
        break;
      }
    }
  }

  // 時刻ベースで見つからない場合、インデックスベースで約10件前を使用
  if (!before && timeSeries.length > 10) {
    before = timeSeries[timeSeries.length - 11];
  } else if (!before && timeSeries.length > 3) {
    before = timeSeries[Math.floor(timeSeries.length / 2)];
  }

  if (!before) return [];

  const changes: LastMinuteChange[] = [];
  const allUmaban = new Set<string>([
    ...Object.keys(before.odds),
    ...Object.keys(last.odds),
  ]);

  for (const umaban of allUmaban) {
    const beforeOdds = before.odds[umaban] ?? before.odds[umaban.replace(/^0+/, '')] ?? null;
    const finalOdds = last.odds[umaban] ?? last.odds[umaban.replace(/^0+/, '')] ?? null;

    let change: number | null = null;
    let changePercent: number | null = null;
    let level: LastMinuteChange['level'] = 'unknown';

    if (beforeOdds != null && beforeOdds > 0 && finalOdds != null && finalOdds > 0) {
      change = finalOdds - beforeOdds;
      changePercent = (change / beforeOdds) * 100;

      // 変動レベルを判定
      if (changePercent <= -15) {
        level = 'hot';  // 15%以上下落 = 急激に人気化
      } else if (changePercent <= -5) {
        level = 'warm'; // 5-15%下落 = やや人気化
      } else if (changePercent >= 10) {
        level = 'cold'; // 10%以上上昇 = 人気低下
      } else {
        level = 'stable';
      }
    }

    changes.push({
      umaban,
      beforeOdds,
      finalOdds,
      change,
      changePercent,
      level,
    });
  }

  return changes.sort((a, b) => {
    const numA = parseInt(a.umaban, 10) || 99;
    const numB = parseInt(b.umaban, 10) || 99;
    return numA - numB;
  });
}

/**
 * 時系列スナップショットファイルを全て取得
 */
function findAllRtFilesForRace(raceId: string): string[] {
  if (raceId.length !== 16) return [];

  const year = raceId.substring(0, 4);
  const mmdd = raceId.substring(4, 8);
  const prefix = `RT${raceId}`;

  const candidates = [
    path.join(RT_DATA_PATH, year, mmdd),
    path.join(RT_DATA_PATH, year),
  ];

  for (const base of candidates) {
    if (!fs.existsSync(base)) continue;
    try {
      const files = fs
        .readdirSync(base)
        .filter((f) => f.startsWith(prefix) && f.endsWith('.DAT'))
        .sort((a, b) => a.localeCompare(b)); // 末尾の数字順（1,2,3...）
      if (files.length > 0) {
        return files.map((f) => path.join(base, f));
      }
    } catch {
      continue;
    }
  }
  return [];
}

/**
 * HappyoTime (MMDDHHmm) を HH:mm 形式に変換
 */
function formatHappyoTime(happyoTime: string): string {
  if (happyoTime.length >= 8) {
    const hh = happyoTime.substring(4, 6);
    const mm = happyoTime.substring(6, 8);
    return `${hh}:${mm}`;
  }
  return happyoTime;
}

/**
 * 時系列オッズデータを取得
 * 複数のスナップショットファイルを読み込み、時系列データを返す
 */
export function getOddsTimeSeries(raceId: string): OddsSnapshot[] {
  const files = findAllRtFilesForRace(raceId);
  if (files.length === 0) return [];

  const snapshots: OddsSnapshot[] = [];
  const seen = new Set<string>(); // 重複防止（同じ時刻）

  for (const filePath of files) {
    try {
      const buffer = fs.readFileSync(filePath);
      const content = iconv.decode(buffer, 'Shift_JIS');
      const parsed = parseO1RecordWithTime(content);
      if (!parsed || !parsed.happyoTime) continue;

      // 重複チェック
      if (seen.has(parsed.happyoTime)) continue;
      seen.add(parsed.happyoTime);

      const odds: Record<string, number> = {};
      for (const h of parsed.horses) {
        if (h.winOdds != null) {
          odds[h.umaban] = h.winOdds;
        }
      }

      snapshots.push({
        happyoTime: parsed.happyoTime,
        timeLabel: formatHappyoTime(parsed.happyoTime),
        odds,
      });
    } catch {
      continue;
    }
  }

  // 時刻順にソート
  return snapshots.sort((a, b) => a.happyoTime.localeCompare(b.happyoTime));
}

/** 時系列オッズの変動情報 */
export interface OddsChange {
  umaban: string;
  firstOdds: number | null;
  lastOdds: number | null;
  change: number | null; // lastOdds - firstOdds
  changePercent: number | null; // ((lastOdds - firstOdds) / firstOdds) * 100
  trend: 'up' | 'down' | 'stable' | 'unknown';
}

/**
 * 朝一オッズと最新オッズを比較して変動を計算
 */
export function calculateOddsChanges(raceId: string): OddsChange[] {
  const timeSeries = getOddsTimeSeries(raceId);
  if (timeSeries.length < 2) return [];

  const first = timeSeries[0];
  const last = timeSeries[timeSeries.length - 1];

  const changes: OddsChange[] = [];
  const allUmaban = new Set<string>([
    ...Object.keys(first.odds),
    ...Object.keys(last.odds),
  ]);

  for (const umaban of allUmaban) {
    const firstOdds = first.odds[umaban] ?? null;
    const lastOdds = last.odds[umaban] ?? null;

    let change: number | null = null;
    let changePercent: number | null = null;
    let trend: 'up' | 'down' | 'stable' | 'unknown' = 'unknown';

    if (firstOdds != null && lastOdds != null) {
      change = lastOdds - firstOdds;
      changePercent = (change / firstOdds) * 100;

      if (Math.abs(change) < 0.5) {
        trend = 'stable';
      } else if (change > 0) {
        trend = 'up'; // オッズ上昇 = 人気低下
      } else {
        trend = 'down'; // オッズ下落 = 人気上昇
      }
    }

    changes.push({
      umaban,
      firstOdds,
      lastOdds,
      change,
      changePercent,
      trend,
    });
  }

  return changes.sort((a, b) => {
    const numA = parseInt(a.umaban, 10) || 99;
    const numB = parseInt(b.umaban, 10) || 99;
    return numA - numB;
  });
}
