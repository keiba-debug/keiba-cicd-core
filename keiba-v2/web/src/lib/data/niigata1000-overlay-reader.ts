/**
 * vega-niigata1000 overlay リーダー (Server-side)
 *
 * predictions.json の race-level/entry-level に書き込まれた
 * niigata1000_applied / entries[].niigata1000 を抽出する。
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import type { NiigataOverlay } from './predictions-reader';

export interface NiigataChokuRaceSummary {
  raceId: string;
  applied: boolean;
  /** 推奨上位 (selection_score 降順、除外馬は末尾) */
  ranked: Array<{
    umaban: number;
    horseName: string;
    polarisP: number;
    overlay: NiigataOverlay;
  }>;
}

/**
 * race_id からその日の predictions.json を読み、
 * niigata1000 オーバーレイ結果を取得する。
 *
 * 千直未開催・overlay未適用なら null。
 */
export function getNiigataChokuOverlay(
  raceId16: string,
  date: string,  // YYYY-MM-DD
): NiigataChokuRaceSummary | null {
  if (!raceId16 || raceId16.length !== 16) return null;
  const [y, m, d] = date.split('-');
  if (!y || !m || !d) return null;

  const predPath = path.join(DATA3_ROOT, 'races', y, m, d, 'predictions.json');
  if (!fs.existsSync(predPath)) return null;

  let preds: { races?: Array<Record<string, unknown>> };
  try {
    preds = JSON.parse(fs.readFileSync(predPath, 'utf-8'));
  } catch {
    return null;
  }

  const race = (preds.races ?? []).find((r) => r.race_id === raceId16);
  if (!race) return null;
  if (!race.niigata1000_applied) return null;

  const entries = (race.entries ?? []) as Array<Record<string, unknown>>;
  const ranked: NiigataChokuRaceSummary['ranked'] = [];
  for (const e of entries) {
    const overlay = e.niigata1000 as NiigataOverlay | undefined;
    if (!overlay || 'error' in overlay) continue;
    ranked.push({
      umaban: Number(e.umaban) || 0,
      horseName: String(e.horse_name ?? ''),
      polarisP: Number(e.pred_proba_p) || 0,
      overlay,
    });
  }

  // selection_score 降順、null は末尾
  ranked.sort((a, b) => {
    const sa = a.overlay.selection_score;
    const sb = b.overlay.selection_score;
    if (sa === null && sb === null) return b.overlay.display_score - a.overlay.display_score;
    if (sa === null) return 1;
    if (sb === null) return -1;
    return sb - sa;
  });

  return {
    raceId: raceId16,
    applied: true,
    ranked,
  };
}

/**
 * 指定日の predictions.json から、千直 overlay が付いた race_id 一覧を返す。
 * /predictions ページで「千直」バッジを出す馬を判定するのに使う。
 */
export function getNiigataChokuRaceIdsForDate(date: string): Set<string> {
  const [y, m, d] = date.split('-');
  if (!y || !m || !d) return new Set();
  const predPath = path.join(DATA3_ROOT, 'races', y, m, d, 'predictions.json');
  if (!fs.existsSync(predPath)) return new Set();
  try {
    const preds = JSON.parse(fs.readFileSync(predPath, 'utf-8')) as {
      races?: Array<{ race_id: string; niigata1000_applied?: boolean }>;
    };
    return new Set(
      (preds.races ?? [])
        .filter((r) => r.niigata1000_applied)
        .map((r) => r.race_id),
    );
  } catch {
    return new Set();
  }
}
