'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw, ChevronDown, ChevronRight, Users, Target, TrendingUp, Pencil, Check, X } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

// =============================================
// Types
// =============================================

interface PatternStats {
  win_rate: number;
  top3_rate: number;
  top5_rate: number;
  avg_finish: number;
  sample_size: number;
  confidence: string;
  lift?: number;
}

interface TrainerPattern {
  description: string;
  human_label?: string | null;
  conditions: Record<string, unknown>;
  stats: PatternStats;
}

interface TrainerInfo {
  jvn_code: string;
  keibabook_ids: string[];
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
  meta?: {
    created_at: string;
    data_period: string;
    total_trainers: number;
    version: string;
  };
  trainers: Record<string, TrainerInfo>;
  summary: {
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

function getTop3Color(rate: number): string {
  if (rate >= 0.35) return 'text-green-700 dark:text-green-400 font-bold';
  if (rate >= 0.25) return 'text-amber-700 dark:text-amber-400 font-semibold';
  return '';
}

function getTop3BgColor(rate: number): string {
  if (rate >= 0.35) return 'bg-green-50 dark:bg-green-900/20';
  if (rate >= 0.25) return 'bg-amber-50 dark:bg-amber-900/20';
  return '';
}

function formatConditions(conditions: Record<string, unknown>): string {
  const parts: string[] = [];
  if (conditions.finalLocation) parts.push(`場所:${conditions.finalLocation}`);
  if (conditions.acceleration) parts.push(`加速:${conditions.acceleration}`);
  if (conditions.hasGoodTime === true) parts.push('好タイム');
  if (conditions.hasGoodTime === false) parts.push('好タイムなし');
  if (conditions.finalLapClassGroup) {
    const groups = conditions.finalLapClassGroup as string[];
    parts.push(`ラップ:${groups.join('/')}`);
  }
  if (conditions.timeClass) parts.push(`時計:${conditions.timeClass}`);
  // 1週前
  if (conditions.weekAgoHasGoodTime === true) parts.push('1週前好タイム');
  if (conditions.weekAgoLocation) parts.push(`1週前場所:${conditions.weekAgoLocation}`);
  if (conditions.weekAgoAcceleration) parts.push(`1週前加速:${conditions.weekAgoAcceleration}`);
  if (conditions.weekAgoLapClassGroup) {
    const groups = conditions.weekAgoLapClassGroup as string[];
    parts.push(`1週前ラップ:${groups.join('/')}`);
  }
  // 土日
  if (conditions.weekendHasGoodTime === true) parts.push('土日好タイム');
  if (conditions.weekendLocation) parts.push(`土日場所:${conditions.weekendLocation}`);
  if (conditions.weekendAcceleration) parts.push(`土日加速:${conditions.weekendAcceleration}`);
  if (conditions.weekendLapClassGroup) {
    const groups = conditions.weekendLapClassGroup as string[];
    parts.push(`土日ラップ:${groups.join('/')}`);
  }
  return parts.join(' / ');
}

// =============================================
// Components
// =============================================

function TrainerDetailRow({ trainer }: { trainer: TrainerInfo }) {
  const [expanded, setExpanded] = useState(false);
  const [comment, setComment] = useState(trainer.comment || '');

  const handleCommentSaved = (newComment: string) => {
    setComment(newComment);
  };

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
            {trainer.tozai}
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
              onCommentSaved={handleCommentSaved}
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
                      <span className="text-green-600">+{(pattern.stats.lift * 100).toFixed(1)}pt</span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* 調教師コメント（編集可能） */}
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
              コメントなし（ペンアイコンをクリックして追加）
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

// =============================================
// Main Page
// =============================================

export default function TrainerPatternsPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('top3_rate');
  const [filterTozai, setFilterTozai] = useState<string>('all');
  const [filterPatternsOnly, setFilterPatternsOnly] = useState(false);

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

  // 調教師一覧のフィルタ+ソート
  const trainerList = useMemo(() => {
    if (!data?.trainers) return [];
    let list = Object.values(data.trainers) as TrainerInfo[];

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
  }, [data, sortKey, filterTozai, filterPatternsOnly]);

  // パターン別集計
  const patternGroups = useMemo(() => {
    if (!data?.trainers) return [];
    const groups = new Map<string, Array<{ trainer: TrainerInfo; pattern: TrainerPattern }>>();

    for (const trainer of Object.values(data.trainers) as TrainerInfo[]) {
      for (const pattern of trainer.best_patterns || []) {
        const key = pattern.description;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push({ trainer, pattern });
      }
    }

    // 各グループを好走率でソート
    const result = Array.from(groups.entries())
      .map(([description, items]) => ({
        description,
        items: items.sort((a, b) => b.pattern.stats.top3_rate - a.pattern.stats.top3_rate),
      }))
      .sort((a, b) => b.items.length - a.items.length);

    return result;
  }, [data]);

  // Loading
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

  // Error
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
          <Link href="/" className="hover:underline flex items-center gap-1">
            <ArrowLeft className="h-4 w-4" />
            トップ
          </Link>
          <span>/</span>
          <span className="text-foreground">調教師パターン分析</span>
        </div>
        <Card className="bg-amber-50 dark:bg-amber-950/30 border-amber-200">
          <CardContent className="p-6 text-center">
            <p className="text-amber-800 dark:text-amber-200 font-medium mb-2">
              {error}
            </p>
            <p className="text-amber-600 dark:text-amber-400 text-sm">
              管理画面 → データ分析 → 「調教師パターン分析」を実行してください
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  const { summary, meta } = data;

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
          <span className="text-foreground">調教師パターン分析</span>
        </div>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">調教師パターン分析</h1>
          <Button variant="outline" size="sm" onClick={fetchData} className="gap-1.5">
            <RefreshCw className="h-4 w-4" />
            更新
          </Button>
        </div>
        {meta && (
          <p className="text-sm text-muted-foreground mt-1">
            対象期間: {meta.data_period} / 生成: {meta.created_at?.slice(0, 10)}
          </p>
        )}
      </div>

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

      {/* タブ */}
      <Tabs defaultValue="trainers">
        <TabsList>
          <TabsTrigger value="trainers">調教師一覧</TabsTrigger>
          <TabsTrigger value="patterns">パターン別</TabsTrigger>
        </TabsList>

        {/* タブ1: 調教師一覧 */}
        <TabsContent value="trainers" className="mt-4 space-y-3">
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
              <span className="text-muted-foreground">表示:</span>
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

          {/* テーブル */}
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

        {/* タブ2: パターン別 */}
        <TabsContent value="patterns" className="mt-4 space-y-4">
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
                      <th className="text-left py-1 pl-2">ラベル</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.items.map(({ trainer, pattern }) => (
                      <tr key={trainer.jvn_code} className={`border-t ${getTop3BgColor(pattern.stats.top3_rate)}`}>
                        <td className="py-1 pr-2 font-medium">
                          {trainer.name}
                          {pattern.human_label && <span className="text-amber-500 ml-0.5">★</span>}
                        </td>
                        <td className="text-center py-1 px-2">{trainer.tozai}</td>
                        <td className={`text-right py-1 px-2 font-mono ${getTop3Color(pattern.stats.top3_rate)}`}>
                          {pct(pattern.stats.top3_rate)}
                        </td>
                        <td className="text-right py-1 px-2 font-mono">{pct(pattern.stats.win_rate)}</td>
                        <td className="text-right py-1 px-2 font-mono">{pattern.stats.sample_size}</td>
                        <td className="text-right py-1 px-2 font-mono text-green-600">
                          {pattern.stats.lift != null ? `+${(pattern.stats.lift * 100).toFixed(1)}` : '-'}
                        </td>
                        <td className="text-center py-1 px-2">{getConfidenceBadge(pattern.stats.confidence)}</td>
                        <td className="py-1 pl-2 text-muted-foreground truncate max-w-40">
                          {pattern.human_label || '-'}
                        </td>
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
