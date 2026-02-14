'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw, ChevronDown, ChevronRight, Users, Target, TrendingUp, Pencil, Check, X, Database, BarChart3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

// =============================================
// Types
// =============================================

interface MetricStats {
  sample_size: number;
  win_rate: number;
  top3_rate: number;
  top5_rate: number;
  avg_finish: number;
  avg_odds: number;
}

interface PopulationBucketAnalysis {
  by_lapRank: Record<string, MetricStats>;
  by_timeLevel: Record<string, MetricStats>;
  by_location: Record<string, MetricStats>;
  by_acceleration: Record<string, MetricStats>;
}

interface OverallAnalysis {
  by_lapRank: Record<string, MetricStats>;
  by_timeLevel: Record<string, MetricStats>;
  by_location: Record<string, MetricStats>;
  by_acceleration: Record<string, MetricStats>;
  by_intensity: Record<string, MetricStats>;
  by_awase: Record<string, MetricStats>;
  by_lapRank_x_location: Record<string, MetricStats>;
  by_timeLevel_x_acceleration: Record<string, MetricStats>;
  by_popularity_bucket: Record<string, PopulationBucketAnalysis>;
  total: MetricStats;
}

interface PatternStats {
  win_rate: number;
  top3_rate: number;
  top5_rate: number;
  avg_finish: number;
  sample_size: number;
  confidence: string;
  lift?: number;
  avg_odds?: number;
}

interface TrainerPattern {
  description: string;
  human_label?: string | null;
  conditions: Record<string, unknown>;
  stats: PatternStats;
}

interface TrainerInfo {
  jvn_code: string;
  name: string;
  tozai: string;
  comment: string;
  total_runners: number;
  overall_stats: {
    win_rate: number;
    top3_rate: number;
    top5_rate: number;
    avg_finish: number;
    sample_size: number;
  };
  best_patterns: TrainerPattern[];
  all_patterns: Record<string, Record<string, PatternStats>>;
}

interface ApiResponse {
  metadata?: {
    created_at: string;
    since: number;
    total_records: number;
    version: string;
  };
  overall?: OverallAnalysis;
  trainers: Record<string, TrainerInfo>;
  summary: {
    totalRecords: number;
    totalTrainers: number;
    trainersWithPatterns: number;
    avgTop3Rate: number;
    topTrainers: Array<{
      name: string;
      tozai: string;
      top3_rate: number;
      win_rate: number;
      sample_size: number;
      patternCount: number;
    }>;
  };
  error?: string;
  message?: string;
}

type SortKey = 'top3_rate' | 'win_rate' | 'total_runners' | 'name';

// =============================================
// Helpers
// =============================================

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function getTop3Color(rate: number): string {
  if (rate >= 0.35) return 'text-green-700 dark:text-green-400 font-bold';
  if (rate >= 0.28) return 'text-emerald-600 dark:text-emerald-400 font-semibold';
  if (rate >= 0.22) return 'text-amber-700 dark:text-amber-400';
  return '';
}

function getTop3BgColor(rate: number): string {
  if (rate >= 0.35) return 'bg-green-50 dark:bg-green-900/20';
  if (rate >= 0.28) return 'bg-emerald-50 dark:bg-emerald-900/10';
  return '';
}

function getLiftColor(lift: number): string {
  if (lift >= 0.05) return 'text-green-600';
  if (lift >= 0.02) return 'text-emerald-500';
  if (lift <= -0.03) return 'text-red-500';
  return 'text-gray-400';
}

function getConfidenceBadge(confidence: string) {
  switch (confidence) {
    case 'high':
      return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 text-[10px]">High</Badge>;
    case 'medium':
      return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200 text-[10px]">Med</Badge>;
    default:
      return <Badge variant="outline" className="bg-gray-50 text-gray-500 border-gray-200 text-[10px]">Low</Badge>;
  }
}

