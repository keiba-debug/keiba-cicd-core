'use client';

import { useMemo, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';

// ── 型定義 ──

export interface HorseIDMData {
  horseId: string;     // ketto_num — 馬詳細リンク用
  horseName: string;
  horseNumber: number; // 馬番
  waku: number;
  birthDate: string; // YYYYMMDD
  idmPoints: Array<{
    ageMonths: number;
    dateNum: number; // エポック日 (2000-01-01からの日数) — X軸用
    idm: number | null;
    date: string;
    track: string;
    raceName: string;
    finishPosition: string;
  }>;
  latestIdm: number | null;
  maxIdm: number | null;
  max5Idm: number | null;  // 近5走最高
  avgIdm: number | null;
  avg3: number | null;   // 近3走平均
  avg5: number | null;   // 近5走平均
  raceCount: number;
  trend: 'up' | 'flat' | 'down';
  odds: number | null;         // 単勝オッズ
  arDeviation: number | null;  // AR偏差値
  predProbaP: number | null;   // P% (好走確率)
  predProbaW: number | null;   // W% (勝率)
  marketSignal: string | null; // 市場シグナル
}

// ── 定数 ──

// JRA枠色 (1枠=白→グレー表示, 2=黒, 3=赤, 4=青, 5=黄, 6=緑, 7=橙, 8=桃)
const WAKU_COLORS: Record<number, string> = {
  1: '#9ca3af', // 白枠 → グレーで視認性確保
  2: '#374151', // 黒枠
  3: '#ef4444', // 赤枠
  4: '#3b82f6', // 青枠
  5: '#eab308', // 黄枠
  6: '#22c55e', // 緑枠
  7: '#f97316', // 橙枠
  8: '#ec4899', // 桃枠
};
const WAKU_FALLBACK = '#6b7280';

// 現在の日付（エポック日: 2000-01-01からの日数）
const NOW_DATE = new Date();
const EPOCH_BASE = Date.UTC(2000, 0, 1);
const NOW_DATENUM = Math.round((Date.UTC(NOW_DATE.getFullYear(), NOW_DATE.getMonth(), NOW_DATE.getDate()) - EPOCH_BASE) / 86400000);

// 開始年の選択肢を動的生成（現在年から遡って6年分 + 全期間）
const CURRENT_YEAR = NOW_DATE.getFullYear();
const START_YEAR_OPTIONS: Array<{ year: number | null; label: string }> = [];
for (let y = CURRENT_YEAR; y >= CURRENT_YEAR - 5; y--) {
  START_YEAR_OPTIONS.push({ year: y, label: `${y}~` });
}
START_YEAR_OPTIONS.push({ year: null, label: '全期間' });

const TREND_ICONS: Record<string, { icon: string; color: string }> = {
  up:   { icon: '↑', color: 'text-green-600 dark:text-green-400' },
  flat: { icon: '→', color: 'text-gray-500' },
  down: { icon: '↓', color: 'text-red-500 dark:text-red-400' },
};

// ── ツールチップ ──

interface ComparisonTooltipProps {
  active?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[];
  label?: number;
  horses: HorseIDMData[];
  visibleHorses: Set<number>;
}

function ComparisonTooltip({ active, payload, label, horses, visibleHorses }: ComparisonTooltipProps) {
  if (!active || !payload?.length || label == null) return null;

  // payload からnon-null値を持つエントリを収集
  const entries: Array<{ name: string; num: number; idm: number; color: string }> = [];
  for (const p of payload) {
    if (p.value == null) continue;
    const key = p.dataKey as string;
    const match = key.match(/^idm_(\d+)$/);
    if (!match) continue;
    const num = parseInt(match[1], 10);
    if (!visibleHorses.has(num)) continue;
    const horse = horses.find(h => h.horseNumber === num);
    if (!horse) continue;
    entries.push({ name: horse.horseName, num, idm: p.value, color: p.stroke });
  }

  if (entries.length === 0) return null;

  // IDM降順ソート
  entries.sort((a, b) => b.idm - a.idm);

  return (
    <div className="bg-white dark:bg-gray-800 border rounded-lg shadow-lg px-3 py-2 text-xs max-h-80 overflow-y-auto">
      <div className="font-semibold mb-1.5 text-muted-foreground">
        {formatDateNum(label)}
      </div>
      <div className="space-y-0.5">
        {entries.map(e => (
          <div key={e.num} className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: e.color }}
            />
            <span className="font-medium" style={{ color: e.color }}>
              {e.num}
            </span>
            <span className="truncate max-w-24">{e.name}</span>
            <span className="ml-auto font-bold">{e.idm}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── メインコンポーネント ──

interface IDMComparisonChartProps {
  horses: HorseIDMData[];
  raceName: string;
  winnerIdmStandard?: number | null; // クラス別勝ち馬IDM基準値
  gradeLabel?: string;               // グレード表示ラベル
}

type SortKey = 'horseNumber' | 'latestIdm' | 'maxIdm' | 'max5Idm' | 'avg3' | 'avg5' | 'raceCount' | 'trend' | 'odds' | 'arDeviation' | 'predProbaP' | 'predProbaW';
type ChartTab = 'timeline' | 'range';

// dateNum (エポック日: 2000-01-01からの日数) → 表示ラベル
function formatDateNum(v: number): string {
  const ms = EPOCH_BASE + v * 86400000;
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth() + 1;
  return `${y}/${String(m).padStart(2, '0')}`;
}

export function IDMComparisonChart({ horses, raceName, winnerIdmStandard, gradeLabel }: IDMComparisonChartProps) {
  const [chartTab, setChartTab] = useState<ChartTab>('timeline');
  const [startYear, setStartYear] = useState<number | null>(CURRENT_YEAR - 1); // デフォルト: 前年から
  const [visibleHorses, setVisibleHorses] = useState<Set<number>>(
    () => new Set(horses.map(h => h.horseNumber))
  );
  const [highlightedHorse, setHighlightedHorse] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('horseNumber');
  const [sortDesc, setSortDesc] = useState(false);

  // 全データの時間範囲
  const { globalMin, globalMax } = useMemo(() => {
    let min = Infinity, max = -Infinity;
    for (const h of horses) {
      for (const p of h.idmPoints) {
        if (p.dateNum < min) min = p.dateNum;
        if (p.dateNum > max) max = p.dateNum;
      }
    }
    return { globalMin: min === Infinity ? 0 : min, globalMax: max === -Infinity ? 0 : max };
  }, [horses]);

  // 統一チャートデータ構築（dateNumベース、選択範囲内のみ）
  // startYearからのエポック日を計算 (e.g. 2025 → 2025-01-01からの日数)
  const rangeMin = startYear != null
    ? Math.round((Date.UTC(startYear, 0, 1) - Date.UTC(2000, 0, 1)) / 86400000)
    : -Infinity;
  const chartData = useMemo(() => {
    const dateSet = new Set<number>();
    for (const h of horses) {
      for (const p of h.idmPoints) {
        if (p.dateNum >= rangeMin) dateSet.add(p.dateNum);
      }
    }
    const sortedDates = Array.from(dateSet).sort((a, b) => a - b);

    return sortedDates.map(dn => {
      const point: Record<string, number | null> = { dateNum: dn };
      for (const h of horses) {
        const match = h.idmPoints.find(p => p.dateNum === dn);
        point[`idm_${h.horseNumber}`] = match?.idm ?? null;
      }
      return point;
    });
  }, [horses, rangeMin]);

  const toggleHorse = useCallback((num: number) => {
    setVisibleHorses(prev => {
      const next = new Set(prev);
      if (next.has(num)) {
        next.delete(num);
      } else {
        next.add(num);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setVisibleHorses(new Set(horses.map(h => h.horseNumber)));
  }, [horses]);

  const clearAll = useCallback(() => {
    setVisibleHorses(new Set());
  }, []);

  // X軸設定: 開始=選択年の1/1、終了=現在日+30日
  const yearToEpochDay = (y: number) => Math.round((Date.UTC(y, 0, 1) - EPOCH_BASE) / 86400000);
  const xMin = startYear != null ? yearToEpochDay(startYear) : globalMin - 30;
  const xMax = NOW_DATENUM + 30;

  // ティック: 四半期境界 (1月/4月/7月/10月)
  const ticks: number[] = [];
  const tickStartYear = startYear ?? new Date(EPOCH_BASE + globalMin * 86400000).getUTCFullYear();
  const tickEndYear = NOW_DATE.getUTCFullYear() + 1;
  for (let y = tickStartYear; y <= tickEndYear; y++) {
    for (const m of [0, 3, 6, 9]) { // 1月, 4月, 7月, 10月
      const t = Math.round((Date.UTC(y, m, 1) - EPOCH_BASE) / 86400000);
      if (t >= xMin && t <= xMax) ticks.push(t);
    }
  }

  // 枠色マップ + 同枠2頭目は破線
  const { colorMap, dashMap } = useMemo(() => {
    const cMap: Record<number, string> = {};
    const dMap: Record<number, boolean> = {}; // true = 破線（同枠2頭目）
    const wakuSeen = new Set<number>();
    // 馬番順にソートしてから処理
    const sorted = [...horses].sort((a, b) => a.horseNumber - b.horseNumber);
    for (const h of sorted) {
      cMap[h.horseNumber] = WAKU_COLORS[h.waku] ?? WAKU_FALLBACK;
      dMap[h.horseNumber] = wakuSeen.has(h.waku);
      wakuSeen.add(h.waku);
    }
    return { colorMap: cMap, dashMap: dMap };
  }, [horses]);

  if (horses.length === 0) {
    return <div className="text-center text-muted-foreground py-12">IDMデータがありません</div>;
  }

  return (
    <div className="space-y-4">
      {/* ヘッダー: タブ + コントロール */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          {/* チャートタブ */}
          <div className="flex items-center rounded-md border text-xs">
            <button
              onClick={() => setChartTab('timeline')}
              className={`px-3 py-1.5 rounded-l-md transition-colors ${
                chartTab === 'timeline' ? 'bg-blue-500 text-white' : 'hover:bg-muted'
              }`}
            >
              推移
            </button>
            <button
              onClick={() => setChartTab('range')}
              className={`px-3 py-1.5 rounded-r-md transition-colors ${
                chartTab === 'range' ? 'bg-blue-500 text-white' : 'hover:bg-muted'
              }`}
            >
              レンジ
            </button>
          </div>
          {/* 開始年セレクター（推移タブのみ表示） */}
          {chartTab === 'timeline' && (
            <div className="flex items-center rounded-md border text-xs">
              {START_YEAR_OPTIONS.map((opt, idx) => (
                <button
                  key={opt.year ?? 'all'}
                  onClick={() => setStartYear(opt.year)}
                  className={`px-3 py-1.5 transition-colors ${
                    startYear === opt.year
                      ? 'bg-blue-500 text-white'
                      : 'hover:bg-muted'
                  } ${idx === 0 ? 'rounded-l-md' : ''} ${idx === START_YEAR_OPTIONS.length - 1 ? 'rounded-r-md' : ''}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
          <span className="text-xs text-muted-foreground">{raceName}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <button onClick={selectAll} className="px-2 py-0.5 rounded border hover:bg-muted transition-colors">
            全選択
          </button>
          <button onClick={clearAll} className="px-2 py-0.5 rounded border hover:bg-muted transition-colors">
            全解除
          </button>
        </div>
      </div>

      {/* 凡例 */}
      <div className="flex flex-wrap gap-1.5">
        {horses.map(h => {
          const color = colorMap[h.horseNumber];
          const isDashed = dashMap[h.horseNumber];
          const isVisible = visibleHorses.has(h.horseNumber);
          const isHighlighted = highlightedHorse === h.horseNumber;
          return (
            <button
              key={h.horseNumber}
              onClick={() => toggleHorse(h.horseNumber)}
              onMouseEnter={() => setHighlightedHorse(h.horseNumber)}
              onMouseLeave={() => setHighlightedHorse(null)}
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium border transition-all ${
                !isVisible ? 'opacity-30 line-through' : isHighlighted ? 'ring-2 ring-offset-1' : ''
              }`}
              style={{
                borderColor: color,
                color: isVisible ? color : '#999',
                ...(isHighlighted ? { ringColor: color } : {}),
              }}
            >
              {/* 枠色ライン（実線/破線） */}
              <svg width="16" height="10" className="flex-shrink-0">
                <line
                  x1="0" y1="5" x2="16" y2="5"
                  stroke={isVisible ? color : '#ccc'}
                  strokeWidth="2.5"
                  strokeDasharray={isDashed ? '4 2' : undefined}
                />
              </svg>
              {h.horseNumber} {h.horseName}
              {h.latestIdm != null && (
                <span className="ml-0.5 opacity-70">{h.latestIdm}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* チャート（タブ切替） */}
      {chartTab === 'timeline' ? (
        <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
          <ResponsiveContainer width="100%" height={600}>
            <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 5, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="dateNum"
                type="number"
                domain={[xMin, xMax]}
                ticks={ticks}
                tickFormatter={formatDateNum}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                domain={[30, 80]}
                ticks={[30, 40, 50, 60, 70, 80]}
                tick={{ fontSize: 12 }}
                width={35}
              />
              <ReferenceLine y={50} stroke="#94a3b8" strokeDasharray="4 4" opacity={0.6} />
              {winnerIdmStandard != null && (
                <ReferenceLine
                  y={winnerIdmStandard}
                  stroke="#f59e0b"
                  strokeWidth={2}
                  opacity={0.7}
                  label={{
                    value: `勝馬基準 ${winnerIdmStandard.toFixed(1)}${gradeLabel ? ` (${gradeLabel})` : ''}`,
                    position: 'insideTopRight',
                    fill: '#f59e0b',
                    fontSize: 11,
                    fontWeight: 'bold',
                  }}
                />
              )}
              <Tooltip
                content={
                  <ComparisonTooltip
                    horses={horses}
                    visibleHorses={visibleHorses}
                  />
                }
              />
              {horses.map(h => {
                const color = colorMap[h.horseNumber];
                const isVisible = visibleHorses.has(h.horseNumber);
                const isHighlighted = highlightedHorse === h.horseNumber;
                const isAnyHighlighted = highlightedHorse != null;
                const isDashed = dashMap[h.horseNumber];
                return (
                  <Line
                    key={h.horseNumber}
                    type="linear"
                    dataKey={`idm_${h.horseNumber}`}
                    stroke={color}
                    strokeWidth={isHighlighted ? 3 : 1.5}
                    strokeDasharray={isDashed ? '6 3' : undefined}
                    strokeOpacity={!isVisible ? 0 : (isAnyHighlighted && !isHighlighted) ? 0.15 : 1}
                    dot={isHighlighted ? { r: 4, fill: color, stroke: '#fff', strokeWidth: 1 } : { r: 2, fill: color }}
                    activeDot={isVisible ? { r: 5 } : false}
                    connectNulls
                    isAnimationActive={false}
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <RecentSlopeChart
          horses={horses}
          colorMap={colorMap}
          visibleHorses={visibleHorses}
          highlightedHorse={highlightedHorse}
          onHighlight={setHighlightedHorse}
          winnerIdmStandard={winnerIdmStandard}
          gradeLabel={gradeLabel}
        />
      )}

      {/* サマリーテーブル */}
      <SummaryTable
        horses={horses}
        colorMap={colorMap}
        visibleHorses={visibleHorses}
        highlightedHorse={highlightedHorse}
        sortKey={sortKey}
        sortDesc={sortDesc}
        onSort={(key) => {
          if (sortKey === key) {
            setSortDesc(!sortDesc);
          } else {
            setSortKey(key);
            setSortDesc(key !== 'horseNumber'); // 番号以外はデフォルト降順
          }
        }}
        onToggle={toggleHorse}
        onHighlight={setHighlightedHorse}
      />
    </div>
  );
}

// ── 近5走 IDMレンジチャート（馬別） ──

interface RecentSlopeChartProps {
  horses: HorseIDMData[];
  colorMap: Record<number, string>;
  visibleHorses: Set<number>;
  highlightedHorse: number | null;
  onHighlight: (num: number | null) => void;
  winnerIdmStandard?: number | null;
  gradeLabel?: string;
}

function RecentSlopeChart({
  horses, colorMap, visibleHorses, highlightedHorse, onHighlight,
  winnerIdmStandard, gradeLabel,
}: RecentSlopeChartProps) {
  // 表示馬を近5走最高IDM降順でソート
  const sorted = useMemo(() => {
    return [...horses]
      .filter(h => visibleHorses.has(h.horseNumber) && h.idmPoints.length > 0)
      .sort((a, b) => (b.max5Idm ?? 0) - (a.max5Idm ?? 0));
  }, [horses, visibleHorses]);

  if (sorted.length === 0) return null;

  // データに合わせてY軸範囲を動的計算（10刻み、最低0）
  const allRecentIdms = sorted.flatMap(h =>
    h.idmPoints.slice(-5).map(p => p.idm).filter((v): v is number => v != null)
  );
  const dataMin = allRecentIdms.length > 0 ? Math.min(...allRecentIdms) : 30;
  const Y_MIN = Math.max(0, Math.floor((dataMin - 5) / 10) * 10); // 最小値-5を10刻みに切り下げ
  const Y_MAX = 80;
  const CHART_H = 600; // 推移チャートと同じ高さ
  const toY = (v: number) => CHART_H * (1 - (v - Y_MIN) / (Y_MAX - Y_MIN));
  // Y軸ティック生成（Y_MINからY_MAXまで10刻み）
  const yTicks: number[] = [];
  for (let t = Y_MIN; t <= Y_MAX; t += 10) yTicks.push(t);

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
      <h3 className="text-sm font-semibold mb-3">近5走 IDMレンジ（近5走最高順）</h3>
      <div className="flex">
        {/* Y軸 */}
        <div className="relative flex-shrink-0" style={{ width: 32, height: CHART_H }}>
          {yTicks.map(v => (
            <span
              key={v}
              className="absolute right-1 text-[10px] text-muted-foreground"
              style={{ top: toY(v), transform: 'translateY(-50%)' }}
            >
              {v}
            </span>
          ))}
        </div>
        {/* チャート本体 */}
        <div className="flex-1 relative" style={{ height: CHART_H }}>
          {/* グリッド線 */}
          {yTicks.map(v => (
            <div
              key={v}
              className="absolute w-full border-t"
              style={{
                top: toY(v),
                borderColor: v === 50 ? '#94a3b8' : '#e2e8f0',
                borderStyle: v === 50 ? 'solid' : 'dashed',
                opacity: v === 50 ? 0.5 : 0.3,
              }}
            />
          ))}
          {/* 勝ち馬IDM基準線 */}
          {winnerIdmStandard != null && winnerIdmStandard >= Y_MIN && winnerIdmStandard <= Y_MAX && (
            <>
              <div
                className="absolute w-full border-t-2 z-10 pointer-events-none"
                style={{
                  top: toY(winnerIdmStandard),
                  borderColor: '#f59e0b',
                  borderStyle: 'solid',
                  opacity: 0.7,
                }}
              />
              <div
                className="absolute z-10 text-[10px] font-bold pointer-events-none"
                style={{
                  top: toY(winnerIdmStandard) - 16,
                  right: 4,
                  color: '#f59e0b',
                }}
              >
                勝馬基準 {winnerIdmStandard.toFixed(1)} {gradeLabel ? `(${gradeLabel})` : ''}
              </div>
            </>
          )}
          {/* 馬カラム */}
          <div className="flex h-full">
            {sorted.map(h => {
              const color = colorMap[h.horseNumber];
              const isHl = highlightedHorse === h.horseNumber;
              const isAnyHl = highlightedHorse != null;
              const recentIdms = h.idmPoints
                .slice(-5)
                .map(p => p.idm)
                .filter((v): v is number => v != null);
              if (recentIdms.length === 0) return null;
              const maxV = Math.max(...recentIdms);
              const minV = Math.min(...recentIdms);
              const latest = recentIdms[recentIdms.length - 1];

              return (
                <div
                  key={h.horseNumber}
                  className="flex-1 relative cursor-pointer"
                  style={{ opacity: isAnyHl && !isHl ? 0.15 : 1 }}
                  onMouseEnter={() => onHighlight(h.horseNumber)}
                  onMouseLeave={() => onHighlight(null)}
                >
                  {/* レンジライン（縦） */}
                  <div
                    className="absolute left-1/2 -translate-x-1/2 rounded-sm"
                    style={{
                      top: toY(maxV),
                      height: Math.max(toY(minV) - toY(maxV), 2),
                      width: isHl ? 4 : 2,
                      backgroundColor: color,
                    }}
                  />
                  {/* 個別ドット */}
                  {recentIdms.map((v, i) => (
                    <div
                      key={i}
                      className="absolute left-1/2 rounded-full"
                      style={{
                        top: toY(v),
                        width: isHl ? 10 : 7,
                        height: isHl ? 10 : 7,
                        transform: 'translate(-50%, -50%)',
                        backgroundColor: i === recentIdms.length - 1 ? color : 'white',
                        border: `2px solid ${color}`,
                      }}
                    />
                  ))}
                  {/* 最高IDMラベル（上部） */}
                  <div
                    className="absolute left-1/2 -translate-x-1/2 text-[10px] font-bold whitespace-nowrap"
                    style={{ top: toY(maxV) - 16, color }}
                  >
                    {maxV}
                  </div>
                  {/* 最新IDMラベル（最新が最高でない場合のみ） */}
                  {latest !== maxV && (
                    <div
                      className="absolute left-1/2 -translate-x-1/2 text-[9px] whitespace-nowrap"
                      style={{ top: toY(latest) + 10, color, opacity: 0.7 }}
                    >
                      {latest}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {/* 馬名ラベル */}
      <div className="flex" style={{ marginLeft: 32 }}>
        {sorted.map(h => {
          const color = colorMap[h.horseNumber];
          const isHl = highlightedHorse === h.horseNumber;
          const isAnyHl = highlightedHorse != null;
          return (
            <div
              key={h.horseNumber}
              className="flex-1 text-center pt-1"
              style={{ opacity: isAnyHl && !isHl ? 0.15 : 1 }}
            >
              <div className="text-[11px] font-bold" style={{ color }}>{h.horseNumber}</div>
              <div
                className="text-[9px] truncate mx-auto"
                style={{ color, fontWeight: isHl ? 700 : 400, maxWidth: 52 }}
                title={h.horseName}
              >
                {h.horseName}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── ソート可能サマリーテーブル ──

const TREND_ORDER: Record<string, number> = { up: 2, flat: 1, down: 0 };

// 相対順位で色クラスを返す（1位=緑, 2-3位=青, 4-5位=黄, 以降=デフォルト）
// higher=true: 値が大きいほど上位, higher=false: 値が小さいほど上位(オッズ用)
function rankColorClass(
  value: number | null | undefined,
  allValues: (number | null | undefined)[],
  higher: boolean = true,
): string {
  if (value == null) return '';
  const valid = allValues.filter((v): v is number => v != null);
  if (valid.length === 0) return '';
  const sorted = [...new Set(valid)].sort((a, b) => higher ? b - a : a - b);
  const rank = sorted.indexOf(value) + 1;
  if (rank === 1) return 'text-green-600 dark:text-green-400';
  if (rank <= 3) return 'text-blue-600 dark:text-blue-400';
  if (rank <= 5) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-muted-foreground';
}

interface SummaryTableProps {
  horses: HorseIDMData[];
  colorMap: Record<number, string>;
  visibleHorses: Set<number>;
  highlightedHorse: number | null;
  sortKey: SortKey;
  sortDesc: boolean;
  onSort: (key: SortKey) => void;
  onToggle: (num: number) => void;
  onHighlight: (num: number | null) => void;
}

function SummaryTable({
  horses, colorMap, visibleHorses, highlightedHorse,
  sortKey, sortDesc, onSort, onToggle, onHighlight,
}: SummaryTableProps) {

  const sorted = useMemo(() => {
    const arr = [...horses];
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (sortKey) {
        case 'horseNumber': va = a.horseNumber; vb = b.horseNumber; break;
        case 'latestIdm': va = a.latestIdm ?? -1; vb = b.latestIdm ?? -1; break;
        case 'maxIdm': va = a.maxIdm ?? -1; vb = b.maxIdm ?? -1; break;
        case 'max5Idm': va = a.max5Idm ?? -1; vb = b.max5Idm ?? -1; break;
        case 'avg3': va = a.avg3 ?? -1; vb = b.avg3 ?? -1; break;
        case 'avg5': va = a.avg5 ?? -1; vb = b.avg5 ?? -1; break;
        case 'raceCount': va = a.raceCount; vb = b.raceCount; break;
        case 'trend': va = TREND_ORDER[a.trend] ?? 0; vb = TREND_ORDER[b.trend] ?? 0; break;
        case 'odds': va = a.odds ?? 999; vb = b.odds ?? 999; break;
        case 'arDeviation': va = a.arDeviation ?? -1; vb = b.arDeviation ?? -1; break;
        case 'predProbaP': va = a.predProbaP ?? -1; vb = b.predProbaP ?? -1; break;
        case 'predProbaW': va = a.predProbaW ?? -1; vb = b.predProbaW ?? -1; break;
        default: va = a.horseNumber; vb = b.horseNumber;
      }
      return sortDesc ? vb - va : va - vb;
    });
    return arr;
  }, [horses, sortKey, sortDesc]);

  // 相対順位用の値配列を事前計算
  const allLatestIdm = horses.map(h => h.latestIdm);
  const allMaxIdm = horses.map(h => h.maxIdm);
  const allMax5Idm = horses.map(h => h.max5Idm);
  const allAvg3 = horses.map(h => h.avg3);
  const allAvg5 = horses.map(h => h.avg5);
  const allOdds = horses.map(h => h.odds);
  const allArd = horses.map(h => h.arDeviation);
  const allPredP = horses.map(h => h.predProbaP);
  const allPredW = horses.map(h => h.predProbaW);

  const columns: Array<{ key: SortKey; label: string }> = [
    { key: 'horseNumber', label: '番' },
    { key: 'latestIdm', label: '最新' },
    { key: 'maxIdm', label: '最高' },
    { key: 'max5Idm', label: '近5最高' },
    { key: 'avg3', label: '近3走' },
    { key: 'avg5', label: '近5走' },
    { key: 'trend', label: '傾向' },
    { key: 'predProbaP', label: 'P%' },
    { key: 'predProbaW', label: 'W%' },
    { key: 'odds', label: 'オッズ' },
    { key: 'arDeviation', label: 'ARd' },
    { key: 'raceCount', label: '戦数' },
  ];

  const sortArrow = (key: SortKey) => {
    if (sortKey !== key) return '';
    return sortDesc ? ' ▼' : ' ▲';
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/30">
            <th className="px-3 py-2 text-left w-8"></th>
            {columns.slice(0, 1).map(col => (
              <th
                key={col.key}
                onClick={() => onSort(col.key)}
                className="px-3 py-2 text-center cursor-pointer hover:bg-muted/50 transition-colors select-none w-10"
              >
                {col.label}{sortArrow(col.key)}
              </th>
            ))}
            <th className="px-3 py-2 text-left">馬名</th>
            {columns.slice(1).map(col => (
              <th
                key={col.key}
                onClick={() => onSort(col.key)}
                className="px-3 py-2 text-center cursor-pointer hover:bg-muted/50 transition-colors select-none"
              >
                {col.label}{sortArrow(col.key)}
              </th>
            ))}
            <th className="px-3 py-2 text-center">市場</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(h => {
            const color = colorMap[h.horseNumber];
            const isVisible = visibleHorses.has(h.horseNumber);
            const isHighlighted = highlightedHorse === h.horseNumber;
            const trendInfo = TREND_ICONS[h.trend];
            return (
              <tr
                key={h.horseNumber}
                onClick={() => onToggle(h.horseNumber)}
                onMouseEnter={() => onHighlight(h.horseNumber)}
                onMouseLeave={() => onHighlight(null)}
                className={`border-b cursor-pointer transition-colors ${
                  isHighlighted ? 'bg-muted/50' : 'hover:bg-muted/30'
                } ${!isVisible ? 'opacity-40' : ''}`}
              >
                <td className="px-3 py-1.5">
                  <span
                    className="w-3 h-3 rounded-full inline-block"
                    style={{ backgroundColor: isVisible ? color : '#ccc' }}
                  />
                </td>
                <td className="px-3 py-1.5 text-center font-mono font-bold" style={{ color }}>
                  {h.horseNumber}
                </td>
                <td className="px-3 py-1.5 font-medium">
                  <Link
                    href={`/horses/${h.horseId}`}
                    target="_blank"
                    onClick={(e) => e.stopPropagation()}
                    className="hover:underline hover:text-blue-600 dark:hover:text-blue-400"
                  >
                    {h.horseName}
                  </Link>
                </td>
                <td className={`px-3 py-1.5 text-center font-mono font-bold ${rankColorClass(h.latestIdm, allLatestIdm)}`}>
                  {h.latestIdm ?? '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono ${rankColorClass(h.maxIdm, allMaxIdm)}`}>
                  {h.maxIdm ?? '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono font-bold ${rankColorClass(h.max5Idm, allMax5Idm)}`}>
                  {h.max5Idm ?? '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono ${rankColorClass(h.avg3, allAvg3)}`}>
                  {h.avg3 != null ? h.avg3.toFixed(1) : '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono ${rankColorClass(h.avg5, allAvg5)}`}>
                  {h.avg5 != null ? h.avg5.toFixed(1) : '-'}
                </td>
                <td className={`px-3 py-1.5 text-center text-lg ${trendInfo?.color || ''}`}>
                  {trendInfo?.icon || '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono font-bold ${rankColorClass(h.predProbaP, allPredP)}`}>
                  {h.predProbaP != null ? h.predProbaP.toFixed(1) : '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono font-bold ${rankColorClass(h.predProbaW, allPredW)}`}>
                  {h.predProbaW != null ? h.predProbaW.toFixed(1) : '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono font-bold ${rankColorClass(h.odds, allOdds, false)}`}>
                  {h.odds != null ? h.odds.toFixed(1) : '-'}
                </td>
                <td className={`px-3 py-1.5 text-center font-mono font-bold ${rankColorClass(h.arDeviation, allArd)}`}>
                  {h.arDeviation != null ? h.arDeviation.toFixed(1) : '-'}
                </td>
                <td className="px-3 py-1.5 text-center text-muted-foreground">
                  {h.raceCount}
                </td>
                {/* 市場シグナル */}
                <td className="px-3 py-1.5 text-center">
                  {h.marketSignal && (
                    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold whitespace-nowrap ${
                      h.marketSignal === '鉄板' ? 'bg-gradient-to-r from-red-600 to-red-500 text-white' :
                      h.marketSignal === '軸向き' ? 'bg-gradient-to-r from-orange-500 to-orange-400 text-white' :
                      h.marketSignal === '妙味' ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white' :
                      h.marketSignal === 'やや妙味' ? 'bg-blue-100 text-blue-800' :
                      h.marketSignal === '想定通り' ? 'bg-gray-100 text-gray-600' :
                      h.marketSignal === '人気しすぎ' ? 'bg-yellow-100 text-yellow-800' :
                      h.marketSignal === '穴注目' ? 'bg-purple-100 text-purple-800' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {h.marketSignal}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
