'use client';

import { useState, useMemo } from 'react';
import { CourseCard, type CourseInfo } from '@/components/course-card';
import { ALL_COURSES, VENUES } from '@/data/course-data';

type SortKey = 'innerAdv' | 'styleAdv' | 'distance' | 'frontPct' | 'fcDist';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'innerAdv', label: '内有利度' },
  { key: 'styleAdv', label: '差し有利度' },
  { key: 'frontPct', label: '逃先top3率' },
  { key: 'fcDist', label: '1角距離' },
  { key: 'distance', label: '距離' },
];

function getSortValue(course: CourseInfo, key: SortKey): number {
  const b = course.babaAnalysis;
  switch (key) {
    case 'innerAdv': return b?.innerAdvantage ?? 0;
    case 'styleAdv': return b?.styleAdvantage ?? 0;
    case 'frontPct': return b?.frontRunnerTop3Pct ?? 0;
    case 'fcDist': return b?.firstCornerDistM ?? 999;
    case 'distance': return course.distanceMeters;
  }
}

export default function CourseDictionaryPage() {
  const [selectedVenue, setSelectedVenue] = useState<string>('全て');
  const [selectedSurface, setSelectedSurface] = useState<string>('全て');
  const [sortKey, setSortKey] = useState<SortKey>('innerAdv');
  const [sortDesc, setSortDesc] = useState(true);
  const [expandAll, setExpandAll] = useState(false);

  const filtered = useMemo(() => {
    let courses = ALL_COURSES;
    if (selectedVenue !== '全て') {
      courses = courses.filter(c => c.trackName === selectedVenue);
    }
    if (selectedSurface !== '全て') {
      courses = courses.filter(c => c.surface === selectedSurface);
    }
    const sorted = [...courses].sort((a, b) => {
      const va = getSortValue(a, sortKey);
      const vb = getSortValue(b, sortKey);
      return sortDesc ? vb - va : va - vb;
    });
    return sorted;
  }, [selectedVenue, selectedSurface, sortKey, sortDesc]);

  // 統計サマリ
  const summary = useMemo(() => {
    if (filtered.length === 0) return null;
    const withBaba = filtered.filter(c => c.babaAnalysis);
    if (withBaba.length === 0) return null;

    const avgInner = withBaba.reduce((s, c) => s + (c.babaAnalysis?.innerAdvantage ?? 0), 0) / withBaba.length;
    const avgStyle = withBaba.reduce((s, c) => s + (c.babaAnalysis?.styleAdvantage ?? 0), 0) / withBaba.length;
    const totalN = withBaba.reduce((s, c) => s + (c.babaAnalysis?.sampleSize ?? 0), 0);
    const mostInner = withBaba.reduce((best, c) =>
      (c.babaAnalysis?.innerAdvantage ?? -99) > (best.babaAnalysis?.innerAdvantage ?? -99) ? c : best
    );
    const mostOuter = withBaba.reduce((best, c) =>
      (c.babaAnalysis?.innerAdvantage ?? 99) < (best.babaAnalysis?.innerAdvantage ?? 99) ? c : best
    );

    return { avgInner, avgStyle, totalN, mostInner, mostOuter, count: withBaba.length };
  }, [filtered]);

  return (
    <div className="container py-6 max-w-5xl">
      <h1 className="text-2xl font-bold mb-1">コース辞典</h1>
      <p className="text-sm text-gray-500 mb-4">
        全{ALL_COURSES.length}コースの馬場バイアス分析 (2021-2026, 229,343エントリ)
      </p>

      {/* フィルタ・ソート */}
      <div className="bg-white rounded-xl border p-4 mb-4 space-y-3">
        {/* 会場フィルタ */}
        <div>
          <div className="text-xs text-gray-500 mb-1.5">会場</div>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setSelectedVenue('全て')}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                selectedVenue === '全て'
                  ? 'bg-gray-800 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              全て
            </button>
            {VENUES.map(v => (
              <button
                key={v}
                onClick={() => setSelectedVenue(v)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  selectedVenue === v
                    ? 'bg-gray-800 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>

        {/* 芝/ダートフィルタ */}
        <div className="flex items-center gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1.5">馬場</div>
            <div className="flex gap-1.5">
              {['全て', '芝', 'ダート'].map(s => (
                <button
                  key={s}
                  onClick={() => setSelectedSurface(s)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    selectedSurface === s
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
          </div>

          {/* ソート */}
          <div className="ml-auto">
            <div className="text-xs text-gray-500 mb-1.5">並び順</div>
            <div className="flex items-center gap-1.5">
              <select
                value={sortKey}
                onChange={e => setSortKey(e.target.value as SortKey)}
                className="text-xs border rounded px-2 py-1 bg-white"
              >
                {SORT_OPTIONS.map(o => (
                  <option key={o.key} value={o.key}>{o.label}</option>
                ))}
              </select>
              <button
                onClick={() => setSortDesc(!sortDesc)}
                className="text-xs border rounded px-2 py-1 bg-white hover:bg-gray-50"
              >
                {sortDesc ? '↓降順' : '↑昇順'}
              </button>
            </div>
          </div>
        </div>

        {/* 表示切替 */}
        <div className="flex items-center gap-2 border-t pt-2">
          <button
            onClick={() => setExpandAll(!expandAll)}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            {expandAll ? '全て閉じる' : '全て展開'}
          </button>
          <span className="text-xs text-gray-400">{filtered.length}コース表示</span>
        </div>
      </div>

      {/* サマリ */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          <div className="bg-white rounded-lg border p-3 text-center">
            <div className="text-xs text-gray-500">平均内有利度</div>
            <div className={`text-lg font-bold ${summary.avgInner > 0 ? 'text-blue-600' : 'text-orange-600'}`}>
              {summary.avgInner > 0 ? '+' : ''}{summary.avgInner.toFixed(1)}pt
            </div>
          </div>
          <div className="bg-white rounded-lg border p-3 text-center">
            <div className="text-xs text-gray-500">平均差し有利度</div>
            <div className={`text-lg font-bold ${summary.avgStyle > -15 ? 'text-green-600' : 'text-red-600'}`}>
              {summary.avgStyle.toFixed(1)}pt
            </div>
          </div>
          <div className="bg-white rounded-lg border p-3 text-center">
            <div className="text-xs text-gray-500">最も内有利</div>
            <div className="text-sm font-bold text-blue-700">
              {summary.mostInner.trackName}{summary.mostInner.distanceMeters}m
            </div>
            <div className="text-xs text-blue-500">
              +{summary.mostInner.babaAnalysis?.innerAdvantage.toFixed(1)}pt
            </div>
          </div>
          <div className="bg-white rounded-lg border p-3 text-center">
            <div className="text-xs text-gray-500">最も外有利</div>
            <div className="text-sm font-bold text-orange-700">
              {summary.mostOuter.trackName}{summary.mostOuter.surface === 'ダート' ? 'D' : ''}{summary.mostOuter.distanceMeters}m
            </div>
            <div className="text-xs text-orange-500">
              {summary.mostOuter.babaAnalysis?.innerAdvantage.toFixed(1)}pt
            </div>
          </div>
        </div>
      )}

      {/* コースカード一覧 */}
      <div className="space-y-3">
        {filtered.map((course, i) => (
          <CourseCard
            key={`${course.trackName}-${course.surface}-${course.distanceMeters}-${course.courseVariant || ''}`}
            course={course}
            compact={!expandAll}
          />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center text-gray-500 py-12">
          該当するコースがありません
        </div>
      )}
    </div>
  );
}
