/**
 * 調教師パターン読み込み & マッチングユーティリティ
 *
 * trainer_patterns.json から調教師の勝負パターンを読み込み、
 * 現在の調教データとのマッチングを行う。
 *
 * パフォーマンス: 1回読み込み、1時間キャッシュ（trainer-index.tsと同パターン）
 */

import fs from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT_DIR } from '@/lib/config';
import type { TrainingSummaryData } from './training-summary-reader';

// =============================================
// Types
// =============================================

export interface PatternStats {
  win_rate: number;
  top3_rate: number;
  top5_rate: number;
  avg_finish: number;
  sample_size: number;
  confidence: string;  // 'high' | 'medium' | 'low'
  lift?: number;       // overall_top3_rateとの差
}

export interface TrainerPattern {
  description: string;
  human_label?: string | null;
  conditions: Record<string, unknown>;
  stats: PatternStats;
}

export interface TrainerPatternInfo {
  jvn_code: string;
  keibabook_ids: string[];
  name: string;
  tozai: string;
  comment: string;
  total_runners: number;
  overall_stats: {
    win_rate: number;
    top3_rate: number;
    top5_rate: number;
    avg_finish: number;
    sample_size: number;
  };
  best_patterns: TrainerPattern[];
  all_patterns: Record<string, Record<string, PatternStats>>;
}

export interface TrainerPatternMatch {
  matchScore: number;          // 0.0 - 1.0
  description: string;
  humanLabel?: string | null;
  stats: PatternStats;
}

// =============================================
// Cache
// =============================================

let patternsCache: Map<string, TrainerPatternInfo> | null = null;
let keibabookIdToJvnCache: Map<string, string> | null = null;
let cacheLoadedAt = 0;
const CACHE_TTL = 60 * 60 * 1000; // 1時間

// =============================================
// Loader
// =============================================

/**
 * trainer_patterns.json を読み込み（キャッシュあり）
 */
export function loadTrainerPatterns(): Map<string, TrainerPatternInfo> {
  const now = Date.now();

  if (patternsCache && (now - cacheLoadedAt) < CACHE_TTL) {
    return patternsCache;
  }

  patternsCache = new Map();
  keibabookIdToJvnCache = new Map();

  try {
    const filePath = path.join(KEIBA_DATA_ROOT_DIR, 'target', 'trainer_patterns.json');

    if (!fs.existsSync(filePath)) {
      // ファイルがなければ空のまま（まだ分析未実行）
      cacheLoadedAt = now;
      return patternsCache;
    }

    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);
    const trainers = data.trainers || {};

    for (const [jvnCode, info] of Object.entries(trainers)) {
      const typed = info as TrainerPatternInfo;
      patternsCache.set(jvnCode, typed);

      // keibabook_id → jvn_code の逆引き構築
      for (const kbId of typed.keibabook_ids || []) {
        keibabookIdToJvnCache.set(kbId, jvnCode);
      }
    }
  } catch {
    // 読み込み失敗は静かに無視
  }

  cacheLoadedAt = now;
  return patternsCache;
}

// =============================================
// Pattern Matching
// =============================================

/**
 * ラップ分類のグループ（先頭文字）を取得
 */
function getLapGroup(lapClass: string): string {
  if (!lapClass) return '';
  if (lapClass === 'SS') return 'SS';
  return lapClass[0] || '';
}

/**
 * 現在の調教データがパターン条件にマッチするか判定
 */
