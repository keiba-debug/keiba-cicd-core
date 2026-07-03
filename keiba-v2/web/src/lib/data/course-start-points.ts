/**
 * コース別発走地点データ (リプレイv2続編 2.5 / 2026-07-03)
 *
 * 出典: `C:/KEIBA-CICD/競馬場コースデータ/発走地点_JRA全10場.md`
 *   (馬ノスケ『競馬場コース事典2』高低断面図の区間帯ラベル+本文記述+幾何検算・ふくだ作成)
 * JRA全10場・全コースの「初角 / 初角までの実距離(m) / 周長(m)」。
 * CourseReplay の startAnchorFor() がこの3値から模式図上の発走anchorを計算する。
 *
 * 内外回りが同距離で両方あるコースは現行番組の主流側を採用:
 *   京都芝1400/1600 → 外 (内外で発走位置はほぼ同一のため影響軽微)
 *   新潟芝2000 → 外 (内2000=スタンド前発走は現行ほぼ未使用)
 * 新潟芝1000(千直)はコーナー無しの専用レイアウト対応まで対象外 (リプレイ自体が通過順位無しで非表示)。
 */

export interface CourseStartPoint {
  /** スタート後最初のコーナー (1〜4角) */
  firstCorner: 1 | 2 | 3 | 4;
  /** 初角までの実距離 (m・Aコース値) */
  distToCornerM: number;
  /** 使用トラックの1周距離 (m・Aコース値) */
  lapM: number;
}

