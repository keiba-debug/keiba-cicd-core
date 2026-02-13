'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import type { PredictionsLive, PredictionRace, PredictionEntry } from '@/lib/data/predictions-reader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

// --- DB Odds types (API response) ---

interface DbOddsHorse {
  umaban: number;
  winOdds: number | null;
}

interface DbOddsResponse {
  raceId: string;
  source: 'timeseries' | 'final' | 'none';
  snapshotTime: string | null;
  horses: DbOddsHorse[];
}

type OddsMap = Record<string, Record<number, number>>; // raceId -> umaban -> winOdds

// --- ヘルパー ---

function getGapColor(gap: number): string {
  if (gap >= 5) return 'text-red-600 font-bold';
  if (gap >= 4) return 'text-orange-600 font-bold';
  if (gap >= 3) return 'text-amber-600 font-semibold';
  if (gap >= 2) return 'text-blue-600';
  return 'text-gray-500';
}

function getGapBg(gap: number): string {
  if (gap >= 5) return 'bg-red-50 dark:bg-red-900/20';
  if (gap >= 4) return 'bg-orange-50 dark:bg-orange-900/20';
  if (gap >= 3) return 'bg-amber-50 dark:bg-amber-900/20';
  return '';
}

function getMarkColor(mark: string): string {
  if (mark === '◎') return 'text-red-600 font-bold';
  if (mark === '◯' || mark === '○') return 'text-blue-600 font-bold';
  if (mark === '▲') return 'text-green-600 font-bold';
  if (mark === '△') return 'text-orange-500';
  return 'text-gray-400';
}

function getEvColor(ev: number): string {
  if (ev >= 2.0) return 'text-emerald-600 font-bold';
  if (ev >= 1.5) return 'text-green-600 font-bold';
  if (ev >= 1.0) return 'text-green-500 font-semibold';
  if (ev >= 0.8) return 'text-yellow-600';
  return 'text-gray-400';
}

function getRaceLink(race: PredictionRace): string {
  const [y, m, d] = [race.date.slice(0, 4), race.date.slice(5, 7), race.date.slice(8, 10)];
  return `/races-v2/${y}-${m}-${d}/${race.venue_name}/${race.race_id}`;
}

function getTrackBadgeClass(trackType: string): string {
  if (trackType === '芝') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
  if (trackType === 'ダ') return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300';
  return 'bg-gray-100 text-gray-600';
}

function getWinOdds(odds: OddsMap, raceId: string, umaban: number, fallback: number): number | null {
  const raceOdds = odds[raceId];
  if (raceOdds && raceOdds[umaban] > 0) return raceOdds[umaban];
  if (fallback > 0) return fallback;
  return null;
}

function calcEv(probV: number, winOdds: number | null): number | null {
  if (!winOdds || winOdds <= 0) return null;
  return probV * winOdds;
}

// --- メインコンポーネント ---

