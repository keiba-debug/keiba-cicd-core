/**
 * vega-niigata1000 Phase 1+2 検証データ読み込み (Server-side)
 *
 * docs/ml-experiments/v8.x_vega_niigata1000_phase1_data/*.csv を読み、
 * 共通スキーマ {n, wins, top3, win_rate, top3_rate, win_roi, *_lo, *_hi} を
 * 持つ row 配列に変換する。
 */

import fs from 'fs';
import path from 'path';

const PHASE1_DATA_DIR = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'ml-experiments',
  'v8.x_vega_niigata1000_phase1_data',
);

const PHASE3_METRICS_PATH = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'ml-experiments',
  'v8.x_vega_niigata1000_phase3_backtest_metrics.json',
);

/** CSV を簡易パース (header + 数値行)。BOM 除去込み。 */
function parseCsv(content: string): Record<string, string>[] {
  const lines = content
    .replace(/^﻿/, '')
    .split(/\r?\n/)
    .filter((l) => l.trim().length > 0);
  if (lines.length === 0) return [];
  const headers = lines[0].split(',');
  return lines.slice(1).map((line) => {
    const cells = line.split(',');
    const row: Record<string, string> = {};
    headers.forEach((h, i) => {
      row[h] = cells[i] ?? '';
    });
    return row;
  });
}

function readCsv(filename: string): Record<string, string>[] {
  const p = path.join(PHASE1_DATA_DIR, filename);
  if (!fs.existsSync(p)) return [];
  const content = fs.readFileSync(p, 'utf-8');
  return parseCsv(content);
}

