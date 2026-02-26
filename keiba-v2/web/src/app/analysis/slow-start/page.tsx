'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw, Users, List, Search, TrendingDown, AlertTriangle, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RecalcButton } from '@/components/admin/recalc-button';

// ============================================================
// Types
// ============================================================

interface Coverage {
  from_date: string;
  to_date: string;
  races_with_hassou: number;
  total_entries: number;
  total_slow_starts: number;
}

interface YearStat {
  total: number;
  slow: number;
  rate: number;
  avg_fp_slow: number | null;
  top3_slow: number | null;
  top3_normal: number | null;
}

interface JockeyRanking {
  jockey_code: string;
  jockey_name: string;
  total_rides: number;
  slow_starts: number;
  slow_start_rate: number;
  avg_finish_when_slow: number | null;
  top3_rate_when_slow: number | null;
  top3_rate_normal: number | null;
  year_stats: Record<string, YearStat>;
}

interface Incident {
  date: string;
  venue_name: string;
  race_num: number;
  umaban: number;
  horse_name: string;
  ketto_num: string;
  jockey_name: string;
  jockey_code: string;
  finish_position: number;
  num_runners: number;
  hassou_excerpt: string;
}

interface HorseYearStat {
  total: number;
  slow: number;
}

interface HorseStat {
  ketto_num: string;
  horse_name: string;
  total_with_hassou: number;
  slow_count: number;
  slow_start_rate: number;
  avg_finish_when_slow: number | null;
  top3_when_slow: number;
  year_stats: Record<string, HorseYearStat>;
}

interface SlowStartData {
  generated_at: string;
  coverage: Coverage;
  jockey_ranking: JockeyRanking[];
  recent_incidents: Incident[];
  horse_stats: HorseStat[];
}