function formatConditions(conditions: Record<string, unknown>): string {
  const parts: string[] = [];
  if (conditions.finalLocation) parts.push(`場所:${conditions.finalLocation}`);
  if (conditions.acceleration) parts.push(`加速:${conditions.acceleration}`);
  if (conditions.hasGoodTime === true) parts.push('好タイム');
  if (conditions.finalLapClassGroup) {
    const groups = conditions.finalLapClassGroup as string[];
    parts.push(`ラップ:${groups.join('/')}`);
  }
  if (conditions.timeClass) parts.push(`時計:${conditions.timeClass}`);
  if (conditions.hasAwase === true) parts.push('併せ馬');
  if (conditions.intensity) parts.push(`脚色:${conditions.intensity}`);
  if (conditions.weekendHasGoodTime === true) parts.push('土日好タイム');
  if (conditions.weekendLocation) parts.push(`土日場所:${conditions.weekendLocation}`);
  if (conditions.weekendAcceleration) parts.push(`土日加速:${conditions.weekendAcceleration}`);
  return parts.join(' / ');
}

// lapRankの表示順序
const LAP_RANK_ORDER = ['SS', 'S+', 'S=', 'S-', 'A+', 'A=', 'A-', 'B+', 'B=', 'B-', 'C+', 'C=', 'C-', 'D+', 'D=', 'D-'];

function sortByLapRank(entries: [string, MetricStats][]): [string, MetricStats][] {
  return entries.sort((a, b) => {
    const ai = LAP_RANK_ORDER.indexOf(a[0]);
    const bi = LAP_RANK_ORDER.indexOf(b[0]);
    if (ai >= 0 && bi >= 0) return ai - bi;
    if (ai >= 0) return -1;
    if (bi >= 0) return 1;
    return 0;
  });
}

// =============================================
// Tab 1: Overall Training Analysis
// =============================================