function num(s: string | undefined): number {
  if (s === undefined || s === '') return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

// =====================================================
// 各 CSV の型 + ローダー
// =====================================================

export interface FrameStat {
  wakuban: number;
  n: number;
  wins: number;
  top3: number;
  winRate: number;
  top3Rate: number;
  winRoi: number;
  top3RateLo: number;
  top3RateHi: number;
}

export function loadFrameOverall(): FrameStat[] {
  return readCsv('01_frame_overall.csv').map((r) => ({
    wakuban: num(r.wakuban),
    n: num(r.n),
    wins: num(r.wins),
    top3: num(r.top3),
    winRate: num(r.win_rate),
    top3Rate: num(r.top3_rate),
    winRoi: num(r.win_roi),
    top3RateLo: num(r.top3_rate_lo),
    top3RateHi: num(r.top3_rate_hi),
  }));
}

export interface FrameStyleStat {
  frameGrp: string;
  runningStyle: string;
  n: number;
  wins: number;
  top3: number;
  winRate: number;
  top3Rate: number;
  winRoi: number;
}

export function loadFrameXStyle(): FrameStyleStat[] {
  return readCsv('02_frame_x_style.csv').map((r) => ({
    frameGrp: r.frame_grp ?? '',
    runningStyle: r.running_style ?? '',
    n: num(r.n),
    wins: num(r.wins),
    top3: num(r.top3),
    winRate: num(r.win_rate),
    top3Rate: num(r.top3_rate),
    winRoi: num(r.win_roi),
  }));
}

export interface RunningStyleStat {
  runningStyle: string;
  n: number;
  wins: number;
  top3: number;
  winRate: number;
  top3Rate: number;
  winRoi: number;
}

export function loadRunningStyle(): RunningStyleStat[] {
  return readCsv('02_running_style_overall.csv').map((r) => ({
    runningStyle: r.running_style ?? '',
    n: num(r.n),
    wins: num(r.wins),
    top3: num(r.top3),
    winRate: num(r.win_rate),
    top3Rate: num(r.top3_rate),
    winRoi: num(r.win_roi),
  }));
}

export interface PrevDistStat {
  prevDistGrp: string;
  n: number;
  wins: number;
  top3: number;
  winRate: number;
  top3Rate: number;
  winRoi: number;
}

export function loadPrevDistance(): PrevDistStat[] {
  return readCsv('04_prev_distance.csv').map((r) => ({
    prevDistGrp: r.prev_distance_grp ?? r.prev_dist_grp ?? r.bin ?? '',
    n: num(r.n),
    wins: num(r.wins),
    top3: num(r.top3),
    winRate: num(r.win_rate),
    top3Rate: num(r.top3_rate),
    winRoi: num(r.win_roi),
  }));
}

export interface SireRanking {
  sireName: string;
  n: number;
  wins: number;
  top3: number;
  strong: number;
  winRate: number;
  top3Rate: number;
  strongRate: number;
  winRoi: number;
}

export function loadSireRanking(): SireRanking[] {
  return readCsv('06_sire_ranking.csv').map((r) => ({
    sireName: r.sire_name ?? '',
    n: num(r.n),
    wins: num(r.wins),
    top3: num(r.top3),
    strong: num(r.strong),
    winRate: num(r.win_rate),
    top3Rate: num(r.top3_rate),
    strongRate: num(r.strong_rate),
    winRoi: num(r.win_roi),
  }));
}

export interface JockeyTrainerStat {
  name: string;
  n: number;
  wins: number;
  top3: number;
  strong: number;
  winRate: number;
  top3Rate: number;
  strongRate: number;
  winRoi: number;
}

function _loadJockeyTrainer(filename: string, nameKey: string): JockeyTrainerStat[] {
  return readCsv(filename).map((r) => ({
    name: r[nameKey] ?? '',
    n: num(r.n),
    wins: num(r.wins),
    top3: num(r.top3),
    strong: num(r.strong),
    winRate: num(r.win_rate),
    top3Rate: num(r.top3_rate),
    strongRate: num(r.strong_rate),
    winRoi: num(r.win_roi),
  }));
}

export function loadJockeyTop3(): JockeyTrainerStat[] {
  return _loadJockeyTrainer('07_jockey_top3.csv', 'jockey_name');
}

export function loadTrainerTop3(): JockeyTrainerStat[] {
  return _loadJockeyTrainer('07_trainer_top3.csv', 'trainer_name');
}

export interface QuartileStat {
  quartile: string;
  n: number;
  wins: number;
  top3: number;
  strong: number;
  winRate: number;
  top3Rate: number;
  strongRate: number;
  winRoi: number;
}

function _loadQuartile(filename: string): QuartileStat[] {
  return readCsv(filename).map((r) => ({
    quartile: r.quartile ?? '',
    n: num(r.n),
    wins: num(r.wins),
    top3: num(r.top3),
    strong: num(r.strong),
    winRate: num(r.win_rate),
    top3Rate: num(r.top3_rate),
    strongRate: num(r.strong_rate),
    winRoi: num(r.win_roi),
  }));
}

export const loadP2CornerFirst = () => _loadQuartile('p2_corner_first_avg.csv');
export const loadP2Last3fAvg = () => _loadQuartile('p2_last_3f_avg.csv');
export const loadP2Last3fMin = () => _loadQuartile('p2_last_3f_min.csv');
export const loadP2ShortL3f = () => _loadQuartile('p2_short_l3f.csv');

// =====================================================
// Phase 3 backtest metrics
// =====================================================

export interface Phase3Metrics {
  polaris_only: {
    n_races: number;
    top3_hit_rate: number;
    top1_wins: number;
    top1_count: number;
    top1_win_rate: number;
    top1_roi: number;
    top3_count: number;
    top3_roi: number;
  };
  polaris_rule: Phase3Metrics['polaris_only'];
  rejected_analysis: {
    n_rejected: number;
    rejected_top3_rate: number;
    n_non_rejected: number;
    non_rejected_top3_rate: number;
  };
}

export function loadPhase3Metrics(): Phase3Metrics | null {
  if (!fs.existsSync(PHASE3_METRICS_PATH)) return null;
  const content = fs.readFileSync(PHASE3_METRICS_PATH, 'utf-8');
  try {
    const parsed = JSON.parse(content);
    return parsed.metrics as Phase3Metrics;
  } catch {
    return null;
  }
}

// =====================================================
// 統合ローダー (一回で全 stats を取得)
// =====================================================

export interface NiigataPhase12Bundle {
  frameOverall: FrameStat[];
  frameXStyle: FrameStyleStat[];
  runningStyle: RunningStyleStat[];
  prevDistance: PrevDistStat[];
  sireRanking: SireRanking[];
  jockeyTop3: JockeyTrainerStat[];
  trainerTop3: JockeyTrainerStat[];
  p2CornerFirst: QuartileStat[];
  p2Last3fMin: QuartileStat[];
  p2ShortL3f: QuartileStat[];
  phase3Metrics: Phase3Metrics | null;
}

export function loadNiigataPhase12Bundle(): NiigataPhase12Bundle {
  return {
    frameOverall: loadFrameOverall(),
    frameXStyle: loadFrameXStyle(),
    runningStyle: loadRunningStyle(),
    prevDistance: loadPrevDistance(),
    sireRanking: loadSireRanking(),
    jockeyTop3: loadJockeyTop3(),
    trainerTop3: loadTrainerTop3(),
    p2CornerFirst: loadP2CornerFirst(),
    p2Last3fMin: loadP2Last3fMin(),
    p2ShortL3f: loadP2ShortL3f(),
    phase3Metrics: loadPhase3Metrics(),
  };
}
