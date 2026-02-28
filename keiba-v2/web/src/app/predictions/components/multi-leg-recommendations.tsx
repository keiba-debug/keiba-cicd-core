'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { MultiLegRecommendation, PredictionRace } from '@/lib/data/predictions-reader';
import type { RaceResultsMap } from '@/lib/data/predictions-reader';
import { isTurf, isDirt } from '../lib/helpers';

interface MultiLegRecommendationsProps {
  recommendations: MultiLegRecommendation[];
  results?: RaceResultsMap;
  races: PredictionRace[];
  venueFilter: string;
  trackFilter: string;
  raceNumFilter: number;
}

const TICKET_TYPE_JP: Record<string, string> = {
  umatan: '馬単',
  umaren: '馬連',
  wide: 'ワイド',
  sanrenpuku: '三連複',
};

/** ticket_type → FF CSV 券種コード */
const TICKET_TYPE_CODE: Record<string, number> = {
  umaren: 3,
  wide: 4,
  umatan: 5,
  sanrenpuku: 6,
};

const STRATEGY_META: Record<string, { label: string; roi: string; desc: string; color: string }> = {
  'I.VB馬単1点': { label: 'VB馬単1点', roi: '189%', desc: '単勝VBの補完', color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' },
  'G.VB馬単流': { label: 'VB馬単流', roi: '130%', desc: 'VB馬→ARd上位流し', color: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200' },
  'K.危険裏ワイド': { label: '危険裏ワイド', roi: '117%', desc: '危険馬除外ワイドBOX', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' },
};

interface RaceGroup {
  raceId: string;
  venue: string;
  raceNum: number;
  trackType: string;
  bets: MultiLegRecommendation[];
}

export function MultiLegRecommendations({ recommendations, results, races, venueFilter, trackFilter, raceNumFilter }: MultiLegRecommendationsProps) {
  const [csvExporting, setCsvExporting] = useState(false);
  const [csvResult, setCsvResult] = useState<{ ok: boolean; msg: string } | null>(null);

  if (!recommendations || recommendations.length === 0) return null;

  // race_id → track_type のマップ
  const raceTrackMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of races) m.set(r.race_id, r.track_type);
    return m;
  }, [races]);

  const { filtered, raceGroups, stratSummary, totalCost } = useMemo(() => {
    // フィルタ適用
    let recs = recommendations;
    if (venueFilter !== 'all') {
      recs = recs.filter(r => r.venue === venueFilter);
    }
    if (trackFilter !== 'all') {
      recs = recs.filter(r => {
        const tt = raceTrackMap.get(r.race_id) || '';
        return trackFilter === 'turf' ? isTurf(tt) : isDirt(tt);
      });
    }
    if (raceNumFilter > 0) {
      recs = recs.filter(r => r.race_number === raceNumFilter);
    }

    // レース別グループ化
    const groupMap = new Map<string, RaceGroup>();
    for (const rec of recs) {
      if (!groupMap.has(rec.race_id)) {
        groupMap.set(rec.race_id, {
          raceId: rec.race_id,
          venue: rec.venue,
          raceNum: rec.race_number,
          trackType: raceTrackMap.get(rec.race_id) || '',
          bets: [],
        });
      }
      groupMap.get(rec.race_id)!.bets.push(rec);
    }
    const raceGroups = Array.from(groupMap.values())
      .sort((a, b) => a.raceNum - b.raceNum || a.raceId.localeCompare(b.raceId));

    // 戦略別集計
    const stratSummary = new Map<string, number>();
    for (const rec of recs) {
      stratSummary.set(rec.strategy, (stratSummary.get(rec.strategy) || 0) + 1);
    }

    const totalCost = recs.reduce((s, r) => s + r.cost, 0);

    return { filtered: recs, raceGroups, stratSummary, totalCost };
  }, [recommendations, venueFilter, trackFilter, raceNumFilter, raceTrackMap]);

  // 着順判定（結果がある場合）
  const getFinish = (raceId: string, umaban: number): number => {
    if (!results) return 0;
    const raceResult = results[raceId];
    if (!raceResult) return 0;
    return raceResult[umaban]?.finish_position || 0;
  };

  const checkHit = (rec: MultiLegRecommendation): 'hit' | 'miss' | 'pending' => {
    if (!results || !results[rec.race_id]) return 'pending';
    const finishes = rec.horses.map(h => getFinish(rec.race_id, h));
    if (finishes.some(f => f === 0)) return 'pending';

    switch (rec.ticket_type) {
      case 'umatan':
        return finishes[0] === 1 && finishes[1] === 2 ? 'hit' : 'miss';
      case 'umaren':
        return finishes.every(f => f <= 2) ? 'hit' : 'miss';
      case 'wide':
        return finishes.every(f => f <= 3) ? 'hit' : 'miss';
      case 'sanrenpuku':
        return finishes.every(f => f <= 3) ? 'hit' : 'miss';
      default:
        return 'pending';
    }
  };

  const hasResults = Object.keys(results || {}).length > 0;
  const isFiltered = venueFilter !== 'all' || trackFilter !== 'all' || raceNumFilter > 0;

  const exportFfCsv = async () => {
    setCsvExporting(true);
    setCsvResult(null);
    try {
      const bets = filtered.map(rec => ({
        raceId: rec.race_id,
        betType: TICKET_TYPE_CODE[rec.ticket_type] ?? 5,
        umaban: rec.horses[0],
        umaban2: rec.horses[1],
        umaban3: rec.horses[2],
        amount: rec.cost,
      }));
      const res = await fetch('/api/target-marks/auto-bet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bets }),
      });
      const data = await res.json();
      if (data.success) {
        setCsvResult({ ok: true, msg: `${data.summary.totalBets}点 出力完了` });
      } else {
        setCsvResult({ ok: false, msg: data.error || '出力失敗' });
      }
    } catch (err) {
      setCsvResult({ ok: false, msg: String(err) });
    } finally {
      setCsvExporting(false);
    }
  };

  return (
    <Card id="section-multi-leg" className="mb-8">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            スポット馬券（連系）
            <Badge variant="outline" className="text-xs">
              {filtered.length}点 / {raceGroups.length}R
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {totalCost.toLocaleString()}円
            </Badge>
            {isFiltered && (
              <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                全{recommendations.length}点中
              </Badge>
            )}
          </h3>
          <div className="flex items-center gap-2">
            {csvResult && (
              <span className={`text-xs ${csvResult.ok ? 'text-green-700 dark:text-green-400' : 'text-red-600'}`}>
                {csvResult.msg}
              </span>
            )}
            <button
              onClick={exportFfCsv}
              disabled={csvExporting || filtered.length === 0}
              className="px-3 py-1 text-xs font-medium rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-blue-300 dark:border-blue-700 disabled:opacity-50"
              title="スポット馬券をTARGET FF CSV形式で出力"
            >
              {csvExporting ? '出力中...' : 'FF CSV出力'}
            </button>
          </div>
        </div>

        {/* 戦略サマリーカード */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          {Array.from(stratSummary.entries()).map(([strat, count]) => {
            const meta = STRATEGY_META[strat];
            return (
              <div key={strat} className={`rounded-lg p-2 text-center text-xs ${meta?.color || 'bg-gray-100'}`}>
                <div className="font-semibold">{meta?.label || strat}</div>
                <div>{count}点 / BT ROI {meta?.roi || '?'}</div>
                <div className="text-[10px] opacity-75">{meta?.desc || ''}</div>
              </div>
            );
          })}
        </div>

        {filtered.length === 0 ? (
          <div className="text-center text-muted-foreground py-4 text-sm">
            該当する推奨なし
          </div>
        ) : (
          /* レース別推奨テーブル */
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-1 px-2">レース</th>
                  <th className="py-1 px-2">戦略</th>
                  <th className="py-1 px-2">券種</th>
                  <th className="py-1 px-2">買い目</th>
                  <th className="py-1 px-2 text-right">金額</th>
                  {hasResults && <th className="py-1 px-2 text-center">結果</th>}
                </tr>
              </thead>
              <tbody>
                {raceGroups.map((group) => {
                  const bets = group.bets;
                  return bets.map((bet, idx) => {
                    const meta = STRATEGY_META[bet.strategy];
                    const tt = TICKET_TYPE_JP[bet.ticket_type] || bet.ticket_type;
                    const horsesStr = bet.horses.map((h, i) => {
                      const name = bet.horse_names[i] || `#${h}`;
                      return `${h}${name}`;
                    });
                    const hitStatus = hasResults ? checkHit(bet) : 'pending';

                    return (
                      <tr
                        key={`${bet.race_id}-${bet.strategy}-${idx}`}
                        className={`border-b border-dashed hover:bg-muted/50 ${
                          hitStatus === 'hit' ? 'bg-green-50 dark:bg-green-950' :
                          hitStatus === 'miss' ? 'bg-gray-50 dark:bg-gray-900 opacity-60' : ''
                        }`}
                      >
                        <td className="py-1.5 px-2 whitespace-nowrap">
                          {idx === 0 ? (
                            <span className="font-medium">{group.venue}{group.raceNum}R</span>
                          ) : null}
                        </td>
                        <td className="py-1.5 px-2">
                          <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${meta?.color || ''}`}>
                            {meta?.label || bet.strategy}
                          </span>
                        </td>
                        <td className="py-1.5 px-2 font-medium">{tt}</td>
                        <td className="py-1.5 px-2">
                          <div className="flex items-center gap-1 flex-wrap">
                            {horsesStr.map((hs, hi) => (
                              <span key={hi}>
                                {hi > 0 && (
                                  <span className="text-muted-foreground mx-0.5">
                                    {bet.ticket_type === 'umatan' ? '\u2192' : '-'}
                                  </span>
                                )}
                                <span className="font-mono">{hs}</span>
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="py-1.5 px-2 text-right font-mono">{bet.cost}</td>
                        {hasResults && (
                          <td className="py-1.5 px-2 text-center">
                            {hitStatus === 'hit' && <span className="text-green-600 font-bold">的中</span>}
                            {hitStatus === 'miss' && <span className="text-gray-400">-</span>}
                            {hitStatus === 'pending' && <span className="text-gray-300">-</span>}
                          </td>
                        )}
                      </tr>
                    );
                  });
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* フッター注釈 */}
        <div className="mt-3 text-[11px] text-muted-foreground">
          BT ROI = バックテスト検証済みROI (2025-2026テスト期間)
        </div>
      </CardContent>
    </Card>
  );
}
