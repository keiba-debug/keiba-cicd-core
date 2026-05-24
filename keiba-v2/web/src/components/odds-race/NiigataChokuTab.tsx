'use client';

/**
 * vega-niigata1000 タブ (Phase 3d)
 *
 * 千直開催レースで、各馬の rule_engine v0.2 補正スコア + 発火ルールを一覧表示。
 * - カラムヘッダクリックでソート (asc/desc トグル)
 * - raceId が渡されると My印1/2 を読み込み + 編集ボタン表示
 * - 各行クリックで explanation 展開
 */

import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Target } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getWakuColor } from '@/types/race-data';
import { TargetMarkInputModal } from '@/components/race-v2/TargetMarkInputModal';
import { parseRaceIdForMarks, fetchMyMarksBoth } from './my-marks-utils';
import type { PredictionEntry } from '@/lib/data/predictions-reader';

interface Props {
  entries: PredictionEntry[];
  /** 16桁 raceId。指定すると My印機能(列表示+編集ボタン)が有効化 */
  raceId?: string;
}

type SortKey = 'umaban' | 'wakuban' | 'horseName' | 'polaris' | 'delta' | 'display' | 'confidence' | 'mark1' | 'mark2';
type SortDir = 'asc' | 'desc';

const CONFIDENCE_ORDER: Record<string, number> = { '高': 3, '中': 2, '低': 1 };
const MARK_ORDER: Record<string, number> = {
  '◎': 9, '○': 8, '▲': 7, '△': 6, 'Ⅲ': 5, '注': 4, '穴': 3, '消': 1,
};

function confidenceColor(c: string): string {
  if (c === '高') return 'bg-green-100 text-green-700 border-green-200';
  if (c === '中') return 'bg-yellow-100 text-yellow-700 border-yellow-200';
  return 'bg-gray-100 text-gray-500 border-gray-200';
}

function markColor(mark: string): string {
  switch (mark) {
    case '◎': return 'bg-red-500 text-white';
    case '○': return 'bg-blue-500 text-white';
    case '▲': return 'bg-yellow-500 text-white';
    case '△': return 'bg-gray-400 text-white';
    case 'Ⅲ': return 'bg-purple-500 text-white';
    case '穴': return 'bg-pink-500 text-white';
    default: return 'bg-gray-100 text-gray-400';
  }
}

interface ColHeaderProps {
  sortKey: SortKey;
  currentSort: { key: SortKey; dir: SortDir };
  onSort: (key: SortKey) => void;
  children: React.ReactNode;
  align?: 'left' | 'right' | 'center';
  className?: string;
}