function MetricTable({
  title,
  data,
  overallRate,
  sortFn,
  nameLabel,
}: {
  title: string;
  data: Record<string, MetricStats>;
  overallRate: number;
  sortFn?: (entries: [string, MetricStats][]) => [string, MetricStats][];
  nameLabel?: string;
}) {
  let entries = Object.entries(data);
  if (sortFn) {
    entries = sortFn(entries);
  } else {
    entries.sort((a, b) => b[1].top3_rate - a[1].top3_rate);
  }

  if (entries.length === 0) return null;

  return (
    <Card>
      <CardHeader className="p-3 pb-2">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-3 pt-0">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="text-muted-foreground border-b">
              <th className="text-left py-1 pr-2">{nameLabel || '分類'}</th>
              <th className="text-right py-1 px-1.5">好走率</th>
              <th className="text-right py-1 px-1.5">勝率</th>
              <th className="text-right py-1 px-1.5">平均着</th>
              <th className="text-right py-1 px-1.5">平均OP</th>
              <th className="text-right py-1 px-1.5">リフト</th>
              <th className="text-right py-1 pl-1.5">n</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, stats]) => {
              const lift = stats.top3_rate - overallRate;
              return (
                <tr key={key} className={`border-b border-gray-100 dark:border-gray-800 ${getTop3BgColor(stats.top3_rate)}`}>
                  <td className="py-1 pr-2 font-medium">{key}</td>
                  <td className={`text-right py-1 px-1.5 font-mono ${getTop3Color(stats.top3_rate)}`}>
                    {pct(stats.top3_rate)}
                  </td>
                  <td className="text-right py-1 px-1.5 font-mono">{pct(stats.win_rate)}</td>
                  <td className="text-right py-1 px-1.5 font-mono">{stats.avg_finish.toFixed(1)}</td>
                  <td className="text-right py-1 px-1.5 font-mono text-muted-foreground">{stats.avg_odds.toFixed(0)}</td>
                  <td className={`text-right py-1 px-1.5 font-mono ${getLiftColor(lift)}`}>
                    {lift >= 0 ? '+' : ''}{(lift * 100).toFixed(1)}
                  </td>
                  <td className="text-right py-1 pl-1.5 font-mono text-muted-foreground">{stats.sample_size.toLocaleString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function OverallTrainingTab({ overall }: { overall: OverallAnalysis }) {
  const [popFilter, setPopFilter] = useState<string>('all');
  const overallRate = overall.total.top3_rate;

  // 人気フィルタ適用
  const getFilteredData = (key: keyof PopulationBucketAnalysis): Record<string, MetricStats> => {
    if (popFilter === 'all') {
      return (overall as unknown as Record<string, Record<string, MetricStats>>)[key] || {};
    }
    const bucket = overall.by_popularity_bucket[popFilter];
    return bucket ? (bucket[key] || {}) : {};
  };

  return (
    <div className="space-y-6">
      {/* 全体サマリ */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xl font-bold">{overall.total.sample_size.toLocaleString()}</div>
            <div className="text-[10px] text-muted-foreground">総レコード</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xl font-bold">{pct(overall.total.win_rate)}</div>
            <div className="text-[10px] text-muted-foreground">全体勝率</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xl font-bold">{pct(overall.total.top3_rate)}</div>
            <div className="text-[10px] text-muted-foreground">全体好走率</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xl font-bold">{overall.total.avg_finish.toFixed(1)}</div>
            <div className="text-[10px] text-muted-foreground">平均着順</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xl font-bold">{overall.total.avg_odds.toFixed(0)}</div>
            <div className="text-[10px] text-muted-foreground">平均オッズ</div>
          </CardContent>
        </Card>
      </div>

      {/* 人気帯フィルタ */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">人気帯:</span>
        {['all', '1-3', '4-6', '7-9', '10+'].map((v) => (
          <Button
            key={v}
            size="sm"
            variant={popFilter === v ? 'default' : 'outline'}
            className="h-7 px-2 text-xs"
            onClick={() => setPopFilter(v)}
          >
            {v === 'all' ? '全体' : `${v}番人気`}
          </Button>
        ))}
      </div>

      {/* メイン分析テーブル群 */}
      <div className="space-y-4">
        {/* lapRank */}
        <MetricTable
          title="ラップランク別 好走率"
          data={getFilteredData('by_lapRank')}
          overallRate={overallRate}
          sortFn={sortByLapRank}
          nameLabel="ランク"
        />

        {/* タイムレベル */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricTable
            title="タイムレベル別 好走率"
            data={getFilteredData('by_timeLevel')}
            overallRate={overallRate}
            sortFn={(entries) => entries.sort((a, b) => Number(b[0]) - Number(a[0]))}
            nameLabel="Lv"
          />
          <MetricTable
            title="調教場所別 好走率"
            data={getFilteredData('by_location')}
            overallRate={overallRate}
            nameLabel="場所"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricTable
            title="加速パターン別 好走率"
            data={getFilteredData('by_acceleration')}
            overallRate={overallRate}
            nameLabel="パターン"
          />
          {popFilter === 'all' && (
            <MetricTable
              title="脚色別 好走率"
              data={overall.by_intensity}
              overallRate={overallRate}
              nameLabel="脚色"
            />
          )}
        </div>

        {popFilter === 'all' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <MetricTable
              title="併せ馬効果"
              data={overall.by_awase}
              overallRate={overallRate}
              nameLabel=""
            />
          </div>
        )}

        {/* 交差分析 (全体のみ) */}
        {popFilter === 'all' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-muted-foreground">交差分析</h3>
            <MetricTable
              title="ラップランク x 場所"
              data={overall.by_lapRank_x_location}
              overallRate={overallRate}
              nameLabel="組合せ"
            />
            <MetricTable
              title="タイムレベル x 加速パターン"
              data={overall.by_timeLevel_x_acceleration}
              overallRate={overallRate}
              nameLabel="組合せ"
            />
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================
// Tab 2: Trainer Training Analysis
// =============================================

function TrainerDetailRow({ trainer }: { trainer: TrainerInfo }) {
  const [expanded, setExpanded] = useState(false);
  const [comment, setComment] = useState(trainer.comment || '');

  return (
    <>
      <tr
        className="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-2 border text-center">
          {expanded
            ? <ChevronDown className="w-4 h-4 inline" />
            : <ChevronRight className="w-4 h-4 inline" />}
        </td>
        <td className="px-3 py-2 border font-medium text-sm">
          {trainer.name}
          {trainer.best_patterns.some(p => p.human_label) && (
            <span className="text-amber-500 ml-1">★</span>
          )}
        </td>
        <td className="px-3 py-2 border text-center text-xs">
          <Badge variant="secondary" className="text-[10px]">
            {trainer.tozai || '-'}
          </Badge>
        </td>
        <td className="px-3 py-2 border text-center text-sm font-mono">
          {trainer.total_runners}
        </td>
        <td className="px-3 py-2 border text-center text-sm font-mono">
          {pct(trainer.overall_stats.win_rate)}
        </td>
        <td className={`px-3 py-2 border text-center text-sm font-mono ${getTop3Color(trainer.overall_stats.top3_rate)}`}>
          {pct(trainer.overall_stats.top3_rate)}
        </td>
        <td className="px-3 py-2 border text-center text-sm font-mono">
          {trainer.overall_stats.avg_finish.toFixed(1)}
        </td>
        <td className="px-3 py-2 border text-center text-sm">
          {trainer.best_patterns.length > 0 ? (
            <Badge variant="outline">{trainer.best_patterns.length}</Badge>
          ) : (
            <span className="text-gray-400">-</span>
          )}
        </td>
        <td className="px-3 py-2 border text-xs max-w-48 truncate">
          {trainer.best_patterns[0]
            ? (trainer.best_patterns[0].human_label || trainer.best_patterns[0].description)
            : <span className="text-gray-400">-</span>}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={9} className="p-0 border">
            <TrainerDetailPanel
              trainer={trainer}
              comment={comment}
              onCommentSaved={setComment}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function TrainerDetailPanel({
  trainer,
  comment,
  onCommentSaved,
}: {
  trainer: TrainerInfo;
  comment: string;
  onCommentSaved: (newComment: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(comment);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch('/api/admin/trainer-patterns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jvnCode: trainer.jvn_code, comment: editText }),
      });
      if (res.ok) {
        onCommentSaved(editText);
        setEditing(false);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditText(comment);
    setEditing(false);
  };

  return (
    <div className="p-4 bg-slate-50 dark:bg-slate-900/50 space-y-4">
      {/* ベストパターン */}
      {trainer.best_patterns.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-2">勝負パターン</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {trainer.best_patterns.map((pattern, i) => (
              <Card key={i} className={getTop3BgColor(pattern.stats.top3_rate)}>
                <CardContent className="p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">
                      {pattern.human_label && <span className="text-amber-500 mr-1">★</span>}
                      {pattern.human_label || pattern.description}
                    </span>
                    {getConfidenceBadge(pattern.stats.confidence)}
                  </div>
                  {pattern.human_label && pattern.description !== pattern.human_label && (
                    <div className="text-xs text-muted-foreground">{pattern.description}</div>
                  )}
                  <div className="text-xs text-muted-foreground">
                    {formatConditions(pattern.conditions)}
                  </div>
                  <div className="flex gap-3 text-xs font-mono">
                    <span>勝率: <strong>{pct(pattern.stats.win_rate)}</strong></span>
                    <span>好走率: <strong className={getTop3Color(pattern.stats.top3_rate)}>{pct(pattern.stats.top3_rate)}</strong></span>
                    <span>{pattern.stats.sample_size}走</span>
                    {pattern.stats.lift != null && (
                      <span className={getLiftColor(pattern.stats.lift)}>
                        {pattern.stats.lift >= 0 ? '+' : ''}{(pattern.stats.lift * 100).toFixed(1)}pt
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* 調教師コメント */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h4 className="text-sm font-semibold">調教師コメント</h4>
          {!editing && (
            <button
              onClick={() => { setEditText(comment); setEditing(true); }}
              className="text-muted-foreground hover:text-foreground"
              title="コメントを編集"
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        {editing ? (
          <div className="space-y-2">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full text-xs p-2 rounded border bg-white dark:bg-gray-800 min-h-[80px] resize-y focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="調教師メモを入力..."
              autoFocus
            />
            <div className="flex gap-2">
              <Button size="sm" className="h-7 px-3 text-xs gap-1" onClick={handleSave} disabled={saving}>
                <Check className="w-3.5 h-3.5" />
                {saving ? '保存中...' : '保存'}
              </Button>
              <Button size="sm" variant="outline" className="h-7 px-3 text-xs gap-1" onClick={handleCancel} disabled={saving}>
                <X className="w-3.5 h-3.5" />
                キャンセル
              </Button>
            </div>
          </div>
        ) : (
          comment ? (
            <p className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap bg-white dark:bg-gray-800 p-2 rounded border">
              {comment}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              コメントなし
            </p>
          )
        )}
      </div>

      {/* 分類別統計 */}
      {trainer.all_patterns && Object.keys(trainer.all_patterns).length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-2">分類別統計</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(trainer.all_patterns).map(([category, groups]) => (
              <BreakdownTable
                key={category}
                title={getCategoryLabel(category)}
                groups={groups}
                overallTop3={trainer.overall_stats.top3_rate}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function getCategoryLabel(key: string): string {
  const labels: Record<string, string> = {
    by_final_lap: 'ラップ分類別',
    by_location: '調教場所別',
    by_volume: '調教本数別',
    by_time_class: 'タイム分類別',
    by_acceleration: '加速パターン別',
  };
  return labels[key] || key;
}

function BreakdownTable({
  title,
  groups,
  overallTop3,
}: {
  title: string;
  groups: Record<string, PatternStats>;
  overallTop3: number;
}) {
  const sorted = Object.entries(groups).sort(
    (a, b) => b[1].top3_rate - a[1].top3_rate
  );

  return (
    <Card>
      <CardHeader className="p-2 pb-1">
        <CardTitle className="text-xs font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-2 pt-0">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="text-left py-0.5">分類</th>
              <th className="text-right py-0.5">好走率</th>
              <th className="text-right py-0.5">勝率</th>
              <th className="text-right py-0.5">走数</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(([key, stats]) => {
              const diff = stats.top3_rate - overallTop3;
              return (
                <tr key={key} className={getTop3BgColor(stats.top3_rate)}>
                  <td className="py-0.5 font-medium">{key}</td>
                  <td className={`text-right py-0.5 font-mono ${getTop3Color(stats.top3_rate)}`}>
                    {pct(stats.top3_rate)}
                    {diff > 0.03 && <span className="text-green-600 ml-0.5">+</span>}
                  </td>
                  <td className="text-right py-0.5 font-mono">{pct(stats.win_rate)}</td>
                  <td className="text-right py-0.5 font-mono text-muted-foreground">{stats.sample_size}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function TrainerTrainingTab({
  trainers,
  summary,
}: {
  trainers: Record<string, TrainerInfo>;
  summary: ApiResponse['summary'];
}) {
  const [sortKey, setSortKey] = useState<SortKey>('top3_rate');
  const [filterTozai, setFilterTozai] = useState<string>('all');
  const [filterPatternsOnly, setFilterPatternsOnly] = useState(false);

  const trainerList = useMemo(() => {
    let list = Object.values(trainers) as TrainerInfo[];

    if (filterTozai !== 'all') {
      list = list.filter((t) => t.tozai === filterTozai);
    }
    if (filterPatternsOnly) {
      list = list.filter((t) => t.best_patterns && t.best_patterns.length > 0);
    }

    list.sort((a, b) => {
      switch (sortKey) {
        case 'top3_rate':
          return (b.overall_stats?.top3_rate || 0) - (a.overall_stats?.top3_rate || 0);
        case 'win_rate':
          return (b.overall_stats?.win_rate || 0) - (a.overall_stats?.win_rate || 0);
        case 'total_runners':
          return (b.total_runners || 0) - (a.total_runners || 0);
        case 'name':
          return a.name.localeCompare(b.name, 'ja');
        default:
          return 0;
      }
    });

    return list;
  }, [trainers, sortKey, filterTozai, filterPatternsOnly]);

  // パターン別集計
  const patternGroups = useMemo(() => {
    const groups = new Map<string, Array<{ trainer: TrainerInfo; pattern: TrainerPattern }>>();

    for (const trainer of Object.values(trainers) as TrainerInfo[]) {
      for (const pattern of trainer.best_patterns || []) {
        const key = pattern.description;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push({ trainer, pattern });
      }
    }

    return Array.from(groups.entries())
      .map(([description, items]) => ({
        description,
        items: items.sort((a, b) => b.pattern.stats.top3_rate - a.pattern.stats.top3_rate),
      }))
      .sort((a, b) => b.items.length - a.items.length);
  }, [trainers]);

  return (
    <div className="space-y-4">
      {/* サマリカード */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Users className="h-8 w-8 text-blue-500" />
            <div>
              <div className="text-2xl font-bold">{summary.totalTrainers}</div>
              <div className="text-xs text-muted-foreground">分析対象調教師</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Target className="h-8 w-8 text-amber-500" />
            <div>
              <div className="text-2xl font-bold">{summary.trainersWithPatterns}</div>
              <div className="text-xs text-muted-foreground">パターン検出調教師</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <TrendingUp className="h-8 w-8 text-green-500" />
            <div>
              <div className="text-2xl font-bold">{pct(summary.avgTop3Rate)}</div>
              <div className="text-xs text-muted-foreground">平均好走率</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* サブタブ: 調教師一覧 / パターン別 */}
      <Tabs defaultValue="trainers-list">
        <TabsList>
          <TabsTrigger value="trainers-list">調教師一覧</TabsTrigger>
          <TabsTrigger value="by-pattern">パターン別</TabsTrigger>
        </TabsList>

        <TabsContent value="trainers-list" className="mt-4 space-y-3">
          {/* フィルタ・ソート */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-sm">
              <span className="text-muted-foreground">所属:</span>
              {['all', '栗東', '美浦'].map((v) => (
                <Button
                  key={v}
                  size="sm"
                  variant={filterTozai === v ? 'default' : 'outline'}
                  className="h-7 px-2 text-xs"
                  onClick={() => setFilterTozai(v)}
                >
                  {v === 'all' ? '全て' : v}
                </Button>
              ))}
            </div>
            <div className="flex items-center gap-1.5 text-sm">
              <Button
                size="sm"
                variant={filterPatternsOnly ? 'default' : 'outline'}
                className="h-7 px-2 text-xs"
                onClick={() => setFilterPatternsOnly(!filterPatternsOnly)}
              >
                パターンあり
              </Button>
            </div>
            <div className="flex items-center gap-1.5 text-sm ml-auto">
              <span className="text-muted-foreground">ソート:</span>
              {([
                ['top3_rate', '好走率'],
                ['win_rate', '勝率'],
                ['total_runners', '出走数'],
                ['name', '名前'],
              ] as [SortKey, string][]).map(([key, label]) => (
                <Button
                  key={key}
                  size="sm"
                  variant={sortKey === key ? 'default' : 'outline'}
                  className="h-7 px-2 text-xs"
                  onClick={() => setSortKey(key)}
                >
                  {label}
                </Button>
              ))}
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            {trainerList.length}名表示 / {summary.totalTrainers}名中
          </div>

          <div className="overflow-x-auto border rounded-lg">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 dark:bg-gray-800">
                  <th className="px-3 py-2 border w-8"></th>
                  <th className="px-3 py-2 border text-left min-w-28">調教師</th>
                  <th className="px-3 py-2 border text-center w-16">所属</th>
                  <th className="px-3 py-2 border text-center w-16">出走数</th>
                  <th className="px-3 py-2 border text-center w-16">勝率</th>
                  <th className="px-3 py-2 border text-center w-16">好走率</th>
                  <th className="px-3 py-2 border text-center w-16">平均着</th>
                  <th className="px-3 py-2 border text-center w-16">PT数</th>
                  <th className="px-3 py-2 border text-left min-w-40">ベストパターン</th>
                </tr>
              </thead>
              <tbody>
                {trainerList.map((trainer) => (
                  <TrainerDetailRow key={trainer.jvn_code} trainer={trainer} />
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="by-pattern" className="mt-4 space-y-4">
          {patternGroups.map((group) => (
            <Card key={group.description}>
              <CardHeader className="p-3 pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  {group.description}
                  <Badge variant="secondary" className="text-[10px]">
                    {group.items.length}名
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-0">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="text-muted-foreground">
                      <th className="text-left py-1 pr-2">調教師</th>
                      <th className="text-center py-1 px-2">所属</th>
                      <th className="text-right py-1 px-2">好走率</th>
                      <th className="text-right py-1 px-2">勝率</th>
                      <th className="text-right py-1 px-2">走数</th>
                      <th className="text-right py-1 px-2">リフト</th>
                      <th className="text-center py-1 px-2">信頼度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.items.map(({ trainer, pattern }) => (
                      <tr key={trainer.jvn_code} className={`border-t ${getTop3BgColor(pattern.stats.top3_rate)}`}>
                        <td className="py-1 pr-2 font-medium">
                          {trainer.name}
                          {pattern.human_label && <span className="text-amber-500 ml-0.5">★</span>}
                        </td>
                        <td className="text-center py-1 px-2">{trainer.tozai || '-'}</td>
                        <td className={`text-right py-1 px-2 font-mono ${getTop3Color(pattern.stats.top3_rate)}`}>
                          {pct(pattern.stats.top3_rate)}
                        </td>
                        <td className="text-right py-1 px-2 font-mono">{pct(pattern.stats.win_rate)}</td>
                        <td className="text-right py-1 px-2 font-mono">{pattern.stats.sample_size}</td>
                        <td className={`text-right py-1 px-2 font-mono ${getLiftColor(pattern.stats.lift || 0)}`}>
                          {pattern.stats.lift != null ? `${pattern.stats.lift >= 0 ? '+' : ''}${(pattern.stats.lift * 100).toFixed(1)}` : '-'}
                        </td>
                        <td className="text-center py-1 px-2">{getConfidenceBadge(pattern.stats.confidence)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// =============================================
// Main Page
// =============================================

export default function TrainingAnalysisPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/trainer-patterns');
      const result = await res.json();
      if (!res.ok) {
        setError(result.message || 'データ取得に失敗しました');
        return;
      }
      setData(result);
    } catch {
      setError('データ取得に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-center py-16 gap-3">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="text-muted-foreground">読み込み中...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
          <Link href="/" className="hover:underline flex items-center gap-1">
            <ArrowLeft className="h-4 w-4" />
            トップ
          </Link>
          <span>/</span>
          <span className="text-foreground">調教分析</span>
        </div>
        <Card className="bg-amber-50 dark:bg-amber-950/30 border-amber-200">
          <CardContent className="p-6 text-center">
            <p className="text-amber-800 dark:text-amber-200 font-medium mb-2">{error}</p>
            <p className="text-amber-600 dark:text-amber-400 text-sm">
              管理画面 → データ分析 → 「調教分析」を実行してください
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  const { summary, metadata, overall } = data;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* ヘッダー */}
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
          <Link href="/" className="hover:underline flex items-center gap-1">
            <ArrowLeft className="h-4 w-4" />
            トップ
          </Link>
          <span>/</span>
          <span className="text-foreground">調教分析</span>
        </div>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">調教分析</h1>
          <Button variant="outline" size="sm" onClick={fetchData} className="gap-1.5">
            <RefreshCw className="h-4 w-4" />
            更新
          </Button>
        </div>
        {metadata && (
          <p className="text-sm text-muted-foreground mt-1">
            対象期間: {metadata.since}年~ / レコード: {metadata.total_records?.toLocaleString()} / 生成: {metadata.created_at?.slice(0, 10)}
          </p>
        )}
      </div>

      {/* メインタブ */}
      <Tabs defaultValue="training">
        <TabsList>
          <TabsTrigger value="training" className="gap-1.5">
            <BarChart3 className="h-4 w-4" />
            調教分析
          </TabsTrigger>
          <TabsTrigger value="trainers" className="gap-1.5">
            <Database className="h-4 w-4" />
            調教 x 調教師
          </TabsTrigger>
        </TabsList>

        <TabsContent value="training" className="mt-4">
          {overall ? (
            <OverallTrainingTab overall={overall} />
          ) : (
            <Card>
              <CardContent className="p-6 text-center text-muted-foreground">
                全体調教分析データがありません。新形式の分析を実行してください。
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="trainers" className="mt-4">
          <TrainerTrainingTab trainers={data.trainers} summary={summary} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
