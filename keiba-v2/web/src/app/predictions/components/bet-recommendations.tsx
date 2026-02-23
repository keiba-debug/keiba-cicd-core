'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { PredictionEntry } from '@/lib/data/predictions-reader';
import type { BetRecommendation, OddsMap, SortState, DbResultsMap } from '../lib/types';
import { BET_CONFIG, PRESET_OPTIONS, type ServerPresetKey, type AllocMode } from '../lib/bet-logic';
import { getWinOdds, calcHeadRatio, getEvColor, getRecBadgeClass, getRaceLink, SortTh, getArColor } from '../lib/helpers';

interface BetRecommendationsProps {
  betRecommendations: BetRecommendation[];
  sortedBetRecommendations: BetRecommendation[];
  betSummary: {
    winCount: number; placeCount: number; winTotal: number; placeTotal: number;
    totalAmount: number; totalBets: number; dangerRaces: number;
  };
  oddsMap: OddsMap;
  getLiveGap: (raceId: string, entry: PredictionEntry) => number;
  oddsLoading: boolean;
  dailyBudget: number;
  updateBudget: (v: number) => void;
  fetchAllOdds: () => Promise<void>;
  syncBetMarks: () => Promise<void>;
  betSyncing: boolean;
  betSyncResult: { totalBets: number; winBets: number; placeBets: number; racesWritten: number; totalAmount: number; filePath: string } | null;
  betSort: SortState;
  setBetSort: (s: SortState) => void;
  preset: ServerPresetKey;
  onPresetChange: (preset: ServerPresetKey) => void;
  allocMode: AllocMode;
  onAllocModeChange: (mode: AllocMode) => void;
  dbResults?: DbResultsMap;
  getFinishPos?: (raceId: string, umaban: number) => number;
}