// ============================================================
// Helpers
// ============================================================

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(digits)}%`;
}

function rateColor(rate: number): string {
  if (rate >= 0.30) return 'text-red-600 dark:text-red-400';
  if (rate >= 0.25) return 'text-orange-600 dark:text-orange-400';
  if (rate >= 0.20) return 'text-amber-600 dark:text-amber-400';
  if (rate <= 0.10) return 'text-green-600 dark:text-green-400';
  return '';
}

function fpColor(fp: number, nr: number): string {
  if (fp <= 3) return 'text-green-600 dark:text-green-400 font-bold';
  if (fp >= nr - 2) return 'text-red-500 dark:text-red-400';
  return '';
}

// ============================================================
// Main Page
// ============================================================

export default function SlowStartAnalysisPage() {
  const [data, setData] = useState<SlowStartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedYear, setSelectedYear] = useState<string>('all');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/slow-start');
      const result = await res.json();
      if (!res.ok) {
        setError(result.message || 'データ取得に失敗');
        return;
      }
      setData(result);
    } catch {
      setError('データ取得に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  // 利用可能な年を抽出
  const availableYears = useMemo(() => {
    if (!data) return [];
    const years = new Set<string>();
    // jockey year_stats から取得（全年を網羅）
    for (const j of data.jockey_ranking) {
      for (const y of Object.keys(j.year_stats || {})) {
        years.add(y);
      }
    }
    return Array.from(years).sort();
  }, [data]);

  if (loading) return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-center py-16 gap-3">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="text-muted-foreground">読み込み中...</span>
      </div>
    </div>
  );

  if (error) return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <Card className="bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-800">
        <CardContent className="p-6 text-center">
          <AlertTriangle className="h-8 w-8 text-amber-600 mx-auto mb-2" />
          <p className="text-amber-800 dark:text-amber-200 font-medium">{error}</p>
        </CardContent>
      </Card>
    </div>
  );

  if (!data) return null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Breadcrumb + Title */}
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
          <Link href="/" className="hover:underline flex items-center gap-1">
            <ArrowLeft className="h-4 w-4" />トップ
          </Link>
          <span>/</span>
          <span className="text-foreground">出遅れ分析</span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">出遅れ分析</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {data.coverage.from_date} ~ {data.coverage.to_date} |
              {' '}{data.coverage.races_with_hassou.toLocaleString()}レース |
              {' '}{data.coverage.total_slow_starts.toLocaleString()}件の出遅れ
              {' '}({pct(data.coverage.total_slow_starts / data.coverage.total_entries)})
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={fetchData} className="gap-1.5">
              <RefreshCw className="h-4 w-4" />更新
            </Button>
            <RecalcButton actionId="rebuild_slow_start" onComplete={fetchData} />
          </div>
        </div>
      </div>

      {/* Year Filter */}
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">期間:</span>
        <Button
          size="sm"
          variant={selectedYear === 'all' ? 'default' : 'outline'}
          className="h-7 px-2.5 text-xs"
          onClick={() => setSelectedYear('all')}
        >
          全期間
        </Button>
        {availableYears.map(y => (
          <Button
            key={y}
            size="sm"
            variant={selectedYear === y ? 'default' : 'outline'}
            className="h-7 px-2.5 text-xs"
            onClick={() => setSelectedYear(y)}
          >
            {y}年
          </Button>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="jockey">
        <TabsList>
          <TabsTrigger value="jockey" className="gap-1.5">
            <Users className="h-4 w-4" />騎手ランキング
          </TabsTrigger>
          <TabsTrigger value="recent" className="gap-1.5">
            <List className="h-4 w-4" />直近の出遅れ
          </TabsTrigger>
          <TabsTrigger value="horse" className="gap-1.5">
            <Search className="h-4 w-4" />馬の出遅れ履歴
          </TabsTrigger>
        </TabsList>

        <TabsContent value="jockey" className="mt-4">
          <JockeyTab data={data} selectedYear={selectedYear} />
        </TabsContent>
        <TabsContent value="recent" className="mt-4">
          <RecentTab data={data} selectedYear={selectedYear} />
        </TabsContent>
        <TabsContent value="horse" className="mt-4">
          <HorseTab data={data} selectedYear={selectedYear} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ============================================================
// Tab 1: 騎手出遅れ率ランキング
// ============================================================

type SortKey = 'slow_start_rate' | 'slow_starts' | 'total_rides' | 'avg_finish_when_slow' | 'top3_rate_when_slow' | 'top3_rate_normal';

interface JockeyRow {
  jockey_code: string;
  jockey_name: string;
  total_rides: number;
  slow_starts: number;
  slow_start_rate: number;
  avg_finish_when_slow: number | null;
  top3_rate_when_slow: number | null;
  top3_rate_normal: number | null;
}

function JockeyTab({ data, selectedYear }: { data: SlowStartData; selectedYear: string }) {
  const [minRides, setMinRides] = useState(50);
  const [sortKey, setSortKey] = useState<SortKey>('slow_start_rate');
  const [sortAsc, setSortAsc] = useState(false);

  // 年フィルタ適用: year_stats から行データを組み立て
  const rows: JockeyRow[] = useMemo(() => {
    if (selectedYear === 'all') {
      return data.jockey_ranking.map(j => ({
        jockey_code: j.jockey_code,
        jockey_name: j.jockey_name,
        total_rides: j.total_rides,
        slow_starts: j.slow_starts,
        slow_start_rate: j.slow_start_rate,
        avg_finish_when_slow: j.avg_finish_when_slow,
        top3_rate_when_slow: j.top3_rate_when_slow,
        top3_rate_normal: j.top3_rate_normal,
      }));
    }
    // 年別: year_stats から構築
    const result: JockeyRow[] = [];
    for (const j of data.jockey_ranking) {
      const ys = j.year_stats?.[selectedYear];
      if (!ys || ys.total === 0) continue;
      result.push({
        jockey_code: j.jockey_code,
        jockey_name: j.jockey_name,
        total_rides: ys.total,
        slow_starts: ys.slow,
        slow_start_rate: ys.rate,
        avg_finish_when_slow: ys.avg_fp_slow,
        top3_rate_when_slow: ys.top3_slow,
        top3_rate_normal: ys.top3_normal,
      });
    }
    return result;
  }, [data.jockey_ranking, selectedYear]);

  const filtered = useMemo(() => {
    const list = rows.filter(j => j.total_rides >= minRides);
    list.sort((a, b) => {
      const va = a[sortKey] ?? 999;
      const vb = b[sortKey] ?? 999;
      return sortAsc ? (va as number) - (vb as number) : (vb as number) - (va as number);
    });
    return list;
  }, [rows, minRides, sortKey, sortAsc]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return '';
    return sortAsc ? ' ▲' : ' ▼';
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">
            騎手出遅れ率ランキング
            {selectedYear !== 'all' && (
              <Badge variant="outline" className="ml-2 text-xs font-normal">{selectedYear}年</Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">最低騎乗数:</span>
            {[30, 50, 100, 200].map(n => (
              <Button
                key={n}
                size="sm"
                variant={minRides === n ? 'default' : 'outline'}
                className="h-7 px-2 text-xs"
                onClick={() => setMinRides(n)}
              >
                {n}+
              </Button>
            ))}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {filtered.length}騎手 | ヘッダークリックでソート
        </p>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-muted-foreground border-b bg-muted/30 text-xs">
                <th className="text-left py-2 px-3 w-8">#</th>
                <th className="text-left py-2 px-2">騎手</th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('total_rides')}>
                  騎乗数{sortIcon('total_rides')}
                </th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('slow_starts')}>
                  出遅れ{sortIcon('slow_starts')}
                </th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('slow_start_rate')}>
                  出遅れ率{sortIcon('slow_start_rate')}
                </th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('avg_finish_when_slow')}>
                  平均着順(遅){sortIcon('avg_finish_when_slow')}
                </th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('top3_rate_when_slow')}>
                  複勝率(遅){sortIcon('top3_rate_when_slow')}
                </th>
                <th className="text-right py-2 px-2 cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('top3_rate_normal')}>
                  複勝率(通常){sortIcon('top3_rate_normal')}
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((j, i) => (
                <tr key={j.jockey_code} className="border-b border-gray-100 dark:border-gray-800 hover:bg-muted/20">
                  <td className="py-1.5 px-3 text-muted-foreground text-xs">{i + 1}</td>
                  <td className="py-1.5 px-2 font-medium">{j.jockey_name}</td>
                  <td className="text-right py-1.5 px-2 font-mono text-muted-foreground">{j.total_rides}</td>
                  <td className="text-right py-1.5 px-2 font-mono">{j.slow_starts}</td>
                  <td className={`text-right py-1.5 px-2 font-mono font-bold ${rateColor(j.slow_start_rate)}`}>
                    {pct(j.slow_start_rate)}
                  </td>
                  <td className="text-right py-1.5 px-2 font-mono text-muted-foreground">
                    {j.avg_finish_when_slow?.toFixed(1) ?? '-'}
                  </td>
                  <td className="text-right py-1.5 px-2 font-mono text-muted-foreground">
                    {pct(j.top3_rate_when_slow)}
                  </td>
                  <td className="text-right py-1.5 px-2 font-mono">
                    {pct(j.top3_rate_normal)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================
// Tab 2: 直近の出遅れ一覧
// ============================================================

function RecentTab({ data, selectedYear }: { data: SlowStartData; selectedYear: string }) {
  const [dateFilter, setDateFilter] = useState<'all' | '1m' | '3m'>('all');
  const [showCount, setShowCount] = useState(200);

  const yearFiltered = useMemo(() => {
    if (selectedYear === 'all') return data.recent_incidents;
    return data.recent_incidents.filter(inc => inc.date.startsWith(selectedYear));
  }, [data.recent_incidents, selectedYear]);

  const filtered = useMemo(() => {
    let list = yearFiltered;
    if (dateFilter !== 'all') {
      const now = new Date();
      const months = dateFilter === '1m' ? 1 : 3;
      const cutoff = new Date(now.getFullYear(), now.getMonth() - months, now.getDate())
        .toISOString().slice(0, 10);
      list = list.filter(inc => inc.date >= cutoff);
    }
    return list.slice(0, showCount);
  }, [yearFiltered, dateFilter, showCount]);

  const totalFiltered = useMemo(() => {
    let list = yearFiltered;
    if (dateFilter !== 'all') {
      const now = new Date();
      const months = dateFilter === '1m' ? 1 : 3;
      const cutoff = new Date(now.getFullYear(), now.getMonth() - months, now.getDate())
        .toISOString().slice(0, 10);
      list = list.filter(inc => inc.date >= cutoff);
    }
    return list.length;
  }, [yearFiltered, dateFilter]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">
            直近の出遅れ一覧
            {selectedYear !== 'all' && (
              <Badge variant="outline" className="ml-2 text-xs font-normal">{selectedYear}年</Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-1.5">
            {([['all', '全件'], ['1m', '1ヶ月'], ['3m', '3ヶ月']] as const).map(([key, label]) => (
              <Button
                key={key}
                size="sm"
                variant={dateFilter === key ? 'default' : 'outline'}
                className="h-7 px-2 text-xs"
                onClick={() => { setDateFilter(key); setShowCount(200); }}
              >
                {label}
              </Button>
            ))}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {totalFiltered.toLocaleString()}件中 {filtered.length}件表示
        </p>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-muted-foreground border-b bg-muted/30 text-xs">
                <th className="text-left py-2 px-3">日付</th>
                <th className="text-left py-2 px-2">場所</th>
                <th className="text-right py-2 px-2">R</th>
                <th className="text-right py-2 px-2">馬番</th>
                <th className="text-left py-2 px-2">馬名</th>
                <th className="text-left py-2 px-2">騎手</th>
                <th className="text-right py-2 px-2">着順</th>
                <th className="text-left py-2 px-2">出遅れ内容</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((inc, i) => (
                <tr key={`${inc.date}-${inc.venue_name}-${inc.race_num}-${inc.umaban}-${i}`}
                    className="border-b border-gray-100 dark:border-gray-800 hover:bg-muted/20">
                  <td className="py-1.5 px-3 text-xs text-muted-foreground whitespace-nowrap">{inc.date}</td>
                  <td className="py-1.5 px-2">{inc.venue_name}</td>
                  <td className="text-right py-1.5 px-2 font-mono">{inc.race_num}</td>
                  <td className="text-right py-1.5 px-2 font-mono">{inc.umaban}</td>
                  <td className="py-1.5 px-2 font-medium">{inc.horse_name}</td>
                  <td className="py-1.5 px-2 text-muted-foreground">{inc.jockey_name}</td>
                  <td className={`text-right py-1.5 px-2 font-mono ${fpColor(inc.finish_position, inc.num_runners)}`}>
                    {inc.finish_position > 0 ? `${inc.finish_position}/${inc.num_runners}` : '-'}
                  </td>
                  <td className="py-1.5 px-2 text-xs text-muted-foreground max-w-[200px] truncate">
                    {inc.hassou_excerpt || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length < totalFiltered && (
          <div className="p-3 text-center">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCount(prev => prev + 200)}
              className="text-xs"
            >
              さらに表示 ({totalFiltered - filtered.length}件)
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================
// Tab 3: 馬の出遅れ履歴
// ============================================================

function HorseTab({ data, selectedYear }: { data: SlowStartData; selectedYear: string }) {
  const [query, setQuery] = useState('');
  const [minRaces, setMinRaces] = useState(3);
  const [expandedHorse, setExpandedHorse] = useState<string | null>(null);

  // 年フィルタ適用: year_stats を見て表示値を計算
  const displayHorses = useMemo(() => {
    let list = data.horse_stats;

    // 年フィルタ
    if (selectedYear !== 'all') {
      list = list.filter(h => {
        const ys = h.year_stats?.[selectedYear];
        return ys && ys.slow > 0;
      });
    }

    // 検索 or デフォルト
    if (query.trim()) {
      const q = query.trim();
      list = list.filter(h => h.horse_name.includes(q));
    } else {
      if (selectedYear === 'all') {
        list = list.filter(h => h.total_with_hassou >= minRaces);
      }
    }
    return list.slice(0, 100);
  }, [data.horse_stats, query, minRaces, selectedYear]);

  // 馬のインシデント取得（年フィルタ付き）
  const getIncidents = (kettoNum: string): Incident[] => {
    let list = data.recent_incidents.filter(inc => inc.ketto_num === kettoNum);
    if (selectedYear !== 'all') {
      list = list.filter(inc => inc.date.startsWith(selectedYear));
    }
    return list;
  };

  // 年別の表示値を取得
  const getDisplayStats = (h: HorseStat) => {
    if (selectedYear === 'all') {
      return {
        rate: h.slow_start_rate,
        slow: h.slow_count,
        total: h.total_with_hassou,
        avgFp: h.avg_finish_when_slow,
      };
    }
    const ys = h.year_stats?.[selectedYear];
    if (!ys) return { rate: 0, slow: 0, total: 0, avgFp: null };
    return {
      rate: ys.total > 0 ? ys.slow / ys.total : 0,
      slow: ys.slow,
      total: ys.total,
      avgFp: null, // 年別の平均着順はインシデントから計算可能だが省略
    };
  };

  return (
    <div className="space-y-4">
      {/* Search + Filter */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="馬名で検索..."
                className="w-full pl-10 pr-3 py-2 text-sm rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            {!query.trim() && selectedYear === 'all' && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground whitespace-nowrap">最低出走数:</span>
                {[3, 5, 10].map(n => (
                  <Button
                    key={n}
                    size="sm"
                    variant={minRaces === n ? 'default' : 'outline'}
                    className="h-7 px-2 text-xs"
                    onClick={() => setMinRaces(n)}
                  >
                    {n}+
                  </Button>
                ))}
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {query.trim()
              ? `「${query}」${displayHorses.length}件`
              : selectedYear !== 'all'
                ? `${selectedYear}年に出遅れのあった馬 ${displayHorses.length}頭`
                : `出遅れ率上位 ${displayHorses.length}頭 (出走${minRaces}回以上)`
            }
          </p>
        </CardContent>
      </Card>

      {/* Horse List */}
      <div className="space-y-2">
        {displayHorses.map(h => {
          const isExpanded = expandedHorse === h.ketto_num;
          const incidents = isExpanded ? getIncidents(h.ketto_num) : [];
          const stats = getDisplayStats(h);

          return (
            <Card key={h.ketto_num} className="overflow-hidden">
              <button
                className="w-full text-left px-4 py-3 hover:bg-muted/30 transition-colors"
                onClick={() => setExpandedHorse(isExpanded ? null : h.ketto_num)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-base">{h.horse_name}</span>
                    <Badge variant={stats.rate >= 0.30 ? 'destructive' : stats.rate >= 0.20 ? 'default' : 'secondary'}
                           className="text-xs">
                      {pct(stats.rate, 0)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      ({stats.slow}/{stats.total})
                    </span>
                    {selectedYear !== 'all' && h.slow_count !== stats.slow && (
                      <span className="text-xs text-muted-foreground">
                        通算: {h.slow_count}/{h.total_with_hassou}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    {stats.avgFp != null && (
                      <span className="text-muted-foreground">
                        出遅れ時平均 <span className="font-mono">{stats.avgFp.toFixed(1)}</span>着
                      </span>
                    )}
                    <TrendingDown className={`h-4 w-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="px-4 pb-3 border-t">
                  {incidents.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-3">インシデント詳細なし</p>
                  ) : (
                    <table className="w-full text-sm border-collapse mt-2">
                      <thead>
                        <tr className="text-muted-foreground text-xs border-b">
                          <th className="text-left py-1.5 pr-2">日付</th>
                          <th className="text-left py-1.5 px-2">場所</th>
                          <th className="text-right py-1.5 px-2">R</th>
                          <th className="text-left py-1.5 px-2">騎手</th>
                          <th className="text-right py-1.5 px-2">着順</th>
                          <th className="text-left py-1.5 pl-2">内容</th>
                        </tr>
                      </thead>
                      <tbody>
                        {incidents.map((inc, i) => (
                          <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                            <td className="py-1.5 pr-2 text-xs text-muted-foreground whitespace-nowrap">{inc.date}</td>
                            <td className="py-1.5 px-2">{inc.venue_name}</td>
                            <td className="text-right py-1.5 px-2 font-mono">{inc.race_num}</td>
                            <td className="py-1.5 px-2 text-muted-foreground">{inc.jockey_name}</td>
                            <td className={`text-right py-1.5 px-2 font-mono ${fpColor(inc.finish_position, inc.num_runners)}`}>
                              {inc.finish_position > 0 ? `${inc.finish_position}/${inc.num_runners}` : '-'}
                            </td>
                            <td className="py-1.5 pl-2 text-xs text-muted-foreground">{inc.hassou_excerpt || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {displayHorses.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            {query.trim() ? `「${query}」に該当する馬が見つかりません` : '該当する馬がありません'}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