function ColHeader({ sortKey, currentSort, onSort, children, align = 'left', className = '' }: ColHeaderProps) {
  const isActive = currentSort.key === sortKey;
  const arrow = isActive ? (currentSort.dir === 'asc' ? '▲' : '▼') : '';
  const alignCls = align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';
  return (
    <th
      className={`${alignCls} py-2 px-2 cursor-pointer select-none hover:bg-gray-100 ${isActive ? 'bg-blue-50 text-blue-700' : ''} ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        <span className="text-[8px] text-gray-400">{arrow || '⇅'}</span>
      </span>
    </th>
  );
}

export function NiigataChokuTab({ entries, raceId }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: 'display', dir: 'desc' });
  const [marks1, setMarks1] = useState<Record<number, string>>({});
  const [marks2, setMarks2] = useState<Record<number, string>>({});

  const raceInfoForMarks = useMemo(
    () => (raceId ? parseRaceIdForMarks(raceId) : null),
    [raceId]
  );
  const myMarksEnabled = raceInfoForMarks !== null;

  const reloadMarks = useCallback(async () => {
    if (!raceInfoForMarks) return;
    const { marks1: m1, marks2: m2 } = await fetchMyMarksBoth(raceInfoForMarks, raceId);
    setMarks1(m1);
    setMarks2(m2);
  }, [raceInfoForMarks, raceId]);

  useEffect(() => {
    reloadMarks();
  }, [reloadMarks]);

  const handleSort = useCallback((key: SortKey) => {
    setSort((prev) => {
      if (prev.key !== key) {
        // 数値系・日本語系のデフォルト方向
        const desc: SortKey[] = ['polaris', 'delta', 'display', 'confidence', 'mark1', 'mark2'];
        return { key, dir: desc.includes(key) ? 'desc' : 'asc' };
      }
      return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' };
    });
  }, []);

  const horses = useMemo(() => {
    const list = entries
      .filter((e) => e.niigata1000)
      .map((e) => ({
        entry: e,
        n1k: e.niigata1000!,
        mark1: marks1[e.umaban] ?? '',
        mark2: marks2[e.umaban] ?? '',
      }));

    list.sort((a, b) => {
      let cmp = 0;
      switch (sort.key) {
        case 'umaban':
          cmp = a.entry.umaban - b.entry.umaban;
          break;
        case 'wakuban':
          cmp = (a.n1k.wakuban ?? 99) - (b.n1k.wakuban ?? 99);
          break;
        case 'horseName':
          cmp = (a.entry.horse_name ?? '').localeCompare(b.entry.horse_name ?? '', 'ja');
          break;
        case 'polaris':
          cmp = (a.entry.pred_proba_p ?? 0) - (b.entry.pred_proba_p ?? 0);
          break;
        case 'delta':
          cmp = a.n1k.delta_p - b.n1k.delta_p;
          break;
        case 'display':
          cmp = a.n1k.display_score - b.n1k.display_score;
          break;
        case 'confidence':
          cmp = (CONFIDENCE_ORDER[a.n1k.confidence] ?? 0) - (CONFIDENCE_ORDER[b.n1k.confidence] ?? 0);
          break;
        case 'mark1':
          cmp = (MARK_ORDER[a.mark1] ?? 0) - (MARK_ORDER[b.mark1] ?? 0);
          break;
        case 'mark2':
          cmp = (MARK_ORDER[a.mark2] ?? 0) - (MARK_ORDER[b.mark2] ?? 0);
          break;
      }
      return sort.dir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [entries, marks1, marks2, sort]);

  if (horses.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          千直オーバーレイは未適用です。新潟芝1000m直線レースのみ自動適用されます。
        </CardContent>
      </Card>
    );
  }

  // 推奨上位3頭 (除外馬を除く、display_score 順)
  const recommendedTop3 = [...horses]
    .sort((a, b) => b.n1k.display_score - a.n1k.display_score)
    .filter((h) => !h.n1k.is_rejected)
    .slice(0, 3);

  // モーダル用 entries (TargetMarkEntry[])
  const modalEntries = entries
    .filter((e) => e.niigata1000)
    .map((e) => ({
      horse_number: e.umaban,
      horse_name: e.horse_name ?? `${e.umaban}番`,
      entry_data: { waku: e.niigata1000?.wakuban ?? null },
    }));

  return (
    <div className="space-y-4">
      {/* ヘッダー */}
      <Card className="border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50/40">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg flex-wrap">
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-600 text-white">千直</span>
            <span>vega-niigata1000 ルール補正</span>
            <div className="ml-auto flex items-center gap-2">
              {myMarksEnabled && raceInfoForMarks && (
                <TargetMarkInputModal
                  raceInfo={raceInfoForMarks}
                  raceId={raceId}
                  entries={modalEntries}
                  trigger={
                    <Button variant="outline" size="sm">
                      <Target className="h-4 w-4 mr-1" />
                      My印を編集
                    </Button>
                  }
                  onSaved={() => reloadMarks()}
                />
              )}
              <Link
                href="/analysis/specialists/niigata-1000m"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline"
              >
                専門解説 →
              </Link>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-3">
          <p className="text-xs text-muted-foreground">
            polaris予測値に STEP B〜E の加減点を logit空間で加算した補正スコア。
            カラムヘッダクリックでソート、行クリックで説明展開。
          </p>
          {recommendedTop3.length > 0 && (
            <div className="rounded-lg bg-white border border-blue-200 px-3 py-2.5">
              <div className="text-[10px] font-bold uppercase tracking-wider text-blue-700 mb-1.5">
                推奨上位（除外馬を除く）
              </div>
              <div className="flex flex-wrap gap-2">
                {recommendedTop3.map(({ entry, n1k }, i) => (
                  <div key={entry.umaban} className="flex items-center gap-1.5 text-xs">
                    <span className="font-mono text-gray-400">#{i + 1}</span>
                    <span className="font-bold">{entry.umaban}番</span>
                    <span className="text-gray-700">{entry.horse_name}</span>
                    <span className="font-mono font-bold text-blue-700">
                      {(n1k.display_score * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* テーブル */}
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b text-xs text-gray-500">
              <tr>
                <ColHeader sortKey="wakuban" currentSort={sort} onSort={handleSort} align="center" className="w-10">枠</ColHeader>
                <ColHeader sortKey="umaban" currentSort={sort} onSort={handleSort} align="center" className="w-10">番</ColHeader>
                {myMarksEnabled && (
                  <>
                    <ColHeader sortKey="mark1" currentSort={sort} onSort={handleSort} align="center" className="w-10">My1</ColHeader>
                    <ColHeader sortKey="mark2" currentSort={sort} onSort={handleSort} align="center" className="w-10">My2</ColHeader>
                  </>
                )}
                <ColHeader sortKey="horseName" currentSort={sort} onSort={handleSort}>馬名</ColHeader>
                <ColHeader sortKey="polaris" currentSort={sort} onSort={handleSort} align="right">polaris</ColHeader>
                <ColHeader sortKey="delta" currentSort={sort} onSort={handleSort} align="right">補正</ColHeader>
                <ColHeader sortKey="display" currentSort={sort} onSort={handleSort} align="right">最終</ColHeader>
                <ColHeader sortKey="confidence" currentSort={sort} onSort={handleSort} align="center" className="w-12">信頼度</ColHeader>
                <th className="text-left py-2 px-2">ルール</th>
                <th className="text-center py-2 px-2 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {horses.map(({ entry, n1k, mark1, mark2 }) => {
                const isExpanded = expanded === entry.umaban;
                const wakuban = n1k.wakuban ?? 0;
                const wakuClass = wakuban ? getWakuColor(wakuban) : 'bg-gray-200 text-gray-500';
                const deltaPct = n1k.delta_p * 100;
                return (
                  <Fragment key={entry.umaban}>
                    <tr
                      onClick={() => setExpanded(isExpanded ? null : entry.umaban)}
                      className={`border-b cursor-pointer hover:bg-blue-50 ${n1k.is_rejected ? 'opacity-50' : ''}`}
                    >
                      <td className="text-center py-2">
                        <span
                          className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold border ${wakuClass}`}
                        >
                          {wakuban || '?'}
                        </span>
                      </td>
                      <td className="text-center py-2 font-bold">{entry.umaban}</td>
                      {myMarksEnabled && (
                        <>
                          <td className="text-center py-2">
                            {mark1 && (
                              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${markColor(mark1)}`}>
                                {mark1}
                              </span>
                            )}
                          </td>
                          <td className="text-center py-2">
                            {mark2 && (
                              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${markColor(mark2)}`}>
                                {mark2}
                              </span>
                            )}
                          </td>
                        </>
                      )}
                      <td className="py-2 px-3">
                        <div className="font-bold">{entry.horse_name}</div>
                        <div className="text-[10px] text-gray-500">
                          {n1k.sex}{n1k.age}歳{n1k.jockey_name ? ` ・ ${n1k.jockey_name}` : ''}
                        </div>
                      </td>
                      <td className="text-right font-mono text-xs text-gray-500">
                        {((entry.pred_proba_p ?? 0) * 100).toFixed(1)}%
                      </td>
                      <td
                        className={`text-right font-mono text-xs font-bold ${
                          deltaPct > 0 ? 'text-blue-600'
                          : deltaPct < 0 ? 'text-orange-600'
                          : 'text-gray-500'
                        }`}
                      >
                        {deltaPct > 0 ? '+' : ''}{deltaPct.toFixed(1)}%
                      </td>
                      <td className="text-right font-mono font-bold">
                        {(n1k.display_score * 100).toFixed(1)}%
                      </td>
                      <td className="text-center">
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded border ${confidenceColor(n1k.confidence)}`}
                        >
                          {n1k.confidence}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-[11px] text-gray-600">
                        {n1k.fired_rule_ids.length} 件
                        {n1k.is_rejected && (
                          <span className="ml-2 text-red-600 font-bold">⚠️除外</span>
                        )}
                      </td>
                      <td className="text-center text-gray-300">{isExpanded ? '▲' : '▼'}</td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-blue-50/30 border-b">
                        <td colSpan={myMarksEnabled ? 11 : 9} className="py-3 px-4">
                          <pre className="text-xs whitespace-pre-wrap font-mono text-gray-800 leading-relaxed">
                            {n1k.explanation}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