/** key: `場名_芝|ダ_距離` */
const COURSE_STARTS: Record<string, CourseStartPoint> = {
  // 札幌 (芝A周1640.9 / ダ周1487.0)
  '札幌_芝_1200': { firstCorner: 3, distToCornerM: 405.5, lapM: 1640.9 },
  '札幌_芝_1500': { firstCorner: 2, distToCornerM: 177.7, lapM: 1640.9 },
  '札幌_芝_1800': { firstCorner: 1, distToCornerM: 185.1, lapM: 1640.9 },
  '札幌_芝_2000': { firstCorner: 1, distToCornerM: 385.1, lapM: 1640.9 },
  '札幌_芝_2600': { firstCorner: 3, distToCornerM: 164.6, lapM: 1640.9 },
  '札幌_ダ_1000': { firstCorner: 3, distToCornerM: 284.3, lapM: 1487.0 },
  '札幌_ダ_1700': { firstCorner: 1, distToCornerM: 240.8, lapM: 1487.0 },
  '札幌_ダ_2400': { firstCorner: 3, distToCornerM: 197.3, lapM: 1487.0 },
  // 函館 (芝A周1626.6 / ダ周1475.8)
  '函館_芝_1200': { firstCorner: 3, distToCornerM: 489.1, lapM: 1626.6 },
  '函館_芝_1800': { firstCorner: 1, distToCornerM: 275.7, lapM: 1626.6 },
  '函館_芝_2000': { firstCorner: 1, distToCornerM: 475.7, lapM: 1626.6 },
  '函館_芝_2600': { firstCorner: 3, distToCornerM: 262.4, lapM: 1626.6 },
  '函館_ダ_1000': { firstCorner: 3, distToCornerM: 366.5, lapM: 1475.8 },
  '函館_ダ_1700': { firstCorner: 1, distToCornerM: 328.5, lapM: 1475.8 },
  '函館_ダ_2400': { firstCorner: 3, distToCornerM: 290.6, lapM: 1475.8 },
  // 福島 (芝A周1600.0 / ダ周1444.6)
  '福島_芝_1200': { firstCorner: 3, distToCornerM: 411.7, lapM: 1600.0 },
  '福島_芝_1800': { firstCorner: 1, distToCornerM: 305.3, lapM: 1600.0 },
  '福島_芝_2000': { firstCorner: 1, distToCornerM: 505.3, lapM: 1600.0 },
  '福島_芝_2600': { firstCorner: 3, distToCornerM: 211.7, lapM: 1600.0 },
  '福島_ダ_1150': { firstCorner: 3, distToCornerM: 492.6, lapM: 1444.6 },
  '福島_ダ_1700': { firstCorner: 1, distToCornerM: 362.4, lapM: 1444.6 },
  '福島_ダ_2400': { firstCorner: 3, distToCornerM: 298.2, lapM: 1444.6 },
  // 新潟 (芝内A周1623.1 / 芝外A周2223.0 / ダ周1472.5) ※芝1000千直は対象外
  '新潟_芝_1200': { firstCorner: 3, distToCornerM: 447.9, lapM: 1623.1 },
  '新潟_芝_1400': { firstCorner: 3, distToCornerM: 647.9, lapM: 1623.1 },
  '新潟_芝_1600': { firstCorner: 3, distToCornerM: 547.9, lapM: 2223.0 },
  '新潟_芝_1800': { firstCorner: 3, distToCornerM: 747.9, lapM: 2223.0 },
  '新潟_芝_2000': { firstCorner: 3, distToCornerM: 947.9, lapM: 2223.0 },   // 外を採用 (内=スタンド前436.4mは現行ほぼ未使用)
  '新潟_芝_2200': { firstCorner: 1, distToCornerM: 636.4, lapM: 1623.1 },
  '新潟_芝_2400': { firstCorner: 1, distToCornerM: 836.4, lapM: 1623.1 },
  '新潟_ダ_1200': { firstCorner: 3, distToCornerM: 524.9, lapM: 1472.5 },
  '新潟_ダ_1800': { firstCorner: 1, distToCornerM: 388.7, lapM: 1472.5 },
  '新潟_ダ_2500': { firstCorner: 3, distToCornerM: 352.5, lapM: 1472.5 },
  // 東京 (芝A周2083.1 / ダ周1899.0)
  '東京_芝_1400': { firstCorner: 3, distToCornerM: 342.7, lapM: 2083.1 },
  '東京_芝_1600': { firstCorner: 3, distToCornerM: 542.7, lapM: 2083.1 },
  '東京_芝_1800': { firstCorner: 2, distToCornerM: 156.6, lapM: 2083.1 },
  '東京_芝_2000': { firstCorner: 2, distToCornerM: 126.3, lapM: 2083.1 },
  '東京_芝_2300': { firstCorner: 1, distToCornerM: 249.6, lapM: 2083.1 },
  '東京_芝_2400': { firstCorner: 1, distToCornerM: 346.6, lapM: 2083.1 },
  '東京_芝_2500': { firstCorner: 1, distToCornerM: 449.6, lapM: 2083.1 },
  '東京_芝_3400': { firstCorner: 3, distToCornerM: 259.6, lapM: 2083.1 },
  '東京_ダ_1300': { firstCorner: 3, distToCornerM: 342.0, lapM: 1899.0 },
  '東京_ダ_1400': { firstCorner: 3, distToCornerM: 442.0, lapM: 1899.0 },
  '東京_ダ_1600': { firstCorner: 3, distToCornerM: 642.0, lapM: 1899.0 },
  '東京_ダ_2100': { firstCorner: 1, distToCornerM: 236.2, lapM: 1899.0 },
  // 中山 (芝内A周1667.1 / 芝外A周1839.7 / ダ周1493.0)
  '中山_芝_1200': { firstCorner: 3, distToCornerM: 275.1, lapM: 1839.7 },
  '中山_芝_1600': { firstCorner: 2, distToCornerM: 239.8, lapM: 1839.7 },
  '中山_芝_1800': { firstCorner: 1, distToCornerM: 204.9, lapM: 1667.1 },
  '中山_芝_2000': { firstCorner: 1, distToCornerM: 404.9, lapM: 1667.1 },
  '中山_芝_2200': { firstCorner: 1, distToCornerM: 432.3, lapM: 1839.7 },
  '中山_芝_2500': { firstCorner: 4, distToCornerM: 193.0, lapM: 1839.7 },
  '中山_芝_3600': { firstCorner: 1, distToCornerM: 337.7, lapM: 1667.1 },
  '中山_ダ_1200': { firstCorner: 3, distToCornerM: 502.6, lapM: 1493.0 },
  '中山_ダ_1800': { firstCorner: 1, distToCornerM: 375.0, lapM: 1493.0 },
  '中山_ダ_2400': { firstCorner: 3, distToCornerM: 209.6, lapM: 1493.0 },
  '中山_ダ_2500': { firstCorner: 3, distToCornerM: 309.6, lapM: 1493.0 },
  // 中京 (芝A周1705.9 / ダ周1530.0)
  '中京_芝_1200': { firstCorner: 3, distToCornerM: 315.5, lapM: 1705.9 },
  '中京_芝_1400': { firstCorner: 3, distToCornerM: 515.5, lapM: 1705.9 },
  '中京_芝_1600': { firstCorner: 2, distToCornerM: 199.9, lapM: 1705.9 },
  '中京_芝_2000': { firstCorner: 1, distToCornerM: 314.1, lapM: 1705.9 },
  '中京_芝_2200': { firstCorner: 1, distToCornerM: 514.1, lapM: 1705.9 },
  '中京_ダ_1200': { firstCorner: 3, distToCornerM: 407.7, lapM: 1530.0 },
  '中京_ダ_1400': { firstCorner: 3, distToCornerM: 607.7, lapM: 1530.0 },
  '中京_ダ_1800': { firstCorner: 1, distToCornerM: 291.8, lapM: 1530.0 },
  '中京_ダ_1900': { firstCorner: 1, distToCornerM: 391.8, lapM: 1530.0 },
  // 京都 (芝内A周1782.8 / 芝外A周1894.3 / ダ周1607.6)
  '京都_芝_1200': { firstCorner: 3, distToCornerM: 316.2, lapM: 1782.8 },
  '京都_芝_1400': { firstCorner: 3, distToCornerM: 511.7, lapM: 1894.3 },   // 外を採用 (内516.2/1782.8とほぼ同位置)
  '京都_芝_1600': { firstCorner: 3, distToCornerM: 711.7, lapM: 1894.3 },   // 外を採用 (内716.2/1782.8とほぼ同位置)
  '京都_芝_1800': { firstCorner: 3, distToCornerM: 911.7, lapM: 1894.3 },
  '京都_芝_2000': { firstCorner: 1, distToCornerM: 308.7, lapM: 1782.8 },
  '京都_芝_2200': { firstCorner: 1, distToCornerM: 397.3, lapM: 1894.3 },
  '京都_芝_2400': { firstCorner: 1, distToCornerM: 597.3, lapM: 1894.3 },
  '京都_芝_3000': { firstCorner: 3, distToCornerM: 217.4, lapM: 1894.3 },
  '京都_芝_3200': { firstCorner: 3, distToCornerM: 417.4, lapM: 1894.3 },
  '京都_ダ_1200': { firstCorner: 3, distToCornerM: 409.6, lapM: 1607.6 },
  '京都_ダ_1400': { firstCorner: 3, distToCornerM: 609.6, lapM: 1607.6 },
  '京都_ダ_1800': { firstCorner: 1, distToCornerM: 285.8, lapM: 1607.6 },
  '京都_ダ_1900': { firstCorner: 1, distToCornerM: 385.8, lapM: 1607.6 },
  // 阪神 (芝内A周1689.0 / 芝外A周2089.0 / ダ周1517.6)
  '阪神_芝_1200': { firstCorner: 3, distToCornerM: 258.2, lapM: 1689.0 },
  '阪神_芝_1400': { firstCorner: 3, distToCornerM: 458.2, lapM: 1689.0 },
  '阪神_芝_1600': { firstCorner: 3, distToCornerM: 444.4, lapM: 2089.0 },
  '阪神_芝_1800': { firstCorner: 3, distToCornerM: 644.4, lapM: 2089.0 },
  '阪神_芝_2000': { firstCorner: 1, distToCornerM: 330.5, lapM: 1689.0 },
  '阪神_芝_2200': { firstCorner: 1, distToCornerM: 530.5, lapM: 1689.0 },
  '阪神_芝_2400': { firstCorner: 1, distToCornerM: 330.5, lapM: 2089.0 },
  '阪神_芝_2600': { firstCorner: 1, distToCornerM: 530.5, lapM: 2089.0 },
  '阪神_芝_3000': { firstCorner: 3, distToCornerM: 369.2, lapM: 1689.0 },
  '阪神_ダ_1200': { firstCorner: 3, distToCornerM: 343.6, lapM: 1517.6 },
  '阪神_ダ_1400': { firstCorner: 3, distToCornerM: 543.6, lapM: 1517.6 },
  '阪神_ダ_1800': { firstCorner: 1, distToCornerM: 298.2, lapM: 1517.6 },
  '阪神_ダ_2000': { firstCorner: 1, distToCornerM: 498.2, lapM: 1517.6 },
  // 小倉 (芝A周1615.1 / ダ周1445.4)
  '小倉_芝_1200': { firstCorner: 3, distToCornerM: 479.0, lapM: 1615.1 },
  '小倉_芝_1800': { firstCorner: 1, distToCornerM: 271.5, lapM: 1615.1 },
  '小倉_芝_2000': { firstCorner: 1, distToCornerM: 471.5, lapM: 1615.1 },
  '小倉_芝_2600': { firstCorner: 3, distToCornerM: 263.9, lapM: 1615.1 },
  '小倉_ダ_1000': { firstCorner: 3, distToCornerM: 245.5, lapM: 1445.4 },
  '小倉_ダ_1700': { firstCorner: 1, distToCornerM: 342.0, lapM: 1445.4 },
  '小倉_ダ_2400': { firstCorner: 3, distToCornerM: 320.1, lapM: 1445.4 },
};

/** track表記ゆれ ('芝'/'ダ'/'ダート'/'turf'/'dirt') → キー用 '芝'|'ダ' */
function normalizeTrackType(t: string): string | null {
  if (t.startsWith('芝') || t === 'turf') return '芝';
  if (t.startsWith('ダ') || t === 'dirt') return 'ダ';
  return null;   // 障害等は対象外
}

/** 場名×トラック種別×距離 → 発走地点。データ無し (障害/千直/地方等) は null */
export function courseStartOf(
  venue: string | undefined,
  trackType: string | undefined,
  distance: number | undefined,
): CourseStartPoint | null {
  if (!venue || !trackType || !distance) return null;
  const t = normalizeTrackType(trackType);
  if (!t) return null;
  return COURSE_STARTS[`${venue}_${t}_${distance}`] ?? null;
}
