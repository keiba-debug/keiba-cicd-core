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
import { parsePassingOrders, timeToSeconds, marginToBashin, SEC_PER_HALF_BASHIN } from '@/lib/data/result-utils';

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

/** 内外の最終フォールバック: 順位の3レーン循環(内1.5/中3/外4.5)で散らして重なりを防ぐ */
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
    .filter((v): v is NonNullable<typeof v> => v !== null)
    // 着順ソート: ゴール着差の累積計算と、同位置に重なった馬の前後ずらし(dup shift)を着順準拠にする
    .sort((a, b) => a.finish - b.finish);
  if (finishers.length < 2) return null;

  const nCorners = Math.min(4, Math.max(...finishers.map(f => f.corners.length)));
  if (nCorners < 1) return null;

  const winnerSec = Math.min(...finishers.map(f => f.timeSec ?? Infinity));

  // --- ゴール隊列の先頭差 (半馬身): 着差(margin)の累積を優先 ---
  // 走破タイムは0.1秒粒度で、クビ/ハナ差の2〜4着が同値に潰れて並び順が壊れる (2026-06-28 函館11R で顕在化)。
  // 着差が取れない馬はタイム差(最低でも半馬身刻みで前の馬より後ろ)へフォールバック
  const goalDiffByNum = new Map<number, number>();
  {
    let acc = 0;
    finishers.forEach((f, k) => {
      if (k > 0) {
        const m = marginToBashin(f.e.result?.margin);
        if (m != null) {
          acc += m * 2;                                   // 馬身→半馬身
        } else {
          const t = f.timeSec != null && winnerSec !== Infinity ? (f.timeSec - winnerSec) / SEC_PER_HALF : null;
          acc = Math.max(acc + 0.5, t ?? 0);
        }
      }
      goalDiffByNum.set(f.e.horse_number, Math.min(40, Math.round(acc * 10) / 10));
    });
  }

  // --- 比較用コマの材料 ---
  const devs = entries
    .map(e => mlPredictions?.[e.horse_number]?.ar_deviation)
    .filter((v): v is number => v != null);
  const hasMl = devs.length >= 2;
  const hasPred = !!legProfiles && finishers.some(f => legProfiles[f.e.horse_number]?.jrdb?.goal);

  // --- コマ定義: スタート(枠順ゲート) → [コーナー...] → ゴール(結果) → 予想ゴール → MLゴール ---
  const cornerLabels = ['1角', '2角', '3角', '4角'].slice(4 - nCorners);
  const cornerAnchors = [COURSE_ANCHORS.c1, COURSE_ANCHORS.c2, COURSE_ANCHORS.c3, COURSE_ANCHORS.c4].slice(4 - nCorners);
  // 出遅れ馬 (実測SED出遅補正) がいるレースは「発走直後」の中間コマを挟んで出遅れを動きで表現する
  const hasSlow = finishers.some(f => (f.e.jrdb_deokure ?? 0) > 0);

  const frameDefs: CourseFrameDef[] = [
    {
      key: 'start', label: 'スタート', anchor: COURSE_ANCHORS.startStraight, inPlay: true, gate: true,
      buttonTitle: '枠順のゲート横一列 (確定情報) — 出遅れ馬は発走直後に下がる。1角への動きで誰がダッシュしたかが見える',
    },
    ...(hasSlow
      ? [{
          key: 'dash', label: '直後', anchor: COURSE_ANCHORS.startStraight - 80,
          inPlay: true, gate: true, hidden: true,
        } satisfies CourseFrameDef]
      : []),
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

  const maxNum = Math.max(...finishers.map(f => f.e.horse_number));

  // --- 内外レーンの確率的推定 (実測コース取りが無い馬用) ---
  // 進路データは現ソースに存在しないため経験則で近似する:
  //   ① 同じような位置取りの集団は内枠の馬がそのまま内を通ることが多い
  //   ② 残り3F(3角)以降に順位を上げた馬は外を通ってまくるケースが多い
  const alignedOrders = finishers.map(f => {
    const arr: (number | undefined)[] = new Array(nCorners).fill(undefined);
    const off = nCorners - Math.min(f.corners.length, nCorners);
    f.corners.slice(-nCorners).forEach((o, i) => { arr[off + i] = o; });
    return arr;
  });
  // フレーム f (0..nCorners-1=コーナー / nCorners=ゴール) → finisher添字 → レーン
  const lateFrom = Math.max(1, nCorners - 2);   // 残り3F圏 = 3角以降 (②は直前コーナーとの比較が必要)
  const heuristicLanes: Array<Map<number, number>> = [];
  for (let f = 0; f <= nCorners; f++) {
    const lanes = new Map<number, number>();
    const at = finishers
      .flatMap((fin, i) => {
        const order = f < nCorners ? alignedOrders[i][f] : fin.finish;
        if (order == null) return [];
        const waku = parseInt(fin.e.entry_data?.waku ?? '', 10);
        return [{ i, order, waku: waku >= 1 ? waku : fin.e.horse_number }];   // 枠欠損は馬番で代用(順序にのみ使用)
      })
      .sort((a, b) => a.order - b.order);
    // ① 近接順位3頭のグループ内で内枠→内レーン
    for (let g = 0; g < at.length; g += 3) {
      at.slice(g, g + 3)
        .sort((a, b) => a.waku - b.waku)
        .forEach((m, j) => lanes.set(m.i, [1.5, 3, 4.5][j]));
    }
    // ② 直前コーナーから2番手以上上げた馬は大外へ (まくり)
    if (f >= lateFrom) {
      for (const m of at) {
        const prev = alignedOrders[m.i][f - 1];
        if (prev != null && prev - m.order >= 2) lanes.set(m.i, 4.5);
      }
    }
    heuristicLanes.push(lanes);
  }

  const horses: CourseHorse[] = finishers.map(({ e, finish, corners }, idx) => {
    // 内外: JRDB実測コース取り（レース全体の代表値）→ 無ければ確率的推定レーン
    const tori = useTori && e.jrdb_course_tori != null && e.jrdb_course_tori >= 1 && e.jrdb_course_tori <= 5
      ? e.jrdb_course_tori
      : null;
    // スタート: 枠順ゲート横一列 (全馬 diff=0・内外=馬番で内→外に均等配置=ゲート番号そのまま)。
    // ゲートコマはエンジン側で前後ずらし無効なので、全馬が同じ線上に並ぶ
    const waku = parseInt(e.entry_data?.waku ?? '', 10);
    const gateLane = maxNum > 1 ? 1 + ((e.horse_number - 1) * 4) / (maxNum - 1) : 3;
    const startFrame: CourseFramePos = {
      order: e.horse_number,
      diff: 0,
      inout: gateLane,
      posLabel: `ゲート${waku >= 1 ? ` (枠${waku})` : ''}`,
    };
    // 発走直後: 出遅れ馬 (実測SED出遅補正のみ。is_slow_start=事前の癖フラグは結果側では使わない)
    // だけ1.75馬身下がる → ゲート一列からガクッと遅れる動きで出遅れを表現
    const slowStart = (e.jrdb_deokure ?? 0) > 0;
    const dashFrame: CourseFramePos | undefined = hasSlow
      ? {
          order: e.horse_number,
          diff: slowStart ? 3.5 : 0,
          inout: gateLane,
          posLabel: `スタート直後${slowStart ? '・出遅れ' : ''}`,
        }
      : undefined;
    // コーナー通過 (馬側のコーナー数が少ない場合は末尾=4角側に揃える)
    const cframes: (CourseFramePos | undefined)[] = new Array(nCorners).fill(undefined);
    const offset = nCorners - Math.min(corners.length, nCorners);
    corners.slice(-nCorners).forEach((o, i) => {
      cframes[offset + i] = { order: o, diff: (o - 1) * 2, inout: tori ?? heuristicLanes[offset + i].get(idx) ?? laneOf(o) };
    });
    // ゴール(結果): 着差累積 (goalDiffByNum) ベース。欠損は着順から概算
    const diffHl = goalDiffByNum.get(e.horse_number) ?? (finish - 1) * 2;
    const goalFrame: CourseFramePos = { order: finish, diff: diffHl, inout: tori ?? heuristicLanes[nCorners].get(idx) ?? laneOf(finish) };
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
        startFrame,
        ...(hasSlow ? [dashFrame] : []),
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
      headerNote={`位置=実測(枠順→コーナー通過順位→着差) / 帽色=枠番${useTori ? ' / 内外=JRDB実測コース取り' : ''}`}
      headerExtra={headerExtra}
      playLabel="リプレイ"
      ringFrameKeys={['rgoal', 'pgoal']}
      legendNote={`コース模式図(${mirrored ? '左' : '右'}回り) / スタート=枠順ゲート(出遅れは発走直後の動きで表現) / 通過順位=JRA-VAN / ゴール=着差(クビ/ハナ等)の累積換算 / 内外=${useTori ? 'JRDB実測コース取り(1最内〜5大外・欠損馬は確率的推定)' : '確率的推定(近い位置は内枠が内・3角以降の追い上げ馬は外)'}`}
    />
  );
}