function PresetButtons({ preset, onPresetChange }: { preset: ServerPresetKey; onPresetChange: (p: ServerPresetKey) => void }) {
  return (
    <div className="flex items-center gap-1.5">
      {PRESET_OPTIONS.map(opt => (
        <button key={opt.key} onClick={() => onPresetChange(opt.key)}
          className={`px-2.5 py-1 text-xs rounded border transition-colors ${preset === opt.key
            ? 'bg-indigo-600 text-white border-indigo-600'
            : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
          title={opt.description}>
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function BetRecommendations({
  betRecommendations, sortedBetRecommendations, betSummary,
  oddsMap, getLiveGap, oddsLoading, dailyBudget, updateBudget,
  fetchAllOdds, syncBetMarks, betSyncing, betSyncResult,
  betSort, setBetSort,
  preset, onPresetChange,
  allocMode, onAllocModeChange,
  dbResults, getFinishPos,
}: BetRecommendationsProps) {
  const hasResults = dbResults && Object.keys(dbResults).length > 0;

  if (betRecommendations.length === 0) {
    return (
      <Card className="mb-8 border-gray-200 dark:border-gray-700">
        <CardContent className="py-6 text-center text-muted-foreground">
          <div className="text-lg font-bold mb-1">本日は見送り推奨</div>
          <div className="text-xs">選択プリセットの条件を満たす馬が見つかりません</div>
          <div className="mt-3">
            <PresetButtons preset={preset} onPresetChange={onPresetChange} />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card id="section-bets" className="mb-8 border-indigo-200 dark:border-indigo-800">
      <CardHeader className="pb-2 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950 dark:to-purple-950">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-lg flex items-center gap-2">
            購入プラン ({sortedBetRecommendations.length !== betRecommendations.length ? `${sortedBetRecommendations.length}/` : ''}{betSummary.totalBets}件)
          </CardTitle>
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchAllOdds()}
              disabled={oddsLoading}
              className="px-2 py-0.5 text-xs rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-gray-300 dark:border-gray-600 disabled:opacity-50"
              title="最新オッズを取得"
            >
              {oddsLoading ? '取得中...' : '更新'}
            </button>
            <label className="flex items-center gap-1 text-xs text-muted-foreground">
              予算
              <input
                type="number"
                value={dailyBudget}
                onChange={(e) => updateBudget(Number(e.target.value))}
                step={5000}
                min={1000}
                className="w-20 px-1.5 py-0.5 text-xs text-right rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
              />
            </label>
            <div className="flex rounded border border-gray-300 dark:border-gray-600 overflow-hidden">
              <button
                onClick={() => onAllocModeChange('kelly')}
                className={`px-2 py-0.5 text-[10px] transition-colors ${allocMode === 'kelly' ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
                title="Gap比例の傾斜配分（gap大→厚め）">傾斜</button>
              <button
                onClick={() => onAllocModeChange('equal')}
                className={`px-2 py-0.5 text-[10px] transition-colors ${allocMode === 'equal' ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
                title="予算を均等配分">均等</button>
            </div>
            {betSyncResult && (
              <span className="text-xs text-green-700 dark:text-green-400">
                {`${betSyncResult.racesWritten}件 / 単${betSyncResult.winBets} 複${betSyncResult.placeBets} / ¥${betSyncResult.totalAmount.toLocaleString()} → FF CSV出力済`}
              </span>
            )}
            <button
              onClick={syncBetMarks}
              disabled={betSyncing}
              className="px-3 py-1 text-xs font-medium rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-indigo-300 dark:border-indigo-700 disabled:opacity-50"
              title="購入プランをFF CSV出力（TARGETの買い目取り込みメニューで読込）"
            >
              {betSyncing ? '出力中...' : 'FF CSV出力'}
            </button>
          </div>
        </div>
        {/* プリセット切り替え */}
        <div className="flex items-center gap-2 mt-2">
          <PresetButtons preset={preset} onPresetChange={onPresetChange} />
          <span className="text-[10px] text-muted-foreground ml-1">
            {PRESET_OPTIONS.find(o => o.key === preset)?.description}
          </span>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {/* サマリー */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-center text-sm">
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-2">
            <div className="text-lg font-bold">&yen;{betSummary.totalAmount.toLocaleString()}</div>
            <div className="text-[10px] text-muted-foreground">投資総額</div>
          </div>
          <div className="bg-red-50 dark:bg-red-900/20 rounded p-2">
            <div className="text-lg font-bold text-red-600">{betSummary.winCount}件</div>
            <div className="text-[10px] text-muted-foreground">単勝 &yen;{betSummary.winTotal.toLocaleString()}</div>
          </div>
          {betSummary.placeCount > 0 && (
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-2">
              <div className="text-lg font-bold text-blue-600">{betSummary.placeCount}件</div>
              <div className="text-[10px] text-muted-foreground">複勝 &yen;{betSummary.placeTotal.toLocaleString()}</div>
            </div>
          )}
          {betSummary.dangerRaces > 0 && (
            <div className="bg-orange-50 dark:bg-orange-900/20 rounded p-2 border border-orange-200 dark:border-orange-800">
              <div className="text-lg font-bold text-orange-600">{betSummary.dangerRaces}R</div>
              <div className="text-[10px] text-muted-foreground">危険人気馬</div>
            </div>
          )}
        </div>

        {/* 推奨テーブル */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-indigo-50 dark:bg-indigo-900/30 text-xs">
                <th className="px-2 py-2 text-left border">場</th>
                <SortTh sortKey="race" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border">R</SortTh>
                <SortTh sortKey="umaban" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border">馬番</SortTh>
                <th className="px-2 py-2 text-left border">馬名</th>
                <SortTh sortKey="winEv" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border bg-amber-50 dark:bg-amber-900/20" title="単勝EV = calibrated P(win) × 単勝オッズ。VB判定の主軸">単EV</SortTh>
                <SortTh sortKey="margin" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="AR (Aura Rating) — グレード補正済みの絶対能力指数。高い=強い">AR</SortTh>
                <SortTh sortKey="amount" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border bg-yellow-50 dark:bg-yellow-900/20" title="推奨金額">金額</SortTh>
                <SortTh sortKey="odds" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="単勝オッズ">オッズ</SortTh>
                <SortTh sortKey="gap" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border text-gray-400" title="Gap（参考）">Gap*</SortTh>
                <SortTh sortKey="placeEv" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="複勝EV">複EV</SortTh>
                <SortTh sortKey="head" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="頭向き度">頭%</SortTh>
                <SortTh sortKey="danger" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border bg-orange-50 dark:bg-orange-900/20" title="危険な人気馬">危険馬</SortTh>
                {hasResults && (
                  <>
                    <th className="px-2 py-2 text-center border bg-gray-100 dark:bg-gray-800" title="確定着順">着順</th>
                    <th className="px-2 py-2 text-center border bg-gray-100 dark:bg-gray-800" title="確定配当">配当</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sortedBetRecommendations.map((r) => {
                const winOdds = getWinOdds(oddsMap, r.race.race_id, r.entry.umaban, r.entry.odds);
                const headRatio = calcHeadRatio(r.entry.pred_proba_wv, r.entry.pred_proba_v);
                return (
                  <tr
                    key={`${r.race.race_id}-${r.entry.umaban}`}
                    className={`border-b hover:bg-indigo-50/50 dark:hover:bg-indigo-900/10 ${
                      r.danger?.isDanger
                        ? 'bg-orange-50/40 dark:bg-orange-900/10'
                        : r.strength === 'strong' ? 'bg-indigo-50/30 dark:bg-indigo-900/10' : ''
                    }`}
                  >
                    <td className="px-2 py-1.5 border text-xs">
                      <Link href={getRaceLink(r.race)} target="_blank" className="hover:text-blue-600 hover:underline">
                        {r.race.venue_name}
                      </Link>
                    </td>
                    <td className="px-2 py-1.5 border text-center font-bold">{r.race.race_number}</td>
                    <td className="px-2 py-1.5 border text-center font-mono">{r.entry.umaban}</td>
                    <td className="px-2 py-1.5 border font-bold text-xs">{r.entry.horse_name}</td>
                    <td className={`px-2 py-1.5 border text-center font-mono font-bold bg-amber-50/30 dark:bg-amber-900/10 ${getEvColor(r.winEv ?? null)}`}>
                      {r.winEv ? r.winEv.toFixed(2) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs ${getArColor(r.predictedMargin)}`}>
                      {r.predictedMargin.toFixed(1)}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono font-bold bg-yellow-50/50 dark:bg-yellow-900/10">
                      {r.betAmountWin > 0 && <div className="text-red-600">&yen;{r.betAmountWin.toLocaleString()}</div>}
                      {r.betAmountPlace > 0 && <div className="text-blue-600">&yen;{r.betAmountPlace.toLocaleString()}</div>}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-xs">
                      {winOdds ? winOdds.toFixed(1) : '-'}
                    </td>
                    {(() => { const lg = getLiveGap(r.race.race_id, r.entry); return (
                    <td className="px-2 py-1.5 border text-center font-mono text-xs text-gray-400" title="Gap（参考）">
                      +{lg}
                    </td>
                    ); })()}
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs ${r.placeEv && r.placeEv >= 1.0 ? 'text-blue-600 font-bold' : 'text-gray-300'}`}>
                      {r.placeEv ? r.placeEv.toFixed(2) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs ${headRatio && headRatio >= 0.35 ? 'text-red-600 font-bold' : ''}`}>
                      {headRatio ? `${(headRatio * 100).toFixed(0)}` : '-'}
                    </td>
                    <td className="px-2 py-1.5 border text-center text-[10px]">
                      {r.danger?.dangerHorse ? (
                        <span className="text-orange-600 font-bold" title={`${r.danger.dangerHorse.horseName}: 人気${r.danger.dangerHorse.oddsRank}位 → V${r.danger.dangerHorse.rankV}位 (gap ${r.danger.dangerScore})`}>
                          {r.danger.dangerHorse.umaban}{r.danger.dangerHorse.horseName.slice(0, 3)}
                          <span className="text-orange-400 ml-0.5">+{r.danger.dangerScore}</span>
                        </span>
                      ) : '-'}
                    </td>
                    {hasResults && (() => {
                      const fp = getFinishPos?.(r.race.race_id, r.entry.umaban) ?? 0;
                      const dbEntry = dbResults?.[r.race.race_id]?.[r.entry.umaban];
                      const isWinHit = fp === 1;
                      const isPlaceHit = fp >= 1 && fp <= 3;
                      let payout = 0;
                      if (isWinHit && r.betAmountWin > 0 && dbEntry?.confirmedWinOdds) {
                        payout += Math.floor(dbEntry.confirmedWinOdds * r.betAmountWin / 100) * 100;
                      }
                      if (isPlaceHit && r.betAmountPlace > 0 && dbEntry?.confirmedPlaceOddsMin) {
                        payout += Math.floor(dbEntry.confirmedPlaceOddsMin * r.betAmountPlace / 100) * 100;
                      }
                      return (
                        <>
                          <td className={`px-2 py-1.5 border text-center font-mono text-xs font-bold ${
                            fp === 0 ? 'text-gray-300' : isWinHit ? 'text-amber-600 bg-amber-50/60 dark:bg-amber-900/20' : isPlaceHit ? 'text-green-600 bg-green-50/40 dark:bg-green-900/10' : 'text-gray-400'}`}>
                            {fp > 0 ? `${fp}着` : '-'}
                          </td>
                          <td className={`px-2 py-1.5 border text-center font-mono text-xs ${payout > 0 ? 'text-emerald-700 font-bold' : 'text-gray-300'}`}>
                            {payout > 0 ? `¥${payout.toLocaleString()}` : fp > 0 ? '¥0' : '-'}
                          </td>
                        </>
                      );
                    })()}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* 結果サマリー（レース結果がある場合） */}
        {hasResults && (() => {
          let totalInvest = 0;
          let totalReturn = 0;
          let winHits = 0;
          let placeHits = 0;
          let totalBets = 0;
          let settledBets = 0;
          for (const r of sortedBetRecommendations) {
            const fp = getFinishPos?.(r.race.race_id, r.entry.umaban) ?? 0;
            const dbEntry = dbResults?.[r.race.race_id]?.[r.entry.umaban];
            const invest = r.betAmountWin + r.betAmountPlace;
            totalBets++;
            if (fp > 0) {
              settledBets++;
              totalInvest += invest;
              if (fp === 1 && r.betAmountWin > 0 && dbEntry?.confirmedWinOdds) {
                totalReturn += Math.floor(dbEntry.confirmedWinOdds * r.betAmountWin / 100) * 100;
                winHits++;
              }
              if (fp <= 3 && r.betAmountPlace > 0 && dbEntry?.confirmedPlaceOddsMin) {
                totalReturn += Math.floor(dbEntry.confirmedPlaceOddsMin * r.betAmountPlace / 100) * 100;
                placeHits++;
              }
            }
          }
          const roi = totalInvest > 0 ? (totalReturn / totalInvest * 100) : 0;
          const profit = totalReturn - totalInvest;
          if (settledBets === 0) return null;
          return (
            <div className={`mt-4 p-3 rounded-lg border ${profit >= 0 ? 'bg-emerald-50/50 dark:bg-emerald-900/10 border-emerald-200 dark:border-emerald-800' : 'bg-red-50/50 dark:bg-red-900/10 border-red-200 dark:border-red-800'}`}>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center text-sm">
                <div>
                  <div className="text-lg font-bold">¥{totalInvest.toLocaleString()}</div>
                  <div className="text-[10px] text-muted-foreground">投資額({settledBets}/{totalBets}件確定)</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-emerald-600">¥{totalReturn.toLocaleString()}</div>
                  <div className="text-[10px] text-muted-foreground">回収額</div>
                </div>
                <div>
                  <div className={`text-lg font-bold ${profit >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {profit >= 0 ? '+' : ''}¥{profit.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-muted-foreground">収支</div>
                </div>
                <div>
                  <div className={`text-lg font-bold ${roi >= 100 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {roi.toFixed(1)}%
                  </div>
                  <div className="text-[10px] text-muted-foreground">ROI</div>
                </div>
                <div>
                  <div className="text-lg font-bold">
                    <span className="text-red-600">{winHits}</span>/<span className="text-blue-600">{placeHits}</span>
                  </div>
                  <div className="text-[10px] text-muted-foreground">単勝/複勝 的中</div>
                </div>
              </div>
            </div>
          );
        })()}

        <div className="mt-3 text-[10px] text-muted-foreground">
          購入プランエンジン / {allocMode === 'equal' ? '均等配分' : '傾斜配分'} / 日予算 &yen;{dailyBudget.toLocaleString()} / 最低 &yen;{BET_CONFIG.minBet}
        </div>
      </CardContent>
    </Card>
  );
}