function matchesConditions(
  conditions: Record<string, unknown>,
  summary: TrainingSummaryData,
): boolean {
  for (const [key, value] of Object.entries(conditions)) {
    switch (key) {
      case 'finalLocation':
        if (summary.finalLocation !== value) return false;
        break;
      case 'acceleration':
        // finalLapの末尾文字が加速記号
        if (!summary.finalLap) return false;
        {
          const lastChar = summary.finalLap.slice(-1);
          if (lastChar !== value) return false;
        }
        break;
      case 'hasGoodTime':
        if (value === true && summary.finalSpeed !== '◎') return false;
        break;
      case 'finalLapClassGroup': {
        if (!summary.finalLap) return false;
        const allowed = value as string[];
        if (!allowed.includes(summary.finalLap)) {
          // グループマッチも試行
          const group = getLapGroup(summary.finalLap);
          if (!allowed.some(a => getLapGroup(a) === group)) return false;
        }
        break;
      }
      case 'countLabel':
        // training summaryにcountLabelは直接ないが、timeRank等で代用は難しい
        // このケースはスキップ（マッチしたとみなす）
        break;
      case 'timeClass':
        if (summary.timeRank !== value) return false;
        break;
      // --- 1週前調教 ---
      case 'weekAgoHasGoodTime':
        if (value === true && summary.weekAgoSpeed !== '◎') return false;
        if (value === false && summary.weekAgoSpeed === '◎') return false;
        break;
      case 'weekAgoLapClassGroup': {
        if (!summary.weekAgoLap) return false;
        const allowedWA = value as string[];
        const groupWA = getLapGroup(summary.weekAgoLap);
        if (!allowedWA.some(a => getLapGroup(a) === groupWA || a === groupWA)) return false;
        break;
      }
      case 'weekAgoLocation':
        if (summary.weekAgoLocation !== value) return false;
        break;
      case 'weekAgoAcceleration':
        if (!summary.weekAgoLap) return false;
        if (summary.weekAgoLap.slice(-1) !== value) return false;
        break;
      // --- 土日調教 ---
      case 'weekendHasGoodTime':
        if (value === true && summary.weekendSpeed !== '◎') return false;
        break;
      case 'weekendLapClassGroup': {
        if (!summary.weekendLap) return false;
        const allowedWE = value as string[];
        const groupWE = getLapGroup(summary.weekendLap);
        if (!allowedWE.some(a => getLapGroup(a) === groupWE || a === groupWE)) return false;
        break;
      }
      case 'weekendLocation':
        if (summary.weekendLocation !== value) return false;
        break;
      case 'weekendAcceleration':
        if (!summary.weekendLap) return false;
        if (summary.weekendLap.slice(-1) !== value) return false;
        break;
    }
  }
  return true;
}

/**
 * 調教師の勝負パターンと現在の調教をマッチング
 *
 * @param keibabookId 競馬ブック厩舎ID
 * @param summary 現在の調教サマリデータ
 * @returns マッチ結果 or null
 */
export function evaluatePatternMatch(
  keibabookId: string,
  summary: TrainingSummaryData,
): TrainerPatternMatch | null {
  if (!keibabookId || !summary) return null;

  const patterns = loadTrainerPatterns();
  if (patterns.size === 0) return null;

  // keibabook_id → jvn_code
  const jvnCode = keibabookIdToJvnCache?.get(keibabookId);
  if (!jvnCode) return null;

  const trainerInfo = patterns.get(jvnCode);
  if (!trainerInfo || !trainerInfo.best_patterns || trainerInfo.best_patterns.length === 0) {
    return null;
  }

  // 最終追い切りデータがなければマッチ不可
  if (!summary.finalLap) return null;

  // ベストパターンから順にマッチング
  for (const pattern of trainerInfo.best_patterns) {
    if (matchesConditions(pattern.conditions, summary)) {
      return {
        matchScore: Math.min(1.0, pattern.stats.top3_rate * 1.5),
        description: pattern.description,
        humanLabel: pattern.human_label,
        stats: pattern.stats,
      };
    }
  }

  return null;
}

/**
 * 調教師のパターン情報を取得（jvn_codeベース）
 */
export function getTrainerPatternInfo(jvnCode: string): TrainerPatternInfo | null {
  const patterns = loadTrainerPatterns();
  return patterns.get(jvnCode) || null;
}
