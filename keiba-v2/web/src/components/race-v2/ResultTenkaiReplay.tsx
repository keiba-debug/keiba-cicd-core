'use client';

/**
 * 🎬 結果リプレイ + 予想答え合わせ (Session 186)
 *
 * CourseReplay エンジンに「実測データのコマ」を流し込む:
 *   コーナー通過順位(1角..4角・JRA-VAN passing_orders) → ゴール(実着順・タイム差=着差)
 * さらに比較用コマとして「予想ゴール(JRDB展開予想)」「MLゴール(AR着差回帰)」を並べ、
 * 実ゴール⇄予想ゴールの切替アニメで「どれくらい当たっていたか」を可視化する。
 * 一致度(Spearman ρ)バッジ + 馬単位の的中/外れリング付き。
 */

import React from 'react';
import { HorseEntry, parseFinishPosition } from '@/types/race-data';
import type { LegProfile } from '@/lib/data/leg-profile-reader';
import type { MlPredictionEntry } from './HorseEntryTable';
import CourseReplay, { COURSE_ANCHORS, LEFT_HANDED_TRACKS } from './CourseReplay';
import type { CourseFrameDef, CourseHorse, CourseFramePos } from './CourseReplay';
import { buildMlGoalFrame } from './TenkaiSection';
import { parsePassingOrders, timeToSeconds, SEC_PER_HALF_BASHIN } from '@/lib/data/result-utils';

/** タイム差→半馬身換算 (1馬身 ≒ 0.16秒 → 半馬身 0.08秒) */
const SEC_PER_HALF = SEC_PER_HALF_BASHIN;

/** Spearman ρ (同順位は平均ランク)。n<3 は null */
function spearman(pairs: Array<[number, number]>): number | null {
  const n = pairs.length;
  if (n < 3) return null;
  const rank = (vals: number[]): number[] => {
    const idx = vals.map((v, i) => [v, i] as const).sort((a, b) => a[0] - b[0]);
    const r = new Array<number>(n).fill(0);
    let i = 0;
    while (i < n) {
      let j = i;
      while (j + 1 < n && idx[j + 1][0] === idx[i][0]) j++;
      const avg = (i + j) / 2 + 1;
      for (let k = i; k <= j; k++) r[idx[k][1]] = avg;
      i = j + 1;
    }
    return r;
  };
  const ra = rank(pairs.map(p => p[0]));
  const rb = rank(pairs.map(p => p[1]));
  const ma = ra.reduce((s, v) => s + v, 0) / n;
  const mb = rb.reduce((s, v) => s + v, 0) / n;
  let num = 0, da = 0, db = 0;
  for (let k = 0; k < n; k++) {
    const a = ra[k] - ma, b = rb[k] - mb;
    num += a * b; da += a * a; db += b * b;
  }
  return da > 0 && db > 0 ? num / Math.sqrt(da * db) : null;
}

/** 内外のフォールバック: JRDBコース取りが無い馬は順位の3レーン循環(内1.5/中3/外4.5)で散らして重なりを防ぐ */
const laneOf = (order: number): number => [3, 1.5, 4.5][order % 3];

const rhoColor = (rho: number): string =>
  rho >= 0.7 ? 'text-emerald-600 dark:text-emerald-400 font-semibold'
  : rho >= 0.4 ? 'text-amber-600 dark:text-amber-400'
  : 'text-red-500 dark:text-red-400';

interface ResultTenkaiReplayProps {
  entries: HorseEntry[];
  /** JRDB展開予想 (予想ゴールコマ・legProfiles.jrdb) */
  legProfiles?: Record<number, LegProfile> | null;
  /** ML予測 (MLゴールコマ) */
  mlPredictions?: Record<number, MlPredictionEntry>;
  /** 場名 (右/左回り判定) */
  track?: string;
}

