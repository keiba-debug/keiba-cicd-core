/**
 * IDM基準値リーダー (JRDB IDM)
 * サーバーサイド専用
 */

import { readFileSync, existsSync } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// ── 型 ──

export interface IDMStatsBlock {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
}

export interface IDMGradeStandard {
  sample_count: number;
  horse_count: number;
  winner_count: number;
  all: IDMStatsBlock;
  winner: IDMStatsBlock | null;
  fallback_from?: string;
  fallback_to?: string;
  original_sample_count?: number;
}

export interface IDMRaceNameStandard {
  grade: string;
  count: number;
  years: string[];
  all_mean: number;
  winner_mean?: number;
  winner_min?: number;
  winner_max?: number;
  yearly_winners?: Array<{ year: string; winner_idm: number }>;
}

export interface IDMStandards {
  metadata: {
    created_at: string;
    source: string;
    years: string;
    total_races: number;
    version: string;
    global_mean_idm: number;
    global_winner_mean_idm: number;
  };
  by_grade: Record<string, IDMGradeStandard>;
  by_race_name?: Record<string, IDMRaceNameStandard>;
}

// ── キャッシュ ──

let cached: IDMStandards | null = null;
let cacheTime = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5分

function getPath(): string {
  return path.join(DATA3_ROOT, 'analysis', 'idm_standards.json');
}

/**
 * IDM基準値を読み込む（同期、サーバー専用）
 */
export function getIDMStandards(): IDMStandards | null {
  if (cached && Date.now() - cacheTime < CACHE_TTL) {
    return cached;
  }
  try {
    const filePath = getPath();
    if (!existsSync(filePath)) return null;
    const content = readFileSync(filePath, 'utf-8');
    cached = JSON.parse(content) as IDMStandards;
    cacheTime = Date.now();
    return cached;
  } catch {
    return null;
  }
}

/**
 * 特定グレードの勝ち馬IDM基準を取得
 * gradeKeyの例: "G1_古馬", "1勝クラス", "未勝利"
 */
export function getWinnerIDMStandard(gradeKey: string): number | null {
  const standards = getIDMStandards();
  if (!standards) return null;
  const grade = standards.by_grade[gradeKey];
  if (!grade?.winner) return null;
  return grade.winner.mean;
}

/**
 * レース名で基準値を取得（重賞用）
 * race_name から全角英数を半角に変換し、装飾を除去して部分一致検索
 *
 * 例: "Ｇ２フィリーズＲ (牝)" → normalize → "フィリーズ"
 *     JSON key "報知杯フィリーズレビュー" → normalize → "フィリーズレビュー"
 *     → 部分一致で "フィリーズ" ⊂ "フィリーズレビュー" でマッチ
 */
export function getWinnerIDMByRaceName(raceName: string): IDMRaceNameStandard | null {
  const standards = getIDMStandards();
  if (!standards?.by_race_name) return null;

  // 完全一致
  if (standards.by_race_name[raceName]) {
    return standards.by_race_name[raceName];
  }

  // 正規化: 全角英数→半角、G1/G2/G3/グレード表記・冠名・略称・括弧を除去
  const normalize = (s: string) => s
    .replace(/[Ａ-Ｚａ-ｚ０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))
    .replace(/[（）\(\)]/g, '')
    .replace(/\s+/g, '')
    .replace(/G[1-3]|GI+/gi, '')
    .replace(/農$/, '')  // JRA-VAN末尾の「農」
    .replace(/[牝牡セ]$/, '')  // 性別表記
    .trim();

  // コアワード抽出: 冠名(〜杯/〜賞)を除去してレース固有名を抽出
  const extractCore = (s: string) => {
    const n = normalize(s);
    // "報知杯フィリーズレビュー" → "フィリーズレビュー"
    // "日刊スポーツ賞中山金杯" → "中山金杯"
    const m = n.match(/(?:杯|賞)(.+)/);
    return m ? m[1] : n;
  };

  const inputCore = extractCore(raceName);
  // 入力が短すぎる場合はスキップ（誤マッチ防止）
  if (inputCore.length < 3) return null;

  // 正規化した入力でマッチング
  const normalizedInput = normalize(raceName);

  let bestMatch: { name: string; data: IDMRaceNameStandard; score: number } | null = null;

  for (const [name, data] of Object.entries(standards.by_race_name)) {
    const normalizedKey = normalize(name);
    const keyCore = extractCore(name);

    // 完全正規化一致
    if (normalizedInput === normalizedKey) {
      return data;
    }

    // コアワード一致（最も信頼性が高い）
    if (inputCore === keyCore) {
      return data;
    }

    // 部分一致: コアワード間
    if (inputCore.length >= 3 && keyCore.length >= 3) {
      if (keyCore.includes(inputCore) || inputCore.includes(keyCore)) {
        const score = Math.min(inputCore.length, keyCore.length);
        if (!bestMatch || score > bestMatch.score) {
          bestMatch = { name, data, score };
        }
      }
    }
  }

  return bestMatch?.data ?? null;
}

/**
 * レースのgrade文字列からIDM基準グレードキーを推定
 * raceData の grade / race_class 等から適切なキーを返す
 */
export function resolveIDMGradeKey(
  grade: string,
  ageClass?: string,
): string {
  // 重賞・OP系はage_class付き
  const ageSeparated = ['G1', 'G2', 'G3', 'OP', 'Listed'];
  if (ageSeparated.includes(grade) && ageClass) {
    return `${grade}_${ageClass}`;
  }
  return grade;
}
