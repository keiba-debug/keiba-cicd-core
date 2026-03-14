'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { MultiLegRecommendation, PredictionRace } from '@/lib/data/predictions-reader';
import type { RaceResultsMap } from '@/lib/data/predictions-reader';
import { isTurf, isDirt } from '../lib/helpers';

interface MultiLegRecommendationsProps {
  recommendations: MultiLegRecommendation[];
  sanrentanFormation?: MultiLegRecommendation[];
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
  sanrentan: '三連単',
};

/** ticket_type → FF CSV 券種コード */
const TICKET_TYPE_CODE: Record<string, number> = {
  umaren: 3,
  wide: 4,
  umatan: 5,
  sanrenpuku: 6,
  sanrentan: 7,
};

const STRATEGY_META: Record<string, { label: string; roi: string; desc: string; color: string }> = {
  'I.VB馬単1点': { label: 'VB馬単1点', roi: '189%', desc: '単勝VBの補完', color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' },
  'G.VB馬単流': { label: 'VB馬単流', roi: '130%', desc: 'VB馬→ARd上位流し', color: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200' },
  'K.危険裏ワイド': { label: '危険裏ワイド', roi: '117%', desc: '危険馬除外ワイドBOX', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' },
  '三連単VB頭': { label: '三連単VB頭', roi: '215%', desc: 'VB馬1着フォーメーション', color: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' },
};

interface RaceGroup {
  raceId: string;
  venue: string;
  raceNum: number;
  trackType: string;
  bets: MultiLegRecommendation[];
}

// ── Helper: checkHit ──
function checkHitFn(rec: MultiLegRecommendation, results?: RaceResultsMap): 'hit' | 'miss' | 'pending' {
  if (!results || !results[rec.race_id]) return 'pending';
  const raceResult = results[rec.race_id];
  const finishes = rec.horses.map(h => raceResult[h]?.finish_position || 0);
  if (finishes.some(f => f === 0)) return 'pending';

  switch (rec.ticket_type) {
    case 'sanrentan':
      return finishes[0] === 1 && finishes[1] === 2 && finishes[2] === 3 ? 'hit' : 'miss';
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
}

// ── Helper: filter + group ──
function useFilteredGroups(
  recs: MultiLegRecommendation[],
  races: PredictionRace[],
  venueFilter: string,
  trackFilter: string,
  raceNumFilter: number,
) {
  const raceTrackMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of races) m.set(r.race_id, r.track_type);
    return m;
  }, [races]);

  return useMemo(() => {
    let filtered = recs;
    if (venueFilter !== 'all') {
      filtered = filtered.filter(r => r.venue === venueFilter);
    }
    if (trackFilter !== 'all') {
      filtered = filtered.filter(r => {
        const tt = raceTrackMap.get(r.race_id) || '';
        return trackFilter === 'turf' ? isTurf(tt) : isDirt(tt);
      });
    }
    if (raceNumFilter > 0) {
      filtered = filtered.filter(r => r.race_number === raceNumFilter);
    }

    const groupMap = new Map<string, RaceGroup>();
    for (const rec of filtered) {
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

    const totalCost = filtered.reduce((s, r) => s + r.cost, 0);
    return { filtered, raceGroups, totalCost };
  }, [recs, venueFilter, trackFilter, raceNumFilter, raceTrackMap]);
}

// ── Helper: FF CSV export ──
function useExportCsv() {
  const [csvExporting, setCsvExporting] = useState(false);
  const [csvResult, setCsvResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const exportFfCsv = async (bets: MultiLegRecommendation[]) => {
    setCsvExporting(true);
    setCsvResult(null);
    try {
      const payload = bets.map(rec => ({
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
        body: JSON.stringify({ bets: payload }),
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

  return { csvExporting, csvResult, exportFfCsv };
}

// ── BetTable sub-component ──
function BetTable({ raceGroups, results }: { raceGroups: RaceGroup[]; results?: RaceResultsMap }) {
  const hasResults = Object.keys(results || {}).length > 0;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-1 px-2">レース</th>
            <th className="py-1 px-2">券種</th>
            <th className="py-1 px-2">買い目</th>
            <th className="py-1 px-2 text-right">金額</th>
            {hasResults && <th className="py-1 px-2 text-center">結果</th>}
          </tr>
        </thead>
        <tbody>
          {raceGroups.map((group) =>
            group.bets.map((bet, idx) => {
              const tt = TICKET_TYPE_JP[bet.ticket_type] || bet.ticket_type;
              const isOrdered = bet.ticket_type === 'umatan' || bet.ticket_type === 'sanrentan';
              const hitStatus = hasResults ? checkHitFn(bet, results) : 'pending';

              return (
                <tr
                  key={`${bet.race_id}-${idx}`}
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
                  <td className="py-1.5 px-2 font-medium">{tt}</td>
                  <td className="py-1.5 px-2">
                    <div className="flex items-center gap-1 flex-wrap">
                      {bet.horses.map((h, hi) => {
                        const name = bet.horse_names[hi] || `#${h}`;
                        return (
                          <span key={hi}>
                            {hi > 0 && (
                              <span className="text-muted-foreground mx-0.5">
                                {isOrdered ? '\u2192' : '-'}
                              </span>
                            )}
                            <span className="font-mono">{h}{name}</span>
                          </span>
                        );
                      })}
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
            })
          )}
        </tbody>
      </table>
    </div>
  );
}


// ====================================================================
// Main component
// ====================================================================

export function MultiLegRecommendations({
  recommendations,
  sanrentanFormation,
  results,
  races,
  venueFilter,
  trackFilter,
  raceNumFilter,
}: MultiLegRecommendationsProps) {
  const hasSanrentan = sanrentanFormation && sanrentanFormation.length > 0;
  const hasMultiLeg = recommendations && recommendations.length > 0;

  if (!hasSanrentan && !hasMultiLeg) return null;

  return (
    <>
      {hasSanrentan && (
        <SanrentanSection
          bets={sanrentanFormation!}
          results={results}
          races={races}
          venueFilter={venueFilter}
          trackFilter={trackFilter}
          raceNumFilter={raceNumFilter}
        />
      )}
      {hasMultiLeg && (
        <SpotSection
          bets={recommendations}
          results={results}
          races={races}
          venueFilter={venueFilter}
          trackFilter={trackFilter}
          raceNumFilter={raceNumFilter}
        />
      )}
    </>
  );
}


// ====================================================================
// 雷切 — 三連単VB頭セクション
// ====================================================================

function SanrentanSection({
  bets,
  results,
  races,
  venueFilter,
  trackFilter,
  raceNumFilter,
}: {
  bets: MultiLegRecommendation[];
  results?: RaceResultsMap;
  races: PredictionRace[];
  venueFilter: string;
  trackFilter: string;
  raceNumFilter: number;
}) {
  const { filtered, raceGroups, totalCost } = useFilteredGroups(bets, races, venueFilter, trackFilter, raceNumFilter);
  const { csvExporting, csvResult, exportFfCsv } = useExportCsv();

  // VB馬ごとの集計
  const vbSummary = useMemo(() => {
    const byRace = new Map<string, { venue: string; raceNum: number; vbHorses: Set<string>; tickets: number; cost: number }>();
    for (const rec of filtered) {
      if (!byRace.has(rec.race_id)) {
        byRace.set(rec.race_id, { venue: rec.venue, raceNum: rec.race_number, vbHorses: new Set(), tickets: 0, cost: 0 });
      }
      const r = byRace.get(rec.race_id)!;
      // ★ horse is first in horses array
      const starName = rec.horse_names[0] || `#${rec.horses[0]}`;
      r.vbHorses.add(`${rec.horses[0]}${starName}`);
      r.tickets += 1;
      r.cost += rec.cost;
    }
    return Array.from(byRace.values()).sort((a, b) => a.raceNum - b.raceNum);
  }, [filtered]);

  const [expanded, setExpanded] = useState(false);

  return (
    <Card id="section-sanrentan" className="mb-8 border-purple-200 dark:border-purple-800">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <span className="text-purple-700 dark:text-purple-300">雷切 — 三連単VB頭</span>
            <Badge variant="outline" className="text-xs border-purple-300 text-purple-700 dark:text-purple-300">
              {filtered.length}点 / {raceGroups.length}R
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {totalCost.toLocaleString()}円
            </Badge>
          </h3>
          <div className="flex items-center gap-2">
            {csvResult && (
              <span className={`text-xs ${csvResult.ok ? 'text-green-700 dark:text-green-400' : 'text-red-600'}`}>
                {csvResult.msg}
              </span>
            )}
            <button
              onClick={() => exportFfCsv(filtered)}
              disabled={csvExporting || filtered.length === 0}
              className="px-3 py-1 text-xs font-medium rounded border bg-purple-50 dark:bg-purple-950 hover:bg-purple-100 dark:hover:bg-purple-900 border-purple-300 dark:border-purple-700 text-purple-700 dark:text-purple-300 disabled:opacity-50"
              title="三連単をTARGET FF CSV形式で出力"
            >
              {csvExporting ? '出力中...' : 'FF CSV出力'}
            </button>
          </div>
        </div>

        {/* 戦略説明 */}
        <div className="rounded-lg bg-purple-50 dark:bg-purple-950/50 p-3 mb-4 text-xs">
          <div className="font-semibold text-purple-800 dark:text-purple-200 mb-1">VB頭フォーメーション (BT ROI 215%)</div>
          <div className="text-purple-700 dark:text-purple-300 space-y-0.5">
            <div>条件: P%Top3シェア&lt;0.45 / 1番人気3.0-4.0倍 / ConfGap&lt;0.10 / VB候補≧3頭</div>
            <div>★(1着)=VB穴馬 → ▲(2着)=P%上位4頭 → △(3着)=次3頭 = 最大28点/VB馬</div>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-center text-muted-foreground py-6 text-sm">
            該当レースなし（条件: Share&lt;0.45 / FO 3-4 / CG&lt;0.10 / VB≧3）
          </div>
        ) : (
          <>
            {/* レース別サマリー */}
            <div className="space-y-2 mb-4">
              {vbSummary.map((race, i) => (
                <div key={i} className="flex items-center gap-3 text-sm border-b border-dashed pb-1">
                  <span className="font-semibold w-16">{race.venue}{race.raceNum}R</span>
                  <span className="text-purple-700 dark:text-purple-300">
                    ★ {Array.from(race.vbHorses).join(' / ')}
                  </span>
                  <span className="text-muted-foreground ml-auto">
                    {race.tickets}点 / {race.cost.toLocaleString()}円
                  </span>
                </div>
              ))}
            </div>

            {/* 全チケット展開 */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-purple-600 dark:text-purple-400 hover:underline mb-2"
            >
              {expanded ? '▲ 全チケットを閉じる' : `▼ 全${filtered.length}チケットを展開`}
            </button>
            {expanded && (
              <BetTable raceGroups={raceGroups} results={results} />
            )}
          </>
        )}

        <div className="mt-3 text-[11px] text-muted-foreground">
          BT検証: ROI 215% (FO&lt;4+CG&lt;0.10, 195R/12hit, 2025-03〜2026-03)
        </div>
      </CardContent>
    </Card>
  );
}


// ====================================================================
// スポット馬券セクション (既存、折りたたみ)
// ====================================================================

function SpotSection({
  bets,
  results,
  races,
  venueFilter,
  trackFilter,
  raceNumFilter,
}: {
  bets: MultiLegRecommendation[];
  results?: RaceResultsMap;
  races: PredictionRace[];
  venueFilter: string;
  trackFilter: string;
  raceNumFilter: number;
}) {
  const { filtered, raceGroups, totalCost } = useFilteredGroups(bets, races, venueFilter, trackFilter, raceNumFilter);
  const { csvExporting, csvResult, exportFfCsv } = useExportCsv();
  const [open, setOpen] = useState(false);
  const isFiltered = venueFilter !== 'all' || trackFilter !== 'all' || raceNumFilter > 0;

  return (
    <Card id="section-multi-leg" className="mb-8">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-2">
          <button onClick={() => setOpen(!open)} className="text-left flex items-center gap-2">
            <h3 className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
              {open ? '▲' : '▼'} スポット馬券（連系）
              <Badge variant="outline" className="text-xs">
                {filtered.length}点 / {raceGroups.length}R
              </Badge>
              <Badge variant="secondary" className="text-xs">
                {totalCost.toLocaleString()}円
              </Badge>
              {isFiltered && (
                <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                  全{bets.length}点中
                </Badge>
              )}
            </h3>
          </button>
          {open && (
            <div className="flex items-center gap-2">
              {csvResult && (
                <span className={`text-xs ${csvResult.ok ? 'text-green-700 dark:text-green-400' : 'text-red-600'}`}>
                  {csvResult.msg}
                </span>
              )}
              <button
                onClick={() => exportFfCsv(filtered)}
                disabled={csvExporting || filtered.length === 0}
                className="px-3 py-1 text-xs font-medium rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-blue-300 dark:border-blue-700 disabled:opacity-50"
              >
                {csvExporting ? '出力中...' : 'FF CSV出力'}
              </button>
            </div>
          )}
        </div>

        {open && (
          <>
            {filtered.length === 0 ? (
              <div className="text-center text-muted-foreground py-4 text-sm">
                該当する推奨なし
              </div>
            ) : (
              <BetTable raceGroups={raceGroups} results={results} />
            )}
            <div className="mt-3 text-[11px] text-muted-foreground">
              BT ROI = バックテスト検証済みROI (2025-2026テスト期間)
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
