'use client';

/**
 * 🎬 コースリプレイ・エンジン (Session 186)
 *
 * 楕円コース模式図の上で「キーフレーム(順位差×内外)の列」を再生する汎用コンポーネント。
 * データソース非依存 — 予想(TenkaiSection)・結果リプレイ(ResultTenkaiReplay)・
 * 将来のML/スタート/風レイヤーが同じ土台に乗る。
 *
 * - コースパス: スタート直線 → 1-2角 → 向こう正面 → 3-4角 → 最終直線 → ゴール
 *   (「ゴール残距離」でパラメータ化。COURSE_ANCHORS で各地点を指定)
 * - 右回り基準で計算し、左回り(東京/中京/新潟)はX反転
 * - 内外はオーバル幾何で自動的に正しい(内=常にオーバル中心側)
 * - 再生は requestAnimationFrame でコース経路に沿って補間(コーナーを曲がる)
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { toCircleNumber } from '@/types/race-data';
import { Play } from 'lucide-react';

// ============================================================
// 型
// ============================================================

/** 1馬×1コマの隊列位置 (JrdbTenkaiFrame と構造互換) */
export interface CourseFramePos {
  order: number;                // 順位 (1=先頭)。gateコマではゲート番号(=馬番)
  diff: number | null;          // 先頭からの差 (半馬身単位・先頭=0)
  inout: number | null;         // 内外 1(最内)〜5(大外)
  posLabel?: string;            // ツールチップの位置表記を上書き (「◯番手」の代わり。ゲート等)
}

/** コマ定義 */
export interface CourseFrameDef {
  key: string;
  label: string;
  anchor: number;               // 先頭馬のゴール残距離 (COURSE_ANCHORS 参照)
  inPlay?: boolean;             // ▶再生シーケンスに含める (レース進行のコマ)
  accent?: 'ml' | 'pred';      // ボタン配色 (ml=紫 / pred=teal / 無指定=青)
  buttonTitle?: string;
  gate?: boolean;               // ゲート整列コマ (order=ゲート番号。テロップは順位変動でなく隊列形成を出す)
  hidden?: boolean;             // コマ選択ボタンを出さない (▶再生シーケンス専用の中間コマ。出遅れ演出等)
}

/** 1頭分の描画データ */
export interface CourseHorse {
  num: number;
  name: string;
  waku?: string;                          // 枠番 (帽色)
  bucket?: string;                        // 競馬ブック展開分類 (右下ドット)
  ring?: 'hit' | 'miss' | null;           // 答え合わせリング (ringFrameKeys のコマで表示)
  frames: (CourseFramePos | undefined)[]; // frameDefs と同順
}

export interface CourseReplayProps {
  frameDefs: CourseFrameDef[];
  horses: CourseHorse[];
  /** 左回りなら true (東京/中京/新潟) */
  mirrored: boolean;
  /** タイトル (デフォルト: 予想隊列図) */
  title?: string;
  /** ヘッダー右側の補足 (位置=… など) */
  headerNote?: string;
  /** ペース表示等の追加ヘッダーテキスト */
  paceNote?: string;
  /** 凡例右端の注記 */
  legendNote?: string;
  /** 再生ボタンのラベル (デフォルト: 再生) */
  playLabel?: string;
  /** 答え合わせリングを表示するコマの key */
  ringFrameKeys?: string[];
  /** ヘッダー左に差し込む追加要素 (一致度バッジ等) */
  headerExtra?: React.ReactNode;
}

// ============================================================
// 配色
// ============================================================

/** 枠番→帽色 (SVG用hex・getWakuColorのTailwind配色と同一) */
const WAKU_HEX: Record<number, { bg: string; text: string; stroke: string }> = {
  1: { bg: '#ffffff', text: '#111827', stroke: '#9ca3af' },
  2: { bg: '#111827', text: '#ffffff', stroke: '#111827' },
  3: { bg: '#dc2626', text: '#ffffff', stroke: '#b91c1c' },
  4: { bg: '#2563eb', text: '#ffffff', stroke: '#1d4ed8' },
  5: { bg: '#facc15', text: '#111827', stroke: '#eab308' },
  6: { bg: '#16a34a', text: '#ffffff', stroke: '#15803d' },
  7: { bg: '#f97316', text: '#ffffff', stroke: '#ea580c' },
  8: { bg: '#f472b6', text: '#ffffff', stroke: '#ec4899' },
};
const WAKU_HEX_FALLBACK = { bg: '#e5e7eb', text: '#111827', stroke: '#9ca3af' };

