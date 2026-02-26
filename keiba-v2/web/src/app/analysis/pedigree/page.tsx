'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw, Search, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

// ============================================================
// Types
// ============================================================

interface SireEntry {
  id: string;
  name: string;
  total_runs: number;
  wins: number;
  top3: number;
  win_rate: number;
  top3_rate: number;
  // H3/H4
  fresh_advantage?: number;
  tight_penalty?: number;
  // H5
  sprint_top3_rate?: number;
  sustained_top3_rate?: number;
  finish_type_pref?: number;
  // H6
  young_top3_rate?: number;
  mature_top3_rate?: number;
  maturity_index?: number;
}

interface Meta {
  total_races: number;
  total_entries: number;
  unique_sires: number;
  unique_bms: number;
  built_at: string;
}

interface PedigreeData {
  sire: Record<string, Record<string, unknown>>;
  bms: Record<string, Record<string, unknown>>;
  meta: Meta;
}

// ============================================================
// Helpers
// ============================================================

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(digits)}%`;
}

function signed(v: number | null | undefined, digits = 1): string {
  if (v == null) return '-';
  const p = (v * 100).toFixed(digits);
  return v >= 0 ? `+${p}%` : `${p}%`;
}

function rateColor(rate: number): string {
  if (rate >= 0.35) return 'text-emerald-600 dark:text-emerald-400 font-bold';
  if (rate >= 0.30) return 'text-green-600 dark:text-green-400';
  if (rate <= 0.15) return 'text-red-500 dark:text-red-400';
  return '';
}

function diffColor(v: number | null | undefined): string {
  if (v == null) return 'text-muted-foreground';
  if (v >= 0.05) return 'text-emerald-600 dark:text-emerald-400 font-bold';
  if (v >= 0.02) return 'text-green-600 dark:text-green-400';
  if (v <= -0.05) return 'text-red-600 dark:text-red-400 font-bold';
  if (v <= -0.02) return 'text-orange-600 dark:text-orange-400';
  return 'text-muted-foreground';
}

function toEntries(raw: Record<string, Record<string, unknown>>): SireEntry[] {
  return Object.entries(raw).map(([id, v]) => ({
    id,
    name: (v.name as string) || id,
    total_runs: (v.total_runs as number) || 0,
    wins: (v.wins as number) || 0,
    top3: (v.top3 as number) || 0,
    win_rate: (v.win_rate as number) || 0,
    top3_rate: (v.top3_rate as number) || 0,
    fresh_advantage: v.fresh_advantage as number | undefined,
    tight_penalty: v.tight_penalty as number | undefined,
    sprint_top3_rate: v.sprint_top3_rate as number | undefined,
    sustained_top3_rate: v.sustained_top3_rate as number | undefined,
    finish_type_pref: v.finish_type_pref as number | undefined,
    young_top3_rate: v.young_top3_rate as number | undefined,
    mature_top3_rate: v.mature_top3_rate as number | undefined,
    maturity_index: v.maturity_index as number | undefined,
  }));
}

// ============================================================
// Main Page
// ============================================================

export default function PedigreeAnalysisPage() {
  const [data, setData] = useState<PedigreeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/pedigree');
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

  const sireEntries = toEntries(data.sire);
  const bmsEntries = toEntries(data.bms);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Breadcrumb + Title */}
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
          <Link href="/" className="hover:underline flex items-center gap-1">
            <ArrowLeft className="h-4 w-4" />トップ
          </Link>
          <span>/</span>
          <span className="text-foreground">血統分析</span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">血統分析</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {data.meta.total_races.toLocaleString()}レース |
              {' '}{data.meta.unique_sires.toLocaleString()}種牡馬 |
              {' '}{data.meta.unique_bms.toLocaleString()}母父 |
              {' '}構築: {data.meta.built_at?.slice(0, 10)}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchData} className="gap-1.5">
            <RefreshCw className="h-4 w-4" />更新
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="sire">
        <TabsList>
          <TabsTrigger value="sire" className="gap-1.5">
            <TrendingUp className="h-4 w-4" />種牡馬
          </TabsTrigger>
          <TabsTrigger value="bms" className="gap-1.5">
            <TrendingDown className="h-4 w-4" />母父
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sire" className="mt-4">
          <RankingTable entries={sireEntries} label="種牡馬" />
        </TabsContent>
        <TabsContent value="bms" className="mt-4">
          <RankingTable entries={bmsEntries} label="母父" />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ============================================================
// Ranking Table Component
// ============================================================

type SortKey = 'top3_rate' | 'win_rate' | 'total_runs' | 'maturity_index' | 'fresh_advantage' | 'tight_penalty' | 'finish_type_pref';

function RankingTable({ entries, label }: { entries: SireEntry[]; label: string }) {
  const [minRuns, setMinRuns] = useState(50);
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('top3_rate');
  const [sortAsc, setSortAsc] = useState(false);
  const [showCount, setShowCount] = useState(100);

  const filtered = useMemo(() => {
    let list = entries;

    // 検索フィルタ
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(e => e.name.toLowerCase().includes(q) || e.id.includes(q));
    }

    // 最低出走数フィルタ
    list = list.filter(e => e.total_runs >= minRuns);

    // ソート
    list = [...list].sort((a, b) => {
      const va = a[sortKey] ?? (sortAsc ? 999 : -999);
      const vb = b[sortKey] ?? (sortAsc ? 999 : -999);
      return sortAsc ? (va as number) - (vb as number) : (vb as number) - (va as number);
    });

    return list;
  }, [entries, query, minRuns, sortKey, sortAsc]);

  const displayed = filtered.slice(0, showCount);

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
    return sortAsc ? ' \u25B2' : ' \u25BC';
  };

  const thClass = 'text-right py-2 px-2 cursor-pointer hover:text-foreground select-none whitespace-nowrap';

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-lg">{label}ランキング</CardTitle>
          <div className="flex items-center gap-3">
            {/* 検索 */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setShowCount(100); }}
                placeholder={`${label}名で検索...`}
                className="pl-8 pr-3 py-1.5 text-sm rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-ring w-48"
              />
            </div>
            {/* 最低出走数 */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">出走数:</span>
              {[30, 50, 100, 200, 500].map(n => (
                <Button
                  key={n}
                  size="sm"
                  variant={minRuns === n ? 'default' : 'outline'}
                  className="h-7 px-2 text-xs"
                  onClick={() => { setMinRuns(n); setShowCount(100); }}
                >
                  {n}+
                </Button>
              ))}
            </div>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {filtered.length.toLocaleString()}{label} |
          {' '}表示: {displayed.length} |
          {' '}ヘッダークリックでソート
        </p>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-muted-foreground border-b bg-muted/30 text-xs">
                <th className="text-left py-2 px-3 w-8">#</th>
                <th className="text-left py-2 px-2">{label}名</th>
                <th className={thClass} onClick={() => handleSort('total_runs')}>
                  出走数{sortIcon('total_runs')}
                </th>
                <th className={thClass} onClick={() => handleSort('win_rate')}>
                  勝率{sortIcon('win_rate')}
                </th>
                <th className={thClass} onClick={() => handleSort('top3_rate')}>
                  複勝率{sortIcon('top3_rate')}
                </th>
                <th className={thClass} onClick={() => handleSort('maturity_index')}>
                  <span title="正=晩成型, 負=早熟型">成長曲線{sortIcon('maturity_index')}</span>
                </th>
                <th className={thClass} onClick={() => handleSort('fresh_advantage')}>
                  <span title="休み明け(8週+)と通常の複勝率差">休み明け{sortIcon('fresh_advantage')}</span>
                </th>
                <th className={thClass} onClick={() => handleSort('tight_penalty')}>
                  <span title="間隔詰め(3週内)と通常の複勝率差">詰め使い{sortIcon('tight_penalty')}</span>
                </th>
                <th className={thClass} onClick={() => handleSort('finish_type_pref')}>
                  <span title="瞬発レース率-持続レース率">瞬発/持続{sortIcon('finish_type_pref')}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((e, i) => (
                <tr key={e.id} className="border-b border-gray-100 dark:border-gray-800 hover:bg-muted/20">
                  <td className="py-1.5 px-3 text-muted-foreground text-xs">{i + 1}</td>
                  <td className="py-1.5 px-2 font-medium whitespace-nowrap">
                    {e.name}
                    <span className="text-xs text-muted-foreground ml-1.5">
                      ({e.wins}-{e.top3 - e.wins}-{e.total_runs - e.top3})
                    </span>
                  </td>
                  <td className="text-right py-1.5 px-2 font-mono text-muted-foreground">
                    {e.total_runs.toLocaleString()}
                  </td>
                  <td className="text-right py-1.5 px-2 font-mono">
                    {pct(e.win_rate)}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono ${rateColor(e.top3_rate)}`}>
                    {pct(e.top3_rate)}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono ${diffColor(e.maturity_index)}`}>
                    {signed(e.maturity_index)}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono ${diffColor(e.fresh_advantage)}`}>
                    {signed(e.fresh_advantage)}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono ${diffColor(e.tight_penalty)}`}>
                    {signed(e.tight_penalty)}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono ${diffColor(e.finish_type_pref)}`}>
                    {signed(e.finish_type_pref)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {displayed.length < filtered.length && (
          <div className="p-3 text-center">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCount(prev => prev + 100)}
              className="text-xs"
            >
              さらに表示 ({(filtered.length - displayed.length).toLocaleString()}件)
            </Button>
          </div>
        )}
      </CardContent>

      {/* 凡例 */}
      <div className="px-4 pb-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>複勝率: ベイズ平滑化済み</span>
        <span>成長曲線: 正=晩成型, 負=早熟型</span>
        <span>休み明け: 8週以上 vs 通常</span>
        <span>詰め使い: 3週以内 vs 通常</span>
        <span>瞬発/持続: RPCI{'\u2265'}53 vs {'\u2264'}49</span>
      </div>
    </Card>
  );
}
