'use client';

import Link from 'next/link';
import { useState, useMemo } from 'react';
import { ALL_COURSES, VENUES, VENUE_INFO, COURSE_TIPS, type VenueInfo } from '@/data/course-data';
import type { CourseInfo } from '@/components/course-card';

// 専門解説ページがあるコース (Phase 3d で追加)
function hasSpecialPage(c: CourseInfo): { href: string; label: string } | null {
  if (c.trackName === '新潟' && c.surface === '芝' && c.distanceMeters === 1000) {
    return { href: '/analysis/specialists/niigata-1000m', label: '千直' };
  }
  return null;
}

// =====================================================
// ヘルパー関数
// =====================================================
function getCourseKey(c: CourseInfo): string {
  return `${c.trackName}-${c.surface}-${c.distanceMeters}`;
}

function formatPt(v: number): string {
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}`;
}

// =====================================================
// VenueCard: 競馬場選択カード
// =====================================================
function VenueCard({
  venue,
  info,
  courseCount,
  isSelected,
  onClick,
}: {
  venue: string;
  info: VenueInfo;
  courseCount: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`relative flex flex-col items-start p-3 rounded-xl border-2 transition-all min-w-[140px] text-left ${
        isSelected
          ? 'border-current shadow-lg scale-[1.02]'
          : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
      }`}
      style={isSelected ? { borderColor: info.color, backgroundColor: `${info.color}08` } : {}}
    >
      <div className="flex items-center gap-2 w-full">
        <span
          className="text-xs font-bold px-1.5 py-0.5 rounded text-white"
          style={{ backgroundColor: info.color }}
        >
          {info.direction}
        </span>
        <span className="font-bold text-sm">{venue}</span>
        <span className="text-[10px] text-gray-400 ml-auto">{info.nameEn}</span>
      </div>
      <div className="flex items-center gap-2 mt-1.5 text-[11px] text-gray-500">
        <span>{info.grassType}</span>
        <span>|</span>
        <span>直線{info.turfStraight}m</span>
      </div>
      <div className="flex flex-wrap gap-1 mt-1.5">
        {info.tags.slice(0, 2).map(tag => (
          <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
            {tag}
          </span>
        ))}
      </div>
      <div className="text-[10px] text-gray-400 mt-1">{courseCount}コース</div>
    </button>
  );
}

// =====================================================
// VenueOverview: 競馬場概要パネル
// =====================================================
function VenueOverview({ info, courses }: { info: VenueInfo; courses: CourseInfo[] }) {
  const turfCourses = courses.filter(c => c.surface === '芝');
  const dirtCourses = courses.filter(c => c.surface === 'ダート');

  const avgInner = courses.reduce((s, c) => s + (c.babaAnalysis?.innerAdvantage ?? 0), 0) / courses.length;
  const avgStyle = courses.reduce((s, c) => s + (c.babaAnalysis?.styleAdvantage ?? 0), 0) / courses.length;

  // 最も特徴的なコースを見つける
  const mostBiased = [...courses].sort((a, b) =>
    Math.abs(b.babaAnalysis?.innerAdvantage ?? 0) - Math.abs(a.babaAnalysis?.innerAdvantage ?? 0)
  )[0];

  return (
    <div className="rounded-2xl border-2 overflow-hidden mb-6" style={{ borderColor: `${info.color}30` }}>
      {/* ヘッダー */}
      <div
        className="px-5 py-4"
        style={{ background: `linear-gradient(135deg, ${info.color}12, ${info.color}06)` }}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold">{info.name}競馬場</h2>
              <span className="text-sm text-gray-400 font-mono">{info.nameEn}</span>
            </div>
            <p className="text-sm text-gray-600 mt-0.5">{info.characteristics}</p>
          </div>
          <div className="flex gap-1.5">
            {info.tags.map(tag => (
              <span
                key={tag}
                className="text-[11px] px-2 py-0.5 rounded-full font-medium text-white"
                style={{ backgroundColor: info.color }}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* スペック */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-gray-100">
        {[
          { label: '芝直線', value: `${info.turfStraight}m`, sub: info.courseType === 'large' ? '長い' : info.courseType === 'medium' ? '中程度' : '短い' },
          { label: '高低差', value: `${info.heightDiff}m`, sub: info.hasSlope ? '急坂あり' : '平坦' },
          { label: '芝1周', value: `${info.turfCircumference.toFixed(0)}m`, sub: `${info.direction}回り` },
          { label: '平均内有利度', value: `${formatPt(avgInner)}pt`, sub: avgInner > 1 ? '内有利傾向' : avgInner < -1 ? '外有利傾向' : 'フラット' },
        ].map((stat, i) => (
          <div key={i} className="bg-white px-4 py-3 text-center">
            <div className="text-[10px] text-gray-400 uppercase tracking-wider">{stat.label}</div>
            <div className="text-lg font-bold mt-0.5" style={{ color: info.color }}>{stat.value}</div>
            <div className="text-[10px] text-gray-500">{stat.sub}</div>
          </div>
        ))}
      </div>

      {/* 解説 */}
      <div className="px-5 py-4 space-y-3">
        <div className="grid md:grid-cols-2 gap-4">
          {/* 芝 */}
          <div className="rounded-xl bg-green-50 p-3.5">
            <div className="flex items-center gap-1.5 mb-1.5">
              <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center text-white text-[10px] font-bold">芝</div>
              <span className="text-xs font-bold text-green-800">芝コースの特徴</span>
              <span className="text-[10px] text-green-600 ml-auto">{turfCourses.length}コース</span>
            </div>
            <p className="text-xs text-green-900 leading-relaxed">{info.turfNote}</p>
          </div>
          {/* ダート */}
          <div className="rounded-xl bg-amber-50 p-3.5">
            <div className="flex items-center gap-1.5 mb-1.5">
              <div className="w-5 h-5 rounded-full bg-amber-600 flex items-center justify-center text-white text-[10px] font-bold">D</div>
              <span className="text-xs font-bold text-amber-800">ダートの特徴</span>
              <span className="text-[10px] text-amber-600 ml-auto">{dirtCourses.length}コース</span>
            </div>
            <p className="text-xs text-amber-900 leading-relaxed">{info.dirtNote}</p>
          </div>
        </div>

        {/* 馬場状態メモ */}
        {info.trackConditionNote && (
          <div className="rounded-lg bg-gray-50 px-3.5 py-2.5 flex items-start gap-2">
            <span className="text-xs text-gray-400 shrink-0 mt-0.5">NOTE</span>
            <p className="text-xs text-gray-600 leading-relaxed">{info.trackConditionNote}</p>
          </div>
        )}

        {/* 最も特徴的なコース */}
        {mostBiased?.babaAnalysis && Math.abs(mostBiased.babaAnalysis.innerAdvantage) >= 3 && (
          <div className="rounded-lg bg-blue-50 px-3.5 py-2.5 flex items-start gap-2">
            <span className="text-xs text-blue-500 shrink-0 mt-0.5">PICK</span>
            <p className="text-xs text-blue-700">
              注目コース: <span className="font-bold">{mostBiased.surface}{mostBiased.distanceMeters}m</span>
              {' — '}
              {mostBiased.babaAnalysis.innerAdvantage > 0 ? '内' : '外'}有利度
              <span className="font-bold">{formatPt(mostBiased.babaAnalysis.innerAdvantage)}pt</span>
              （{mostBiased.babaAnalysis.sampleSize.toLocaleString()}レース分析）
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// =====================================================
// BiasBar: 内外/脚質バイアスの視覚バー
// =====================================================
function BiasBar({
  value,
  maxAbs = 10,
  leftLabel,
  rightLabel,
  leftColor = '#f97316',
  rightColor = '#3b82f6',
}: {
  value: number;
  maxAbs?: number;
  leftLabel: string;
  rightLabel: string;
  leftColor?: string;
  rightColor?: string;
}) {
  const clamped = Math.max(-maxAbs, Math.min(maxAbs, value));
  const pct = Math.abs(clamped) / maxAbs * 50;
  const isPositive = value >= 0;

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-gray-400 w-7 text-right shrink-0">{leftLabel}</span>
      <div className="flex-1 h-2.5 bg-gray-100 rounded-full relative overflow-hidden">
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-300 z-10" />
        {isPositive ? (
          <div
            className="absolute top-0 bottom-0 rounded-r-full"
            style={{ left: '50%', width: `${pct}%`, backgroundColor: rightColor }}
          />
        ) : (
          <div
            className="absolute top-0 bottom-0 rounded-l-full"
            style={{ right: '50%', width: `${pct}%`, backgroundColor: leftColor }}
          />
        )}
      </div>
      <span className="text-[10px] text-gray-400 w-7 shrink-0">{rightLabel}</span>
      <span className="text-xs font-mono font-bold w-12 text-right" style={{ color: isPositive ? rightColor : leftColor }}>
        {formatPt(value)}
      </span>
    </div>
  );
}

// =====================================================
// EnhancedCourseCard: 強化版コースカード
// =====================================================
function EnhancedCourseCard({ course, venueColor }: { course: CourseInfo; venueColor: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const baba = course.babaAnalysis;
  const tipKey = getCourseKey(course);
  const tip = COURSE_TIPS[tipKey];

  const isTurf = course.surface === '芝';
  const surfaceColor = isTurf ? '#16a34a' : '#d97706';
  const surfaceBg = isTurf ? 'bg-green-50' : 'bg-amber-50';

  // バイアス強度でカードの左ボーダーの色を決める
  const biasIntensity = Math.abs(baba?.innerAdvantage ?? 0);
  const borderColor = biasIntensity >= 5
    ? (baba?.innerAdvantage ?? 0) > 0 ? '#3b82f6' : '#f97316'
    : '#e5e7eb';

  return (
    <div
      className="rounded-xl border bg-white overflow-hidden hover:shadow-md transition-all cursor-pointer"
      style={{ borderLeftWidth: 4, borderLeftColor: borderColor }}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* コンパクトヘッダー */}
      <div className={`px-4 py-3 ${surfaceBg}`}>
        <div className="flex items-center gap-3">
          {/* 表面タイプバッジ */}
          <div
            className="w-10 h-10 rounded-lg flex flex-col items-center justify-center text-white font-bold shrink-0"
            style={{ backgroundColor: surfaceColor }}
          >
            <span className="text-[10px] leading-none">{course.surface}</span>
            <span className="text-sm leading-tight">{course.distanceMeters}</span>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-bold">
                {course.trackName} {course.surface}{course.distanceMeters}m
                {course.courseVariant && course.courseVariant !== 'なし' && (
                  <span className="text-gray-500 text-xs font-normal ml-1">({course.courseVariant})</span>
                )}
              </h3>
              {hasSpecialPage(course) && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-600 text-white">
                  {hasSpecialPage(course)!.label}
                </span>
              )}
            </div>
            {tip && (
              <p className="text-xs text-gray-600 mt-0.5 truncate">{tip.headline}</p>
            )}
          </div>

          {/* ミニバイアスバッジ */}
          {baba && (
            <div className="flex flex-col items-end gap-1 shrink-0">
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                baba.innerAdvantage >= 3 ? 'bg-blue-100 text-blue-700'
                : baba.innerAdvantage <= -3 ? 'bg-orange-100 text-orange-700'
                : 'bg-gray-100 text-gray-500'
              }`}>
                {baba.innerAdvantage >= 3 ? '内有利' : baba.innerAdvantage <= -3 ? '外有利' : 'フラット'}
                {Math.abs(baba.innerAdvantage) >= 1 && ` ${formatPt(baba.innerAdvantage)}`}
              </span>
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                baba.styleAdvantage >= -10 ? 'bg-green-100 text-green-700'
                : baba.styleAdvantage <= -20 ? 'bg-red-100 text-red-700'
                : 'bg-yellow-100 text-yellow-700'
              }`}>
                {baba.styleAdvantage >= -10 ? '差し有効' : baba.styleAdvantage <= -20 ? '先行圧倒' : '先行有利'}
              </span>
            </div>
          )}

          <span className="text-gray-300 text-sm">{isExpanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* 展開コンテンツ */}
      {isExpanded && (
        <div className="px-4 py-4 space-y-4">
          {/* 専門解説リンク (千直など) */}
          {hasSpecialPage(course) && (
            <Link
              href={hasSpecialPage(course)!.href}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="block rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 px-4 py-3 hover:shadow-md hover:border-blue-300 transition-all"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold text-blue-900">vega-niigata1000 専門解説 →</div>
                  <div className="text-[11px] text-blue-700">枠順バイアス・強馬製造元・ルールエンジン v0.2</div>
                </div>
                <span className="text-blue-600 text-lg">›</span>
              </div>
            </Link>
          )}


          {/* バイアスバー */}
          {baba && (
            <div className="space-y-2">
              <BiasBar
                value={baba.innerAdvantage}
                leftLabel="外"
                rightLabel="内"
                leftColor="#f97316"
                rightColor="#3b82f6"
              />
              <BiasBar
                value={-baba.styleAdvantage}
                maxAbs={30}
                leftLabel="前"
                rightLabel="差"
                leftColor="#ef4444"
                rightColor="#22c55e"
              />
            </div>
          )}

          {/* 数値グリッド */}
          {baba && (
            <div className="grid grid-cols-4 gap-2">
              <div className="text-center bg-gray-50 rounded-lg py-2">
                <div className="text-[10px] text-gray-400">内枠top3</div>
                <div className="text-sm font-bold">{baba.innerTop3Pct.toFixed(1)}%</div>
              </div>
              <div className="text-center bg-gray-50 rounded-lg py-2">
                <div className="text-[10px] text-gray-400">外枠top3</div>
                <div className="text-sm font-bold">{baba.outerTop3Pct.toFixed(1)}%</div>
              </div>
              <div className="text-center bg-gray-50 rounded-lg py-2">
                <div className="text-[10px] text-gray-400">逃先top3</div>
                <div className="text-sm font-bold">{baba.frontRunnerTop3Pct.toFixed(1)}%</div>
              </div>
              {baba.firstCornerDistM && (
                <div className="text-center bg-gray-50 rounded-lg py-2">
                  <div className="text-[10px] text-gray-400">1角距離</div>
                  <div className="text-sm font-bold">{baba.firstCornerDistM}m</div>
                </div>
              )}
            </div>
          )}

          {/* コース解説 */}
          {tip && (
            <div className="space-y-2">
              <p className="text-xs text-gray-700 leading-relaxed">{tip.description}</p>

              {/* 狙い方Tips */}
              <div className="rounded-lg p-3" style={{ backgroundColor: `${venueColor}08`, border: `1px solid ${venueColor}20` }}>
                <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: venueColor }}>
                  このコースの狙い方
                </div>
                <div className="space-y-1">
                  {tip.tips.map((t, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-xs">
                      <span style={{ color: venueColor }} className="shrink-0 mt-0.5">●</span>
                      <span className="text-gray-700">{t}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* コーススペック */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-gray-500">
            <span>{course.turn}回り</span>
            {course.courseGeometry && (
              <>
                <span>直線{course.courseGeometry.straightLengthM}m</span>
                <span>高低差{course.courseGeometry.elevationDiffM}m</span>
              </>
            )}
            {baba && <span>n={baba.sampleSize.toLocaleString()}</span>}
          </div>

          {/* 馬場状態別バイアス */}
          {baba?.conditionBias && baba.conditionBias.length > 0 && (
            <div>
              <div className="text-[10px] text-gray-400 mb-1.5">馬場状態別バイアス</div>
              <div className="grid grid-cols-3 gap-1.5">
                {baba.conditionBias.map((cb, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg px-2.5 py-2 text-center">
                    <div className="text-[10px] text-gray-500">{cb.label}</div>
                    <div className={`text-xs font-bold ${cb.innerAdvantage > 0 ? 'text-blue-600' : 'text-orange-600'}`}>
                      内{formatPt(cb.innerAdvantage)}pt
                    </div>
                    <div className="text-[10px] text-gray-400">n={cb.sampleSize}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 高低断面図 */}
          {course.elevationProfile && (
            <ElevationMiniChart profile={course.elevationProfile} />
          )}
        </div>
      )}
    </div>
  );
}

// =====================================================
// ElevationMiniChart: 高低断面図(小型)
// =====================================================
function ElevationMiniChart({ profile }: { profile: NonNullable<CourseInfo['elevationProfile']> }) {
  if (!profile.points || profile.points.length < 2) return null;

  const width = 400;
  const height = 70;
  const padding = { top: 8, bottom: 20, left: 5, right: 5 };
  const points = profile.points;
  const maxDist = Math.max(...points.map(p => p.distanceFromGoalM));
  const minElev = Math.min(...points.map(p => p.elevationM));
  const maxElev = Math.max(...points.map(p => p.elevationM));
  const elevRange = maxElev - minElev || 1;
  const cw = width - padding.left - padding.right;
  const ch = height - padding.top - padding.bottom;

  const svgPoints = points.map(p => ({
    x: padding.left + (1 - p.distanceFromGoalM / maxDist) * cw,
    y: padding.top + (1 - (p.elevationM - minElev) / elevRange) * ch,
    landmark: p.landmark,
  }));

  const pathD = svgPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const fillD = `${pathD} L ${svgPoints[svgPoints.length - 1].x} ${height - padding.bottom} L ${svgPoints[0].x} ${height - padding.bottom} Z`;

  return (
    <div>
      <div className="text-[10px] text-gray-400 mb-1">高低断面図</div>
      <svg width={width} height={height} className="w-full" viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <linearGradient id="elevFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.1" />
          </linearGradient>
        </defs>
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#e5e7eb" strokeWidth="1" />
        <path d={fillD} fill="url(#elevFill)" />
        <path d={pathD} fill="none" stroke="#16a34a" strokeWidth="1.5" />
        {svgPoints.filter(p => p.landmark).map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="2" fill="#16a34a" />
            <text x={p.x} y={height - 5} textAnchor="middle" fontSize="7" fill="#999">
              {p.landmark?.replace('コーナー', 'C')}
            </text>
          </g>
        ))}
      </svg>
      {profile.keyFeatures && (
        <div className="space-y-0.5 mt-1">
          {profile.keyFeatures.map((f, i) => (
            <div key={i} className="text-[11px] text-gray-500">
              <span className="font-medium text-gray-600">{f.position}:</span> {f.description}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =====================================================
// ComparisonTable: 全場比較テーブル
// =====================================================
function ComparisonTable({ courses }: { courses: CourseInfo[] }) {
  const [sortBy, setSortBy] = useState<'inner' | 'style' | 'front' | 'fc'>('inner');
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    return [...courses].filter(c => c.babaAnalysis).sort((a, b) => {
      const ba = a.babaAnalysis!;
      const bb = b.babaAnalysis!;
      let va: number, vb: number;
      switch (sortBy) {
        case 'inner': va = ba.innerAdvantage; vb = bb.innerAdvantage; break;
        case 'style': va = ba.styleAdvantage; vb = bb.styleAdvantage; break;
        case 'front': va = ba.frontRunnerTop3Pct; vb = bb.frontRunnerTop3Pct; break;
        case 'fc': va = ba.firstCornerDistM ?? 999; vb = bb.firstCornerDistM ?? 999; break;
      }
      return sortAsc ? va - vb : vb - va;
    });
  }, [courses, sortBy, sortAsc]);

  const headers: { key: typeof sortBy; label: string }[] = [
    { key: 'inner', label: '内有利度' },
    { key: 'style', label: '脚質(差有利度)' },
    { key: 'front', label: '逃先top3%' },
    { key: 'fc', label: '1角距離' },
  ];

  return (
    <div className="rounded-xl border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-50">
              <th className="text-left px-3 py-2 font-medium text-gray-500">コース</th>
              {headers.map(h => (
                <th
                  key={h.key}
                  className="text-right px-3 py-2 font-medium text-gray-500 cursor-pointer hover:text-gray-800"
                  onClick={() => {
                    if (sortBy === h.key) setSortAsc(!sortAsc);
                    else { setSortBy(h.key); setSortAsc(false); }
                  }}
                >
                  {h.label}
                  {sortBy === h.key && (sortAsc ? ' ↑' : ' ↓')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.slice(0, 20).map((c, i) => {
              const b = c.babaAnalysis!;
              return (
                <tr key={i} className="border-t hover:bg-gray-50">
                  <td className="px-3 py-2">
                    <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${c.surface === '芝' ? 'bg-green-500' : 'bg-amber-500'}`} />
                    <span className="font-medium">{c.trackName}</span>
                    <span className="text-gray-400 ml-1">{c.surface}{c.distanceMeters}m</span>
                  </td>
                  <td className={`px-3 py-2 text-right font-mono font-medium ${b.innerAdvantage > 0 ? 'text-blue-600' : 'text-orange-600'}`}>
                    {formatPt(b.innerAdvantage)}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono ${b.styleAdvantage >= -10 ? 'text-green-600' : b.styleAdvantage <= -20 ? 'text-red-600' : 'text-yellow-600'}`}>
                    {formatPt(b.styleAdvantage)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{b.frontRunnerTop3Pct.toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-600">{b.firstCornerDistM ?? '-'}m</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {sorted.length > 20 && (
        <div className="text-center py-2 text-[10px] text-gray-400 bg-gray-50 border-t">
          上位20コースを表示（全{sorted.length}コース）
        </div>
      )}
    </div>
  );
}

// =====================================================
// メインページ
// =====================================================
type ViewMode = 'cards' | 'table';

export default function CourseDictionaryPage() {
  const [selectedVenue, setSelectedVenue] = useState<string | null>(null);
  const [surfaceFilter, setSurfaceFilter] = useState<string>('全て');
  const [viewMode, setViewMode] = useState<ViewMode>('cards');

  const venueInfo = selectedVenue ? VENUE_INFO[selectedVenue] : null;

  const filtered = useMemo(() => {
    let courses = ALL_COURSES;
    if (selectedVenue) {
      courses = courses.filter(c => c.trackName === selectedVenue);
    }
    if (surfaceFilter !== '全て') {
      courses = courses.filter(c => c.surface === surfaceFilter);
    }
    // 距離順にソート
    return [...courses].sort((a, b) => {
      if (a.surface !== b.surface) return a.surface === '芝' ? -1 : 1;
      return a.distanceMeters - b.distanceMeters;
    });
  }, [selectedVenue, surfaceFilter]);

  return (
    <div className="container py-6 max-w-7xl">
      {/* ヘッダー */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold">コース辞典</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          JRA全10場 {ALL_COURSES.length}コースの馬場バイアス分析と実践的な狙い方
        </p>
      </div>

      {/* 競馬場選択カード */}
      <div className="mb-5">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-gray-400 font-medium">競馬場を選択</span>
          {selectedVenue && (
            <button
              onClick={() => setSelectedVenue(null)}
              className="text-[11px] text-gray-400 hover:text-gray-600 ml-auto"
            >
              全場比較に戻る
            </button>
          )}
        </div>
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
          {VENUES.map(v => {
            const info = VENUE_INFO[v];
            const count = ALL_COURSES.filter(c => c.trackName === v).length;
            return (
              <VenueCard
                key={v}
                venue={v}
                info={info}
                courseCount={count}
                isSelected={selectedVenue === v}
                onClick={() => setSelectedVenue(selectedVenue === v ? null : v)}
              />
            );
          })}
        </div>
      </div>

      {/* 競馬場概要パネル */}
      {venueInfo && selectedVenue && (
        <VenueOverview
          info={venueInfo}
          courses={ALL_COURSES.filter(c => c.trackName === selectedVenue)}
        />
      )}

      {/* フィルタ・表示切替 */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex gap-1.5">
          {['全て', '芝', 'ダート'].map(s => (
            <button
              key={s}
              onClick={() => setSurfaceFilter(s)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                surfaceFilter === s
                  ? s === '芝' ? 'bg-green-600 text-white'
                    : s === 'ダート' ? 'bg-amber-600 text-white'
                    : 'bg-gray-800 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <span className="text-[11px] text-gray-400">{filtered.length}コース</span>

        <div className="ml-auto flex gap-1">
          <button
            onClick={() => setViewMode('cards')}
            className={`px-2.5 py-1 rounded text-xs ${viewMode === 'cards' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-500'}`}
          >
            カード
          </button>
          <button
            onClick={() => setViewMode('table')}
            className={`px-2.5 py-1 rounded text-xs ${viewMode === 'table' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-500'}`}
          >
            比較表
          </button>
        </div>
      </div>

      {/* コンテンツ */}
      {viewMode === 'table' ? (
        <ComparisonTable courses={filtered} />
      ) : (
        <div className="space-y-2.5">
          {filtered.map((course, i) => (
            <EnhancedCourseCard
              key={`${course.trackName}-${course.surface}-${course.distanceMeters}-${course.courseVariant || ''}`}
              course={course}
              venueColor={venueInfo?.color ?? VENUE_INFO[course.trackName]?.color ?? '#6b7280'}
            />
          ))}
        </div>
      )}

      {filtered.length === 0 && (
        <div className="text-center text-gray-400 py-16 text-sm">
          該当するコースがありません
        </div>
      )}
    </div>
  );
}