/** 競馬ブック展開分類 → マーカー右下ドット色 */
export const BUCKET_DOT_HEX: Record<string, string> = {
  '逃げ': '#ef4444',
  '好位': '#f97316',
  '中位': '#3b82f6',
  '後方': '#6b7280',
};

/** 左回りの競馬場 (それ以外は右回り扱い。新潟1000m直線=千直はコーナー無しなので近似表示) */
export const LEFT_HANDED_TRACKS = new Set(['東京', '中京', '新潟']);

// ============================================================
// コースジオメトリ (viewBox 1000×480・スタンド=下・右回り基準)
// パス: スタート直線(下辺東側) → 1-2角(左端) → 向こう正面(上辺) → 3-4角(右端) → 最終直線 → ゴール
// ============================================================

const TOP_Y = 95;                              // 向こう正面の中心線
const BOT_Y = 385;                             // 最終直線の中心線
const MID_Y = (TOP_Y + BOT_Y) / 2;
const ARC_R = (BOT_Y - TOP_Y) / 2;             // コーナー半径
const ARC_CX = 790;                            // 3-4角の中心X (右回り基準)
const ARC_CX_L = 210;                          // 1-2角の中心X
const GOAL_X = 260;                            // ゴール線X (右回り基準)
const SEG_HOME = ARC_CX - GOAL_X;              // 最終直線(4角→ゴール)
const SEG_ARC = Math.PI * ARC_R;               // コーナー(半円)
const SEG_BACK = ARC_CX - ARC_CX_L;            // 向こう正面
const SEG_START_MAX = 520;                     // スタート直線の描画上限 (4角ゾーンに食い込まない範囲)
const MAX_GD = SEG_HOME + SEG_ARC + SEG_BACK + SEG_ARC + SEG_START_MAX;

/** 主要地点のゴール残距離 — frameDefs.anchor に使う */
export const COURSE_ANCHORS = {
  goal: 2,
  c4: SEG_HOME + SEG_ARC * 0.12,               // 4角 (出口)
  f3: SEG_HOME + SEG_ARC * 0.35,               // 残り3F (コーナー中盤)
  c3: SEG_HOME + SEG_ARC * 0.88,               // 3角 (入口)
  backMid: SEG_HOME + SEG_ARC + SEG_BACK * 0.5, // 向こう正面中央 (道中)
  c2: SEG_HOME + SEG_ARC + SEG_BACK + SEG_ARC * 0.12,   // 2角
  c1: SEG_HOME + SEG_ARC + SEG_BACK + SEG_ARC * 0.88,   // 1角
  startStraight: SEG_HOME + SEG_ARC + SEG_BACK + SEG_ARC + 250,  // スタンド前発走地点 (将来用)
};

/** 半馬身→path単位 (視認性優先でややデフォルメ) */
export const HALF_LEN = 6;

/** 馬マーカーの表示倍率 (ゲート一列でも重なりにくい小サイズで全コマ統一) */
const MARKER_SCALE = 0.55;

// ============================================================
// コンポーネント
// ============================================================