export function PredictionsContent({ data }: { data: PredictionsLive }) {
  const [oddsMap, setOddsMap] = useState<OddsMap>({});
  const [oddsSource, setOddsSource] = useState<string>('');
  const [oddsTime, setOddsTime] = useState<string | null>(null);
  const [oddsLoading, setOddsLoading] = useState(true);

  const isToday = useMemo(() => {
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    return data.date === todayStr;
  }, [data.date]);

  const raceIds = useMemo(() => data.races.map(r => r.race_id), [data.races]);

  const fetchAllOdds = useCallback(async () => {
    try {
      const results = await Promise.all(
        raceIds.map(id =>
          fetch(`/api/odds/db-latest?raceId=${id}`)
            .then(r => r.json() as Promise<DbOddsResponse>)
            .catch(() => null)
        )
      );

      const newOdds: OddsMap = {};
      let src = '';
      let time: string | null = null;

      for (const result of results) {
        if (!result || !result.horses) continue;
        const h: Record<number, number> = {};
        for (const horse of result.horses) {
          if (horse.winOdds && horse.winOdds > 0) h[horse.umaban] = horse.winOdds;
        }
        if (Object.keys(h).length > 0) newOdds[result.raceId] = h;
        if (!src && result.source !== 'none') src = result.source;
        if (!time && result.snapshotTime) time = result.snapshotTime;
      }

      setOddsMap(newOdds);
      setOddsSource(src);
      setOddsTime(time);
    } catch {
      // ignore
    } finally {
      setOddsLoading(false);
    }
  }, [raceIds]);

  useEffect(() => {
    fetchAllOdds();
    if (isToday) {
      const interval = setInterval(fetchAllOdds, 30000);
      return () => clearInterval(interval);
    }
  }, [fetchAllOdds, isToday]);

  const { races, summary } = data;

  // 開催場ごとにグループ化
  const venueGroups = useMemo(() => {
    const map = new Map<string, PredictionRace[]>();
    for (const race of races) {
      const group = map.get(race.venue_name) || [];
      group.push(race);
      map.set(race.venue_name, group);
    }
    return map;
  }, [races]);

  // VB候補一覧
  const allVBEntries = useMemo(() => {
    const entries: Array<{ race: PredictionRace; entry: PredictionEntry }> = [];
    for (const race of races) {
      for (const entry of race.entries) {
        if (entry.is_value_bet) entries.push({ race, entry });
      }
    }
    entries.sort((a, b) => b.entry.vb_gap - a.entry.vb_gap);
    return entries;
  }, [races]);

  // 統計
  const stats = useMemo(() => {
    let totalVB = 0;
    let totalEntries = 0;
    let evPositiveCount = 0;
    const venueMap = new Map<string, { races: number; vb: number }>();

    for (const race of races) {
      totalEntries += race.entries.length;
      const vbCount = race.entries.filter(e => e.is_value_bet).length;
      totalVB += vbCount;
      const v = venueMap.get(race.venue_name) || { races: 0, vb: 0 };
      v.races++;
      v.vb += vbCount;
      venueMap.set(race.venue_name, v);

      for (const entry of race.entries) {
        const odds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
        const ev = calcEv(entry.pred_proba_v, odds);
        if (ev !== null && ev >= 1.0) evPositiveCount++;
      }
    }

    return { totalVB, totalEntries, venueMap, evPositiveCount };
  }, [races, oddsMap]);

  const hasOdds = Object.keys(oddsMap).length > 0;

  return (
    <div className="py-6">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">ML予測一覧</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data.date} / Model v{data.model_version} / オッズ: {data.odds_source}
            {data.db_odds_coverage && ` (${data.db_odds_coverage})`}
          </p>
        </div>
        <div className="text-right text-sm text-muted-foreground">
          <div>生成: {new Date(data.created_at).toLocaleString('ja-JP')}</div>
          {hasOdds && (
            <div className="text-xs mt-0.5">
              DBオッズ: {oddsSource === 'timeseries' ? '時系列' : '確定'}
              {oddsTime && ` (${oddsTime})`}
              {isToday && ' 🔄30秒更新'}
            </div>
          )}
          {oddsLoading && <div className="text-xs mt-0.5">オッズ読込中...</div>}
        </div>
      </div>

      {/* サマリーカード */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold">{summary.total_races}</div>
            <div className="text-xs text-muted-foreground">レース</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold">{summary.total_entries}</div>
            <div className="text-xs text-muted-foreground">出走頭数</div>
          </CardContent>
        </Card>
        <Card className="border-amber-200 dark:border-amber-800">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold text-amber-600">{stats.totalVB}</div>
            <div className="text-xs text-muted-foreground">VB候補 (gap&ge;3)</div>
          </CardContent>
        </Card>
        <Card className="border-emerald-200 dark:border-emerald-800">
          <CardContent className="pt-4 pb-3 text-center">
            <div className={`text-3xl font-bold ${hasOdds ? 'text-emerald-600' : 'text-muted-foreground'}`}>
              {hasOdds ? stats.evPositiveCount : '-'}
            </div>
            <div className="text-xs text-muted-foreground">EV&ge;1.0</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold">{Array.from(stats.venueMap.keys()).join(' / ')}</div>
            <div className="text-xs text-muted-foreground">開催場</div>
          </CardContent>
        </Card>
      </div>

      {/* VB候補ハイライト */}
      {allVBEntries.length > 0 && (
        <Card className="mb-8 border-amber-200 dark:border-amber-800">
          <CardHeader className="pb-2 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950 dark:to-orange-950">
            <CardTitle className="text-lg flex items-center gap-2">
              Value Bet 候補 ({allVBEntries.length}頭)
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-100 dark:bg-gray-800 text-xs">
                    <th className="px-2 py-2 text-left border">場</th>
                    <th className="px-2 py-2 text-center border">R</th>
                    <th className="px-2 py-2 text-center border">馬番</th>
                    <th className="px-2 py-2 text-left border">馬名</th>
                    <th className="px-2 py-2 text-center border" title="競馬ブック本紙予想の印">本紙</th>
                    <th className="px-2 py-2 text-center border" title="Value順位：市場非依存モデル(B)の予測順位">VR</th>
                    <th className="px-2 py-2 text-center border" title="オッズ順人気">人気</th>
                    <th className="px-2 py-2 text-center border" title="単勝オッズ（DB最新）">倍率</th>
                    <th className="px-2 py-2 text-center border" title="人気 - VR：市場評価とモデル評価の乖離（大きいほど過小評価）">Gap</th>
                    <th className="px-2 py-2 text-center border bg-emerald-50 dark:bg-emerald-900/30" title="期待値 = V確率 × 単勝オッズ（1.0以上がプラス期待値）">EV</th>
                    <th className="px-2 py-2 text-center border" title="Model A（精度モデル）の勝率予測 — オッズ情報を含む全特徴量使用">A%</th>
                    <th className="px-2 py-2 text-center border" title="Model V（市場非依存モデル）の勝率予測 — オッズ情報を使わない">V%</th>
                    <th className="px-2 py-2 text-center border" title="競馬ブック調教評価の矢印">調教</th>
                    <th className="px-2 py-2 text-left border" title="競馬ブック短評コメント">短評</th>
                  </tr>
                </thead>
                <tbody>
                  {allVBEntries.map(({ race, entry }) => {
                    const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
                    const ev = calcEv(entry.pred_proba_v, winOdds);
                    return (
                      <tr
                        key={`${race.race_id}-${entry.umaban}`}
                        className={`border-b hover:bg-blue-50/50 dark:hover:bg-blue-900/10 ${getGapBg(entry.vb_gap)}`}
                      >
                        <td className="px-2 py-1.5 border text-xs">
                          <Link href={getRaceLink(race)} target="_blank" className="hover:text-blue-600 hover:underline">
                            {race.venue_name}
                          </Link>
                        </td>
                        <td className="px-2 py-1.5 border text-center font-bold">
                          <Link href={getRaceLink(race)} target="_blank" className="hover:text-blue-600 hover:underline">
                            {race.race_number}
                          </Link>
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono">{entry.umaban}</td>
                        <td className="px-2 py-1.5 border font-bold">{entry.horse_name}</td>
                        <td className={`px-2 py-1.5 border text-center ${getMarkColor(entry.kb_mark)}`}>
                          {entry.kb_mark || '-'}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono font-bold text-blue-600">{entry.rank_v}</td>
                        <td className="px-2 py-1.5 border text-center font-mono">{entry.odds_rank || '-'}</td>
                        <td className="px-2 py-1.5 border text-center font-mono font-bold">
                          {winOdds ? winOdds.toFixed(1) : '-'}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono ${getGapColor(entry.vb_gap)}`}>
                          +{entry.vb_gap}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono ${ev !== null ? getEvColor(ev) : 'text-gray-300'} bg-emerald-50/50 dark:bg-emerald-900/10`}>
                          {ev !== null ? ev.toFixed(2) : '-'}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono text-xs">
                          {(entry.pred_proba_a * 100).toFixed(1)}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono text-xs">
                          {(entry.pred_proba_v * 100).toFixed(1)}
                        </td>
                        <td className="px-2 py-1.5 border text-center">{entry.kb_training_arrow}</td>
                        <td className="px-2 py-1.5 border text-xs text-muted-foreground max-w-[200px] truncate">
                          {entry.kb_comment}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 開催場別レース一覧 */}
      <div className="space-y-8">
        {Array.from(venueGroups.entries()).map(([venue, venueRaces]) => (
          <div key={venue}>
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              {venue}
              <Badge variant="outline">{venueRaces.length}R</Badge>
              <Badge variant="secondary" className="text-xs">
                VB: {venueRaces.reduce((s, r) => s + r.entries.filter(e => e.is_value_bet).length, 0)}頭
              </Badge>
            </h2>

            <div className="space-y-4">
              {venueRaces.sort((a, b) => a.race_number - b.race_number).map((race) => (
                <RaceCard key={race.race_id} race={race} oddsMap={oddsMap} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- レースカード ---

function RaceCard({ race, oddsMap }: { race: PredictionRace; oddsMap: OddsMap }) {
  const vbEntries = race.entries.filter(e => e.is_value_bet);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="py-3 px-4 border-b bg-muted/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href={getRaceLink(race)}
              target="_blank"
              className="text-lg font-bold hover:text-blue-600 hover:underline"
            >
              {race.race_number}R
            </Link>
            <Badge className={`text-[10px] ${getTrackBadgeClass(race.track_type)}`}>
              {race.track_type}{race.distance}m
            </Badge>
            <span className="text-sm text-muted-foreground">{race.num_runners}頭</span>
          </div>
          <div className="flex items-center gap-2">
            {vbEntries.length > 0 && (
              <Badge variant="outline" className="text-amber-600 border-amber-300">
                VB {vbEntries.length}頭
              </Badge>
            )}
            <Link
              href={getRaceLink(race)}
              target="_blank"
              className="text-xs text-blue-600 hover:underline"
            >
              詳細 →
            </Link>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800/50 text-xs">
                <th className="px-2 py-1.5 text-center border-b w-10">番</th>
                <th className="px-2 py-1.5 text-left border-b min-w-[100px]">馬名</th>
                <th className="px-2 py-1.5 text-center border-b w-10" title="競馬ブック本紙予想の印">紙</th>
                <th className="px-2 py-1.5 text-center border-b w-12" title="Model A（精度モデル）の順位 — 全特徴量使用">A順</th>
                <th className="px-2 py-1.5 text-center border-b w-12" title="Model V（市場非依存モデル）の順位 — オッズ不使用">V順</th>
                <th className="px-2 py-1.5 text-center border-b w-10" title="オッズ順人気">人</th>
                <th className="px-2 py-1.5 text-center border-b w-14" title="単勝オッズ（DB最新）">倍率</th>
                <th className="px-2 py-1.5 text-center border-b w-12" title="人気 - VR：市場評価とモデル評価の乖離">Gap</th>
                <th className="px-2 py-1.5 text-center border-b w-14 bg-emerald-50/50 dark:bg-emerald-900/20" title="期待値 = V確率 × オッズ（1.0以上がプラス期待値）">EV</th>
                <th className="px-2 py-1.5 text-center border-b w-14" title="Model A 勝率予測（%）">A%</th>
                <th className="px-2 py-1.5 text-center border-b w-14" title="Model V 勝率予測（%）">V%</th>
                <th className="px-2 py-1.5 text-center border-b w-14" title="競馬ブックレイティング">Rate</th>
                <th className="px-2 py-1.5 text-center border-b w-10" title="競馬ブック調教評価">調</th>
                <th className="px-2 py-1.5 text-left border-b" title="競馬ブック短評">短評</th>
              </tr>
            </thead>
            <tbody>
              {race.entries.map((entry) => {
                const isVB = entry.is_value_bet;
                const isTopA = entry.rank_a <= 3;
                const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
                const ev = calcEv(entry.pred_proba_v, winOdds);
                return (
                  <tr
                    key={entry.umaban}
                    className={`border-b transition-colors ${
                      isVB ? getGapBg(entry.vb_gap) :
                      isTopA ? 'bg-blue-50/30 dark:bg-blue-900/5' : ''
                    } hover:bg-blue-50/50 dark:hover:bg-blue-900/10`}
                  >
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.umaban}</td>
                    <td className="px-2 py-1 font-bold text-xs">
                      {entry.horse_name}
                      {isVB && <span className="ml-1 text-amber-500 text-[10px]">VB</span>}
                    </td>
                    <td className={`px-2 py-1 text-center ${getMarkColor(entry.kb_mark)}`}>
                      {entry.kb_mark || '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.rank_a <= 3 ? 'font-bold text-blue-600' : ''}`}>
                      {entry.rank_a}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.rank_v <= 3 ? 'font-bold text-purple-600' : ''}`}>
                      {entry.rank_v}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.odds_rank || '-'}</td>
                    <td className="px-2 py-1 text-center font-mono text-xs font-bold">
                      {winOdds ? winOdds.toFixed(1) : '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.vb_gap >= 3 ? getGapColor(entry.vb_gap) : 'text-gray-400'}`}>
                      {entry.vb_gap > 0 ? `+${entry.vb_gap}` : entry.vb_gap === 0 ? '0' : entry.vb_gap}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${ev !== null ? getEvColor(ev) : 'text-gray-300'} bg-emerald-50/30 dark:bg-emerald-900/10`}>
                      {ev !== null ? ev.toFixed(2) : '-'}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{(entry.pred_proba_a * 100).toFixed(1)}</td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{(entry.pred_proba_v * 100).toFixed(1)}</td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.kb_rating > 0 ? entry.kb_rating.toFixed(1) : '-'}</td>
                    <td className="px-2 py-1 text-center text-xs">{entry.kb_training_arrow}</td>
                    <td className="px-2 py-1 text-xs text-muted-foreground truncate max-w-[180px]">{entry.kb_comment}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
