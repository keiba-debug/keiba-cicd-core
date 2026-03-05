/**
 * JRDB KAA（開催情報）インデックスリーダー
 *
 * レース後のトラックバイアス情報（内/外有利、差値）を提供する。
 * data3/indexes/jrdb_kaa_index.json をメモリキャッシュして読み込む。
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '../config';

const KAA_INDEX_FILE = path.join(DATA3_ROOT, 'indexes', 'jrdb_kaa_index.json');

export interface TrackBias {
  weatherCode: number;        // 1=晴,2=曇,3=雨,4=小雨,5=雪,6=小雪
  turfConditionCode: number;  // 1=良,2=稍重,3=重,4=不良
  dirtConditionCode: number;
  turfSa: number;             // 差値（マイナス=内有利）
  dirtSa: number;
  turfInner: number;          // 1=有利,2=普通,3=不利
  turfMiddle: number;
  turfOuter: number;
  dirtInner: number;
  dirtMiddle: number;
  dirtOuter: number;
  straightInnermost: number;
  straightInner: number;
  straightMiddle: number;
  straightOuter: number;
  straightOutermost: number;
  dataKubun: number;          // 4=確定
}

// メモリキャッシュ
let kaaCache: Record<string, Record<string, unknown>> | null = null;

function loadKaaIndex(): Record<string, Record<string, unknown>> {
  if (kaaCache) return kaaCache;
  try {
    if (!fs.existsSync(KAA_INDEX_FILE)) return {};
    kaaCache = JSON.parse(fs.readFileSync(KAA_INDEX_FILE, 'utf-8'));
    return kaaCache!;
  } catch {
    return {};
  }
}

/**
 * 指定会場・日付のトラックバイアスを取得
 * @param venueCode JRA-VAN 場所コード (2桁: "01"〜"10")
 * @param date 日付 (YYYY-MM-DD)
 */
export function getTrackBias(venueCode: string, date: string): TrackBias | null {
  const index = loadKaaIndex();
  const key = `${venueCode}_${date}`;
  const entry = index[key];
  if (!entry) return null;

  return {
    weatherCode: (entry.weather_code as number) ?? 0,
    turfConditionCode: (entry.turf_condition_code as number) ?? 0,
    dirtConditionCode: (entry.dirt_condition_code as number) ?? 0,
    turfSa: (entry.turf_sa as number) ?? 0,
    dirtSa: (entry.dirt_sa as number) ?? 0,
    turfInner: (entry.turf_inner as number) ?? 2,
    turfMiddle: (entry.turf_middle as number) ?? 2,
    turfOuter: (entry.turf_outer as number) ?? 2,
    dirtInner: (entry.dirt_inner as number) ?? 2,
    dirtMiddle: (entry.dirt_middle as number) ?? 2,
    dirtOuter: (entry.dirt_outer as number) ?? 2,
    straightInnermost: (entry.straight_innermost as number) ?? 0,
    straightInner: (entry.straight_inner as number) ?? 0,
    straightMiddle: (entry.straight_middle as number) ?? 0,
    straightOuter: (entry.straight_outer as number) ?? 0,
    straightOutermost: (entry.straight_outermost as number) ?? 0,
    dataKubun: (entry.data_kubun as number) ?? 0,
  };
}