export default function CourseReplay({
  frameDefs,
  horses,
  mirrored,
  title = '予想隊列図',
  headerNote,
  paceNote,
  legendNote,
  playLabel = '再生',
  ringFrameKeys,
  headerExtra,
}: CourseReplayProps) {
  const [frameIdx, setFrameIdx] = useState(0);       // ボタン選択中のコマ
  const [prog, setProg] = useState(0);               // 連続コマ位置 (rAFが駆動)
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);             // 再生時間の倍率 (2=🐢ゆっくり / 1=普通 / 0.5=速い)
  const [telop, setTelop] = useState<string | null>(null);   // 再生中の区間テロップ
  const progRef = useRef(0);
  const rafRef = useRef(0);
  const speedRef = useRef(1);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { speedRef.current = speed; }, [speed]);

  useEffect(() => () => {
    cancelAnimationFrame(rafRef.current);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  /** prog を target まで easeInOutQuad で補間 — 馬はコース経路に沿って動く */
  const animateTo = useCallback((target: number, done?: () => void) => {
    cancelAnimationFrame(rafRef.current);
    const from = progRef.current;
    const dur = Math.max(400, Math.abs(target - from) * 2600 * speedRef.current);   // ゆっくり=動き(馬ごとの速度差)が読める
    const t0 = performance.now();
    const tick = (now: number) => {
      const u = Math.min(1, (now - t0) / dur);
      const e = u < 0.5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2;
      progRef.current = from + (target - from) * e;
      setProg(progRef.current);
      if (u < 1) rafRef.current = requestAnimationFrame(tick);
      else done?.();
    };
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const stopAnim = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    if (timerRef.current) clearTimeout(timerRef.current);
    setPlaying(false);
    setTelop(null);
  }, []);

  /**
   * 区間テロップ: ia→ib のコマ間で目立った動きを一行にする。
   * 通常区間 = 2番手以上上がった馬 (最大2頭)。ゲート区間 = 隊列形成 (先頭に立った馬)。
   */
  const telopFor = useCallback((ia: number, ib: number): string | null => {
    const a = frameDefs[ia], b = frameDefs[ib];
    const seg = `${a.label}→${b.label}`;
    if (b.gate) {
      // ゲート→発走直後: 出遅れた馬 (直後コマで先頭差がついた馬) を告知
      const slow = horses
        .map(h => ({ num: h.num, f: h.frames[ib] }))
        .filter((x): x is { num: number; f: CourseFramePos } => !!x.f && (x.f.diff ?? 0) >= 2)
        .map(x => toCircleNumber(x.num));
      return slow.length > 0 ? `${a.label}: ${slow.join('')}が出遅れ` : null;
    }
    if (a.gate) {
      const leaders = horses
        .map(h => ({ num: h.num, f: h.frames[ib] }))
        .filter((x): x is { num: number; f: CourseFramePos } => !!x.f)
        .sort((p, q) => p.f.order - q.f.order)
        .slice(0, 2);
      if (leaders.length === 0) return null;
      return `${seg}: ${leaders.map(x => `${toCircleNumber(x.num)}${x.f.order === 1 ? 'が先頭' : ` ${x.f.order}番手`}`).join('・')}`;
    }
    const movers = horses
      .map(h => {
        const fa = h.frames[ia], fb = h.frames[ib];
        if (!fa || !fb) return null;
        return { num: h.num, from: fa.order, to: fb.order, up: fa.order - fb.order };
      })
      .filter((v): v is NonNullable<typeof v> => v !== null && v.up >= 2)
      .sort((p, q) => q.up - p.up)
      .slice(0, 2);
    if (movers.length === 0) return null;
    return `${seg}: ${movers.map(m => `${toCircleNumber(m.num)} ${m.from}位→${m.to}位↑`).join(' ・ ')}`;
  }, [frameDefs, horses]);

  /** ▶再生: inPlay なコマを先頭から順に流す (コマ間ポーズで区間テロップを読ませる) */
  const play = useCallback(() => {
    stopAnim();
    const seq = frameDefs.map((f, i) => (f.inPlay ? i : -1)).filter(i => i >= 0);
    if (seq.length < 2) return;
    setPlaying(true);
    setFrameIdx(seq[0]);
    progRef.current = seq[0];
    setProg(seq[0]);
    const step = (k: number) => {
      timerRef.current = setTimeout(() => {
        setFrameIdx(seq[k]);
        setTelop(telopFor(seq[k - 1], seq[k]));
        animateTo(seq[k], () => {
          if (k < seq.length - 1) step(k + 1);
          else {
            setPlaying(false);
            // 最終区間のテロップは余韻を持たせて消す
            timerRef.current = setTimeout(() => setTelop(null), 1600);
          }
        });
      }, Math.round((k === 1 ? 500 : 1100) * speedRef.current));
    };
    step(1);
  }, [animateTo, stopAnim, telopFor, frameDefs]);

  if (horses.length < 2 || frameDefs.length < 2) return null;

  /** ゴール残距離+内外レーン → SVG座標+進行方向角。内=オーバル中心側 (進行方向右手が中心を向く・右回り基準) */
  const posAt = (goalDist: number, inout: number): { x: number; y: number; ang: number } => {
    const gd = Math.max(2, Math.min(MAX_GD, goalDist));
    let x: number, y: number, tx: number, ty: number;
    if (gd <= SEG_HOME) {
      // 最終直線 (西向き)
      x = GOAL_X + gd; y = BOT_Y; tx = -1; ty = 0;
    } else if (gd <= SEG_HOME + SEG_ARC) {
      // 3-4角 (上=3角入口 → 下=4角出口)
      const th = Math.PI / 2 - (gd - SEG_HOME) / ARC_R;
      x = ARC_CX + ARC_R * Math.cos(th);
      y = MID_Y + ARC_R * Math.sin(th);
      tx = -Math.sin(th); ty = Math.cos(th);
    } else if (gd <= SEG_HOME + SEG_ARC + SEG_BACK) {
      // 向こう正面 (東向き)
      x = ARC_CX - (gd - SEG_HOME - SEG_ARC); y = TOP_Y; tx = 1; ty = 0;
    } else if (gd <= SEG_HOME + SEG_ARC + SEG_BACK + SEG_ARC) {
      // 1-2角 (下=1角入口 → 上=2角出口)
      const a = Math.PI - (gd - SEG_HOME - SEG_ARC - SEG_BACK) / ARC_R;
      const th = Math.PI / 2 + a;
      x = ARC_CX_L + ARC_R * Math.cos(th);
      y = MID_Y + ARC_R * Math.sin(th);
      tx = -Math.sin(th); ty = Math.cos(th);
    } else {
      // スタート直線 (スタンド前東側・西向き)
      x = ARC_CX_L + (gd - SEG_HOME - SEG_ARC - SEG_BACK - SEG_ARC);
      y = BOT_Y; tx = -1; ty = 0;
    }
    const lane = 45 - (Math.min(5, Math.max(1, inout)) - 1) * 22.5;   // 内(1)=+45 → 外(5)=-45 (重なり回避で広め)
    x += -ty * lane;
    y += tx * lane;
    return {
      x: mirrored ? 1000 - x : x,
      y,
      ang: Math.atan2(ty, mirrored ? -tx : tx),   // 伸び流線の向きに使用
    };
  };

  /** コマ欠損時は直近の存在コマへフォールバック */
  const frameOf = (h: CourseHorse, i: number): CourseFramePos | null => {
    if (h.frames[i]) return h.frames[i]!;
    const avail = h.frames.map((f, j) => (f ? j : -1)).filter(j => j >= 0);
    if (avail.length === 0) return null;
    const j = avail.reduce((best, k) => (Math.abs(k - i) < Math.abs(best - i) ? k : best), avail[0]);
    return h.frames[j]!;
  };
  const dval = (f: CourseFramePos) => f.diff ?? (f.order - 1) * 2;  // diff欠損は順位から概算

  // 連続コマ位置 prog での各馬の (先頭差, 内外) — コマ間は線形補間
  const i0 = Math.max(0, Math.min(frameDefs.length - 2, Math.floor(prog)));
  const u = Math.max(0, Math.min(1, prog - i0));
  const lerp = (a: number, b: number) => a + (b - a) * u;
  const anchor = lerp(frameDefs[i0].anchor, frameDefs[i0 + 1].anchor);

  // アニメーション進行中か (静止コマ表示中は流線を消す)
  const moving = Math.abs(prog - Math.round(prog)) > 0.02;
  // 伸び流線はレース進行(inPlay同士)の区間のみ (予想⇄MLの意見割れ切替では出さない)
  const racingSegment = !!frameDefs[i0].inPlay && !!frameDefs[i0 + 1].inPlay;
  const showRing = !!ringFrameKeys?.includes(frameDefs[frameIdx].key);
  // ゲート度 (0〜1): ゲートコマでは前後ずらしを無効化して「横一列」を保つ (発走後は補間で通常挙動へ)
  const gateW = lerp(frameDefs[i0].gate ? 1 : 0, frameDefs[i0 + 1].gate ? 1 : 0);

  const dups = new Map<string, number>();
  const rendered = horses
    .map(h => {
      const fa = frameOf(h, i0);
      const fb = frameOf(h, i0 + 1);
      if (!fa || !fb) return null;
      const diff = lerp(dval(fa), dval(fb));
      const inout = lerp(fa.inout ?? 3, fb.inout ?? 3);
      const cur = frameOf(h, frameIdx)!;
      const closing = dval(fa) - dval(fb);   // 正=この区間で前との差を詰めている(伸び)・半馬身
      // 同一位置(差×内外)の馬は縦列(前後)にずらす (ゲートでは無効=同じ線上に並べる)
      const key = `${Math.round(diff * 2)}:${Math.round(inout)}`;
      const dup = dups.get(key) ?? 0;
      dups.set(key, dup + 1);
      const { x, y, ang } = posAt(anchor + diff * HALF_LEN + dup * 13 * (1 - gateW), inout);
      return { h, x, y, ang, cur, closing, ghost: !h.frames[frameIdx] };
    })
    .filter((r): r is NonNullable<typeof r> => r !== null);

  const gx = mirrored ? 1000 - GOAL_X : GOAL_X;
  const cornerX34 = mirrored ? 60 : 940;
  const cornerX12 = mirrored ? 940 : 60;
  const hasBuckets = horses.some(h => h.bucket);
  const canPlay = frameDefs.filter(f => f.inPlay).length >= 2;

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="text-xs font-medium text-gray-600 dark:text-gray-400">
          🎬 {title}
          {headerNote && <span className="ml-2 font-normal text-gray-400">{headerNote}</span>}
          {paceNote && <span className="ml-2 font-normal text-gray-400">{paceNote}</span>}
          {headerExtra}
        </div>
        <div className="flex items-center gap-1 flex-wrap">
          {frameDefs.map((f, i) => f.hidden ? null : (
            <button
              key={f.key}
              onClick={() => { stopAnim(); setFrameIdx(i); animateTo(i); }}
              title={f.buttonTitle}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                frameIdx === i
                  ? f.accent === 'ml' ? 'bg-violet-600 text-white'
                    : f.accent === 'pred' ? 'bg-teal-600 text-white'
                    : 'bg-blue-600 text-white'
                  : f.accent === 'ml'
                    ? 'bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 hover:bg-violet-100 dark:hover:bg-violet-900/50'
                    : f.accent === 'pred'
                      ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 hover:bg-teal-100 dark:hover:bg-teal-900/50'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
          {canPlay && (
            <>
              <span className="ml-1 inline-flex rounded overflow-hidden border border-gray-200 dark:border-gray-700">
                {([
                  { mult: 2, label: '🐢', title: 'ゆっくり (×2)' },
                  { mult: 1, label: '▶', title: '普通' },
                  { mult: 0.5, label: '⏩', title: '速い (×0.5)' },
                ] as const).map(s => (
                  <button
                    key={s.mult}
                    onClick={() => setSpeed(s.mult)}
                    title={`再生速度: ${s.title}`}
                    className={`px-1.5 py-1 text-xs transition-colors ${
                      speed === s.mult
                        ? 'bg-gray-600 dark:bg-gray-500 text-white'
                        : 'bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </span>
              <button
                onClick={play}
                disabled={playing}
                className="px-2.5 py-1 rounded text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 inline-flex items-center gap-1"
                title="コース経路に沿ってコマ送り再生"
              >
                <Play className="w-3 h-3" /> {playLabel}
              </button>
            </>
          )}
        </div>
      </div>

      {/* コース模式図 (SVG・スタンド=下・回り反映) */}
      <svg viewBox="0 0 1000 480" className="w-full h-auto rounded-lg border bg-emerald-50/50 dark:bg-gray-900">
        {/* 馬場 (外ラチ〜内ラチのリング・中心線±50) */}
        <rect x={15} y={45} width={970} height={390} rx={195}
          className="fill-emerald-200/70 dark:fill-emerald-800/40 stroke-emerald-400/70" strokeWidth={2} />
        <rect x={115} y={145} width={770} height={190} rx={95}
          className="fill-emerald-50 dark:fill-gray-900 stroke-emerald-400/70" strokeWidth={2} />

        {/* ゴール線 */}
        <line x1={gx} y1={BOT_Y - 56} x2={gx} y2={BOT_Y + 56} className="stroke-red-500" strokeWidth={3} strokeDasharray="7 4" />
        <text x={gx} y={BOT_Y + 74} textAnchor="middle" fontSize={13} fontWeight={700} className="fill-red-500">GOAL</text>

        {/* ガイドラベル */}
        <text x={500} y={80} textAnchor="middle" fontSize={12} className="fill-gray-400">向こう正面 (道中)</text>
        <text x={cornerX34} y={92} textAnchor="middle" fontSize={12} className="fill-gray-400">3角</text>
        <text x={cornerX34} y={402} textAnchor="middle" fontSize={12} className="fill-gray-400">4角</text>
        <text x={cornerX12} y={92} textAnchor="middle" fontSize={12} className="fill-gray-400">2角</text>
        <text x={cornerX12} y={402} textAnchor="middle" fontSize={12} className="fill-gray-400">1角</text>
        <text x={500} y={245} textAnchor="middle" fontSize={12} className="fill-gray-400">{mirrored ? '左回り' : '右回り'}</text>
        <text x={500} y={472} textAnchor="middle" fontSize={12} className="fill-gray-400">スタンド前 (最終直線)</text>

        {/* 区間テロップ (再生中・インフィールド中央) */}
        {telop && (
          <text x={500} y={290} textAnchor="middle" fontSize={16} fontWeight={700}
            className="fill-amber-600 dark:fill-amber-400" style={{ paintOrder: 'stroke' }}>
            {telop}
          </text>
        )}

        {/* 馬マーカー (rAF がコース経路に沿って駆動) */}
        {rendered.map(({ h, x, y, ang, cur, closing, ghost }) => {
          const cap = WAKU_HEX[parseInt(h.waku ?? '', 10)] ?? WAKU_HEX_FALLBACK;
          const lineLen = Math.min(20, 7 + closing * 1.3);
          return (
            <g key={h.num} transform={`translate(${x.toFixed(1)},${y.toFixed(1)}) scale(${MARKER_SCALE})`} opacity={ghost ? 0.45 : 1}>
              <title>{`${toCircleNumber(h.num)} ${h.name}${h.bucket ? ` / 競馬ブック: ${h.bucket}` : ''} / ${frameDefs[frameIdx].label}: ${cur.posLabel ?? `${cur.order}番手${cur.diff != null && cur.diff > 0 ? ` (先頭差${cur.diff}半馬身)` : ''}`}`}</title>
              {/* 伸び流線 (差を詰めている馬・再生中のみ・進行方向の逆に流す) */}
              {moving && racingSegment && closing >= 3 && (
                <g transform={`rotate(${((ang * 180) / Math.PI).toFixed(1)})`} opacity={Math.min(0.85, closing / 8)}>
                  <line x1={-11} y1={-3.5} x2={-11 - lineLen} y2={-3.5} stroke="#10b981" strokeWidth={2} strokeLinecap="round" />
                  <line x1={-12} y1={3.5} x2={-12 - lineLen * 0.7} y2={3.5} stroke="#10b981" strokeWidth={2} strokeLinecap="round" />
                </g>
              )}
              {/* 答え合わせリング (hit=緑/miss=赤破線) */}
              {showRing && h.ring && (
                <circle r={13} fill="none"
                  stroke={h.ring === 'hit' ? '#22c55e' : '#ef4444'}
                  strokeWidth={2.2}
                  strokeDasharray={h.ring === 'miss' ? '4 3' : undefined} />
              )}
              <circle r={9.5} fill={cap.bg} stroke={cap.stroke} strokeWidth={1.4} />
              <text y={3.6} textAnchor="middle" fontSize={10.5} fontWeight={700} fill={cap.text}>{h.num}</text>
              {h.bucket && (
                <circle cx={7.5} cy={7.5} r={3.4} fill={BUCKET_DOT_HEX[h.bucket]} stroke="#ffffff" strokeWidth={1} />
              )}
            </g>
          );
        })}
      </svg>

      {/* 凡例 */}
      <div className="mt-1.5 flex items-center gap-3 flex-wrap text-[10px] text-gray-500 dark:text-gray-400">
        {hasBuckets && (
          <>
            <span>競馬ブック分類:</span>
            {Object.entries(BUCKET_DOT_HEX).map(([b, hex]) => (
              <span key={b} className="inline-flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: hex }} />{b}
              </span>
            ))}
          </>
        )}
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-4 border-t-2 rounded" style={{ borderColor: '#10b981' }} />再生中の緑線=伸び(差を詰めている馬)
        </span>
        {ringFrameKeys && (
          <span className="inline-flex items-center gap-2">
            <span className="inline-flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full border-2" style={{ borderColor: '#22c55e' }} />予想的中(±1番手)
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full border-2 border-dashed" style={{ borderColor: '#ef4444' }} />大きく外れ(5番手以上)
            </span>
          </span>
        )}
        {legendNote && <span className="ml-auto">{legendNote}</span>}
      </div>
    </div>
  );
}
