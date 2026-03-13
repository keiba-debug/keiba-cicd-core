/**
 * レース検索インデックス リーダー
 *
 * Python バッチで生成された race_search_index.json を読み込み、
 * 各種フィルタで絞り込んだ検索結果を返す。
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '../config';

const INDEX_FILE = path.join(DATA3_ROOT, 'indexes', 'race_search_index.json');

// ── 型定義 ──

export interface RaceSearchEntry {
  raceId: string;
  date: string;
  venue: string;
  raceNumber: number;
  raceName: string;
  grade: string;
  track: string;
  distance: number;
  trackCondition: string;
  entryCount: number;
  winnerName: string;
  winnerTime: string;
  winnerLast3f: number | null;
  weather: string;
  paceType: string;
  rpci: number | null;
  raceTrendV2?: string;
}

export interface RaceSearchFilters {
  query?: string;
  venues?: string[];
  track?: string;
  distanceMin?: number;
  distanceMax?: number;
  years?: number[];
  grades?: string[];
  babas?: string[];
  dateFrom?: string; // YYYY-MM
  dateTo?: string;   // YYYY-MM
}

export interface RaceSearchResult {
  races: RaceSearchEntry[];
  totalCount: number;
  filteredCount: number;
}

// ── インメモリキャッシュ（ファイル更新時に自動再読み込み） ──

let cachedIndex: RaceSearchEntry[] | null = null;
let cachedMtime = 0;

function loadIndex(): RaceSearchEntry[] {
  if (!fs.existsSync(INDEX_FILE)) {
    console.warn('[RaceSearch] Index file not found:', INDEX_FILE);
    return [];
  }

  // ファイルの更新時刻をチェック — 変更があればリロード
  const stat = fs.statSync(INDEX_FILE);
  const mtime = stat.mtimeMs;
  if (cachedIndex && mtime === cachedMtime) {
    return cachedIndex;
  }

  try {
    const raw = fs.readFileSync(INDEX_FILE, 'utf-8');
    const data = JSON.parse(raw);
    cachedIndex = (data.races || []) as RaceSearchEntry[];
    cachedMtime = mtime;
    console.log(`[RaceSearch] Loaded ${cachedIndex.length} races from index`);
    return cachedIndex;
  } catch (error) {
    console.error('[RaceSearch] Failed to load index:', error);
    return [];
  }
}

// ── テキスト正規化（全角→半角） ──

function normalizeSearchText(text: string): string {
  return text
    .replace(/[Ａ-Ｚ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/[ａ-ｚ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/Ｓ/g, 'S')
    .replace(/Ｃ/g, 'C')
    .toLowerCase();
}

// ── 検索関数 ──

export function searchRaces(filters: RaceSearchFilters): RaceSearchResult {
  const allRaces = loadIndex();
  const totalCount = allRaces.length;

  let results = allRaces;

  // レース名部分一致
  if (filters.query?.trim()) {
    const q = normalizeSearchText(filters.query.trim());
    results = results.filter((r) => normalizeSearchText(r.raceName).includes(q));
  }

  // 競馬場
  if (filters.venues?.length) {
    const venueSet = new Set(filters.venues);
    results = results.filter((r) => venueSet.has(r.venue));
  }

  // トラック
  if (filters.track) {
    results = results.filter((r) => r.track === filters.track);
  }

  // 距離範囲
  if (filters.distanceMin) {
    results = results.filter((r) => r.distance >= filters.distanceMin!);
  }
  if (filters.distanceMax) {
    results = results.filter((r) => r.distance <= filters.distanceMax!);
  }

  // 年度
  if (filters.years?.length) {
    const yearSet = new Set(filters.years);
    results = results.filter((r) => yearSet.has(parseInt(r.date.substring(0, 4))));
  }

  // グレード
  if (filters.grades?.length) {
    const gradeSet = new Set(filters.grades);
    results = results.filter((r) => gradeSet.has(r.grade));
  }

  // 馬場状態
  if (filters.babas?.length) {
    const babaSet = new Set(filters.babas);
    results = results.filter((r) => babaSet.has(r.trackCondition));
  }

  // 期間 (YYYY-MM → YYYY-MM-01 / YYYY-MM-31 で前方一致比較)
  if (filters.dateFrom) {
    const from = filters.dateFrom + '-01';
    results = results.filter((r) => r.date >= from);
  }
  if (filters.dateTo) {
    const to = filters.dateTo + '-31';
    results = results.filter((r) => r.date <= to);
  }

  // 日付降順（インデックスが既にソート済みだが念のため）
  results.sort((a, b) => b.date.localeCompare(a.date) || b.raceNumber - a.raceNumber);

  const filteredCount = results.length;
  const limited = results.slice(0, 100);

  return {
    races: limited,
    totalCount,
    filteredCount,
  };
}