export default function ResultTenkaiReplay({ entries, legProfiles, mlPredictions, track }: ResultTenkaiReplayProps) {
  // --- 完走馬の実測データを収集 ---
  const finishers = entries
    .map(e => {
      const r = e.result;
      if (!r) return null;
      const finish = parseFinishPosition(r.finish_position);
      if (!finish || finish <= 0) return null;
      const corners = parsePassingOrders(r.passing_orders, entries.length);
      return { e, finish, corners, timeSec: timeToSeconds(r.time) };
    })
    .filter((v): v is NonNullable<typeof v> => v !== null);
  if (finishers.length < 2) return null;

  const nCorners = Math.min(4, Math.max(...finishers.map(f => f.corners.length)));
  if (nCorners < 1) return null;

  const winnerSec = Math.min(...finishers.map(f => f.timeSec ?? Infinity));

  // --- 比較用コマの材料 ---
  const devs = entries
    .map(e => mlPredictions?.[e.horse_number]?.ar_deviation)
    .filter((v): v is number => v != null);
  const hasMl = devs.length >= 2;
  const hasPred = !!legProfiles && finishers.some(f => legProfiles[f.e.horse_number]?.jrdb?.goal);

  // --- コマ定義: [コーナー...] → ゴール(結果) → 予想ゴール → MLゴール ---
  const cornerLabels = ['1角', '2角', '3角', '4角'].slice(4 - nCorners);
  const cornerAnchors = [COURSE_ANCHORS.c1, COURSE_ANCHORS.c2, COURSE_ANCHORS.c3, COURSE_ANCHORS.c4].slice(4 - nCorners);
  const frameDefs: CourseFrameDef[] = [
    ...cornerLabels.map((label, i) => ({
      key: `c${i}`, label, anchor: cornerAnchors[i], inPlay: true,
    })),
    { key: 'rgoal', label: 'ゴール(結果)', anchor: COURSE_ANCHORS.goal, inPlay: true },
    ...(hasPred
      ? [{
          key: 'pgoal', label: '予想ゴール', anchor: COURSE_ANCHORS.goal, accent: 'pred' as const,
          buttonTitle: 'JRDB展開予想のゴール隊列 — 結果と切り替えると答え合わせ(動く馬=外れた馬)',
        }]
      : []),
    ...(hasMl
      ? [{
          key: 'ml', label: 'MLゴール', anchor: COURSE_ANCHORS.goal, accent: 'ml' as const,
          buttonTitle: 'ML(AR着差回帰)の予想着順 — 結果と切り替えると答え合わせ',
        }]
      : []),
  ];

  // --- 馬ごとのコマ列 ---
  // JRDB実測コース取り（1:最内〜5:大外）が全馬同レーンだと重なるので、実測がある馬が2レーン以上に散る場合のみ採用
  const toriLanes = new Set(
    finishers.map(f => f.e.jrdb_course_tori).filter((v): v is number => v != null && v >= 1 && v <= 5)
  );
  const useTori = toriLanes.size >= 2;

  const horses: CourseHorse[] = finishers.map(({ e, finish, corners, timeSec }) => {
    // 内外: JRDB実測コース取り（レース全体の代表値）→ 無ければ順位循環フォールバック
    const tori = useTori && e.jrdb_course_tori != null && e.jrdb_course_tori >= 1 && e.jrdb_course_tori <= 5
      ? e.jrdb_course_tori
      : null;
    // コーナー通過 (馬側のコーナー数が少ない場合は末尾=4角側に揃える)
    const cframes: (CourseFramePos | undefined)[] = new Array(nCorners).fill(undefined);
    const offset = nCorners - Math.min(corners.length, nCorners);
    corners.slice(-nCorners).forEach((o, i) => {
      cframes[offset + i] = { order: o, diff: (o - 1) * 2, inout: tori ?? laneOf(o) };
    });
    // ゴール(結果): タイム差→半馬身。タイム欠損は着順から概算
    const diffHl = timeSec != null && winnerSec !== Infinity
      ? Math.min(40, Math.round(((timeSec - winnerSec) / SEC_PER_HALF) * 10) / 10)
      : (finish - 1) * 2;
    const goalFrame: CourseFramePos = { order: finish, diff: diffHl, inout: tori ?? laneOf(finish) };
    // 比較用コマ
    const jrGoal = legProfiles?.[e.horse_number]?.jrdb?.goal;
    const mlFrame = hasMl
      ? buildMlGoalFrame(mlPredictions?.[e.horse_number]?.ar_deviation, devs, jrGoal?.inout ?? goalFrame.inout)
      : undefined;
    // 答え合わせリング (JRDB予想ゴール vs 実着順)
    const ring = jrGoal
      ? Math.abs(jrGoal.order - finish) <= 1 ? ('hit' as const)
        : Math.abs(jrGoal.order - finish) >= 5 ? ('miss' as const)
        : null
      : null;
    return {
      num: e.horse_number,
      name: e.horse_name,
      waku: e.entry_data?.waku,
      ring,
      frames: [
        ...cframes,
        goalFrame,
        ...(hasPred ? [jrGoal ?? undefined] : []),
        ...(hasMl ? [mlFrame] : []),
      ],
    };
  });

  // --- 一致度 (Spearman ρ): 予想順位 vs 実着順 ---
  const rhoJrdb = hasPred
    ? spearman(
        finishers
          .map(f => {
            const o = legProfiles?.[f.e.horse_number]?.jrdb?.goal?.order;
            return o != null ? ([o, f.finish] as [number, number]) : null;
          })
          .filter((v): v is [number, number] => v !== null),
      )
    : null;
  const rhoMl = hasMl
    ? spearman(
        finishers
          .map(f => {
            const dev = mlPredictions?.[f.e.horse_number]?.ar_deviation;
            return dev != null ? ([-dev, f.finish] as [number, number]) : null;   // 偏差値高い=上位着順
          })
          .filter((v): v is [number, number] => v !== null),
      )
    : null;

  const mirrored = !!track && LEFT_HANDED_TRACKS.has(track);

  const headerExtra = (rhoJrdb != null || rhoMl != null) ? (
    <span className="ml-3 font-normal">
      答え合わせ(隊列一致度):
      {rhoJrdb != null && <span className={`ml-1.5 ${rhoColor(rhoJrdb)}`}>JRDB予想 ρ={rhoJrdb.toFixed(2)}</span>}
      {rhoMl != null && <span className={`ml-1.5 ${rhoColor(rhoMl)}`}>ML ρ={rhoMl.toFixed(2)}</span>}
    </span>
  ) : undefined;

  return (
    <CourseReplay
      frameDefs={frameDefs}
      horses={horses}
      mirrored={mirrored}
      title="結果リプレイ・答え合わせ"
      headerNote={`位置=実測(コーナー通過順位・着差) / 帽色=枠番${useTori ? ' / 内外=JRDB実測コース取り' : ''}`}
      headerExtra={headerExtra}
      playLabel="リプレイ"
      ringFrameKeys={['rgoal', 'pgoal']}
      legendNote={`コース模式図(${mirrored ? '左' : '右'}回り) / 通過順位=JRA-VAN / ゴール着差=タイム差の半馬身換算 / 内外=${useTori ? 'JRDB実測コース取り(1最内〜5大外)' : '順位から機械的に散らした仮配置'}`}
    />
  );
}
