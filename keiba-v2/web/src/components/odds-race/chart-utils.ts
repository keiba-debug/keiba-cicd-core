/**
 * オッズ時系列 → ローソク足 / ラインシリーズ 変換ユーティリティ
 *
 * /api/odds/ji-timeseries の snapshots を lightweight-charts 形式に変換する。
 *
 * snapshot 例: { time: "04241835", timeLabel: "18:35", odds: { "1": 19.0, ... } }
 * - time は MMDDHHMM (8桁) 形式
 * - raceId(16桁) の YYYY と組み合わせて UTCTimestamp(秒) を生成
 */

import type { UTCTimestamp, CandlestickData, LineData } from 'lightweight-charts';

export interface OddsSnapshot {
  time: string;
  timeLabel: string;
  odds: Record<string, number>;
}

export type Bucket = '5m' | '15m' | '30m' | '1h';

const BUCKET_SECONDS: Record<Bucket, number> = {
  '5m': 5 * 60,
  '15m': 15 * 60,
  '30m': 30 * 60,
  '1h': 60 * 60,
};

/**
 * snapshot.time (MMDDHHMM) + raceId 先頭4桁 → UTCTimestamp (秒)
 *
 * 例: time="04241835" + raceId="2026..." → 2026-04-24 18:35 JST
 *
 * 注意: 日本標準時の素朴な秒変換。lightweight-charts は UTCTimestamp 型だが
 * X軸表示は localization で JST 時刻として表示される（ライブラリの文字列フォーマットに任せる）。
 * 過去同月跨ぎ問題（snapshot に翌日分があるなど）は raceId の YYYY を共通として扱う。
 */
export function parseSnapshotTime(snapshotTime: string, raceIdYear: string): UTCTimestamp {
  if (snapshotTime.length !== 8) return 0 as UTCTimestamp;
  const mm = parseInt(snapshotTime.substring(0, 2), 10);
  const dd = parseInt(snapshotTime.substring(2, 4), 10);
  const hh = parseInt(snapshotTime.substring(4, 6), 10);
  const mi = parseInt(snapshotTime.substring(6, 8), 10);
  const yyyy = parseInt(raceIdYear, 10);
  // JST と仮定して Date.UTC で秒換算（表示はlightweight-chartsのlocaleに任せる）
  const ms = Date.UTC(yyyy, mm - 1, dd, hh, mi, 0);
  return Math.floor(ms / 1000) as UTCTimestamp;
}

/**
 * 1馬分のスナップショット列 → ライン用シリーズ
 */
export function toLineSeries(
  snapshots: OddsSnapshot[],
  umaban: string,
  raceIdYear: string
): LineData<UTCTimestamp>[] {
  const ub2 = umaban.replace(/^0+/, '');
  const points: LineData<UTCTimestamp>[] = [];
  const seen = new Set<UTCTimestamp>();
  for (const s of snapshots) {
    const v = s.odds[umaban] ?? s.odds[ub2];
    if (v == null || v <= 0) continue;
    const t = parseSnapshotTime(s.time, raceIdYear);
    if (t === 0 || seen.has(t)) continue; // 重複時刻はスキップ（lightweight-chartsは昇順ユニーク要求）
    seen.add(t);
    points.push({ time: t, value: v });
  }
  // 念のため時刻昇順
  return points.sort((a, b) => (a.time as number) - (b.time as number));
}

/**
 * 1馬分のスナップショット列 → ローソク足シリーズ
 *
 * 各バケットの範囲内に含まれる snapshots から OHLC を計算:
 *   open  = バケット内最初の snapshot のオッズ
 *   high  = 最大値
 *   low   = 最小値
 *   close = バケット内最後の snapshot のオッズ
 * 値が無い馬は当該バケットを生成しない。
 */
export function toCandleSeries(
  snapshots: OddsSnapshot[],
  umaban: string,
  raceIdYear: string,
  bucket: Bucket
): CandlestickData<UTCTimestamp>[] {
  const ub2 = umaban.replace(/^0+/, '');
  const bucketSec = BUCKET_SECONDS[bucket];

  // バケット境界 → snapshots
  const buckets = new Map<UTCTimestamp, { ts: UTCTimestamp; values: number[] }>();
  for (const s of snapshots) {
    const v = s.odds[umaban] ?? s.odds[ub2];
    if (v == null || v <= 0) continue;
    const t = parseSnapshotTime(s.time, raceIdYear);
    if (t === 0) continue;
    const bucketStart = (Math.floor((t as number) / bucketSec) * bucketSec) as UTCTimestamp;
    const b = buckets.get(bucketStart);
    if (b) {
      b.values.push(v);
    } else {
      buckets.set(bucketStart, { ts: bucketStart, values: [v] });
    }
  }

  const result: CandlestickData<UTCTimestamp>[] = [];
  for (const { ts, values } of buckets.values()) {
    if (values.length === 0) continue;
    const open = values[0];
    const close = values[values.length - 1];
    let high = values[0];
    let low = values[0];
    for (const v of values) {
      if (v > high) high = v;
      if (v < low) low = v;
    }
    result.push({ time: ts, open, high, low, close });
  }
  return result.sort((a, b) => (a.time as number) - (b.time as number));
}

/** 急騰マーカー用: snapshot 列から 「直前1区間で-15%以上下落」した時刻を抽出 */
export function detectSurgeMarkers(
  snapshots: OddsSnapshot[],
  umaban: string,
  raceIdYear: string,
  thresholdPercent = -15
): { time: UTCTimestamp; changePercent: number }[] {
  const series = toLineSeries(snapshots, umaban, raceIdYear);
  const markers: { time: UTCTimestamp; changePercent: number }[] = [];
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].value;
    const cur = series[i].value;
    if (prev > 0) {
      const pct = ((cur - prev) / prev) * 100;
      if (pct <= thresholdPercent) {
        markers.push({ time: series[i].time, changePercent: pct });
      }
    }
  }
  return markers;
}

/**
 * 馬番別の代表色（人気順 or 馬番順で循環）
 * lightweight-charts に series ごと色を割り当てる
 */
const COLOR_PALETTE = [
  '#ef4444', // red-500
  '#3b82f6', // blue-500
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#06b6d4', // cyan-500
  '#84cc16', // lime-500
  '#f97316', // orange-500
  '#6366f1', // indigo-500
  '#14b8a6', // teal-500
  '#a855f7', // purple-500
  '#eab308', // yellow-500
  '#22c55e', // green-500
  '#0ea5e9', // sky-500
  '#dc2626', // red-600
  '#2563eb', // blue-600
  '#059669', // emerald-600
];

export function colorForUmaban(_umaban: string, index: number): string {
  // 現状は index ベースで循環。将来「枠番固定色」「人気固定色」に変えたければ umaban を活用
  return COLOR_PALETTE[index % COLOR_PALETTE.length];
}
