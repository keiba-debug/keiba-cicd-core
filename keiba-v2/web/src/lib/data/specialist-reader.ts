/**
 * Specialist 予想画面 (/specialist/[raceId]) 用データリーダー (Server-side)
 *
 * 1つのレースに適用される全 specialist モデルを一覧化する。
 * 現状: vega-niigata1000 のみ。将来は血統モデル等を追加。
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import type { PredictionRace, NiigataOverlay } from './predictions-reader';

export type SpecialistModelId = 'niigata1000';

export interface SpecialistModelMeta {
  id: SpecialistModelId;
  label: string;        // タブラベル「🌪 千直」等
  fullName: string;     // フルネーム「vega-niigata1000」等
  description: string;  // 短い説明（ヘッダー表示用）
  encyclopediaUrl: string;     // コース事典/解説ページURL
  dashboardUrl?: string;        // 全データダッシュボードURL（任意）
}

const NIIGATA_1000_META: SpecialistModelMeta = {
  id: 'niigata1000',
  label: '🌪 千直',
  fullName: 'vega-niigata1000',
  description: '新潟芝1000m直線専用、polaris+rule v0.2',
  encyclopediaUrl: '/analysis/specialists/niigata-1000m',
  dashboardUrl: '/analysis/specialists/niigata-1000m?tab=data',
};

export interface RaceMetaForSpecialist {
  raceId: string;
  date: string;          // YYYY-MM-DD
  venueName: string;
  raceNumber: number;
  raceName: string;
  distance: number;
  trackType: string;     // "芝" / "ダ" / "障"
  numRunners: number;
  grade?: string;
  predictionRace: PredictionRace;
  appliedModels: SpecialistModelMeta[];
}

/**
 * raceId(16桁) からその日の predictions.json を読み、
 * 適用されている specialist モデル一覧を返す。
 */
export function getRaceMetaForSpecialist(raceId16: string): RaceMetaForSpecialist | null {
  if (!raceId16 || raceId16.length !== 16) return null;
  // raceId YYYYMMDDJJKKNNRR から日付を取り出す
  const y = raceId16.substring(0, 4);
  const m = raceId16.substring(4, 6);
  const d = raceId16.substring(6, 8);
  const date = `${y}-${m}-${d}`;

  const predPath = path.join(DATA3_ROOT, 'races', y, m, d, 'predictions.json');
  if (!fs.existsSync(predPath)) return null;

  let preds: { races?: PredictionRace[] };
  try {
    preds = JSON.parse(fs.readFileSync(predPath, 'utf-8'));
  } catch {
    return null;
  }

  const race = (preds.races ?? []).find((r) => r.race_id === raceId16);
  if (!race) return null;

  const appliedModels: SpecialistModelMeta[] = [];
  if (race.niigata1000_applied) {
    appliedModels.push(NIIGATA_1000_META);
  }
  // 将来: race.<other_specialist>_applied をチェックして push

  return {
    raceId: raceId16,
    date,
    venueName: race.venue_name ?? '',
    raceNumber: race.race_number ?? 0,
    raceName: (race as { race_name?: string | null }).race_name ?? '',
    distance: race.distance ?? 0,
    trackType: race.track_type ?? '',
    numRunners: race.num_runners ?? 0,
    grade: race.grade,
    predictionRace: race,
    appliedModels,
  };
}

/** Niigata 千直 overlay 配列を display_score 降順で取得 (panel 用ヘルパー) */
export function getNiigataChokuRanked(
  race: PredictionRace,
): Array<{ umaban: number; horseName: string; polarisP: number; overlay: NiigataOverlay }> {
  const ranked: Array<{ umaban: number; horseName: string; polarisP: number; overlay: NiigataOverlay }> = [];
  for (const e of race.entries ?? []) {
    const overlay = e.niigata1000;
    if (!overlay || 'error' in overlay) continue;
    ranked.push({
      umaban: e.umaban,
      horseName: e.horse_name ?? '',
      polarisP: e.pred_proba_p ?? 0,
      overlay,
    });
  }
  ranked.sort((a, b) => {
    const sa = a.overlay.selection_score;
    const sb = b.overlay.selection_score;
    if (sa === null && sb === null) return b.overlay.display_score - a.overlay.display_score;
    if (sa === null) return 1;
    if (sb === null) return -1;
    return sb - sa;
  });
  return ranked;
}
