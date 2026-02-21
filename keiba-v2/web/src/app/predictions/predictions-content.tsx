'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Badge } from '@/components/ui/badge';
import type { PredictionsLive, PredictionRace, PredictionEntry, RaceResultsMap } from '@/lib/data/predictions-reader';

// lib
import type { DbOddsResponse, OddsMap, DbResultsMap, DbResultEntry, DbResultsResponse, BetRecommendation, DangerHorseEntry, SortState, BetStrategyParams, BetPresetKey } from './lib/types';
import {
  getWinOdds, getPlaceOddsMin, calcWinEv, calcPlaceEv, calcHeadRatio,
  isTurf, isDirt, getPlaceLimit, getRaceDanger,
} from './lib/helpers';
import { BET_CONFIG, BET_PRESETS, getDefaultParams, getBuyRecommendation, calcKellyFraction, getEmpiricalRates } from './lib/bet-logic';

// components
import { DateNav } from './components/date-nav';
import { SummaryCards } from './components/summary-cards';
import { FilterBar } from './components/filter-bar';
import { SectionNav } from './components/section-nav';
import { RoiSummary } from './components/roi-summary';
import { BetRecommendations } from './components/bet-recommendations';
import { VBTable } from './components/vb-table';
import { RaceCard } from './components/race-card';
import { DangerResults } from './components/danger-results';

// --- メインコンポーネント ---

interface PredictionsContentProps {
  data: PredictionsLive;
  availableDates?: string[];
  currentDate?: string;
  isArchive?: boolean;
  results?: RaceResultsMap;
}

export function PredictionsContent({ data, availableDates = [], currentDate = '', isArchive = false, results }: PredictionsContentProps) {
  const [oddsMap, setOddsMap] = useState<OddsMap>({});
  const [oddsSource, setOddsSource] = useState<string>('');
  const [oddsTime, setOddsTime] = useState<string | null>(null);
  const [oddsLoading, setOddsLoading] = useState(true);
  const [dbResults, setDbResults] = useState<DbResultsMap>({});

  // フィルタ state
  const [venueFilter, setVenueFilter] = useState<string>('all');
  const [raceNumFilter, setRaceNumFilter] = useState<number>(0);
  const [trackFilter, setTrackFilter] = useState<string>('all');
  const [minGap, setMinGap] = useState<number>(3);
  const [minEv, setMinEv] = useState<number>(0);

  // ソート
  const [vbSort, setVbSort] = useState<SortState>({ key: 'gap', dir: 'desc' });
  const [betSort, setBetSort] = useState<SortState>({ key: 'amount', dir: 'desc' });

  // TARGET馬印2 VB印反映
  const [markSyncing, setMarkSyncing] = useState(false);
  const [markResult, setMarkResult] = useState<{ marks: Record<string, number>; markedHorses: number } | null>(null);

  // 推奨買い目 予算設定
  const [dailyBudget, setDailyBudget] = useState<number>(BET_CONFIG.defaultBudget);
  useEffect(() => {
    const saved = localStorage.getItem('keiba_daily_budget');
    if (saved) setDailyBudget(Number(saved));
  }, []);
  const updateBudget = useCallback((value: number) => {
    const v = Math.max(1000, Math.round(value / 1000) * 1000);
    setDailyBudget(v);
    localStorage.setItem('keiba_daily_budget', String(v));
  }, []);

  // 推奨買い目 戦略パラメータ
  const [betParams, setBetParams] = useState<BetStrategyParams>(getDefaultParams);
  const [betPreset, setBetPreset] = useState<BetPresetKey | 'custom'>('standard');
  useEffect(() => {
    const saved = localStorage.getItem('keiba_bet_params');
    const savedPreset = localStorage.getItem('keiba_bet_preset');
    if (saved) {
      try { setBetParams(JSON.parse(saved)); } catch { /* ignore */ }
    }
    if (savedPreset) setBetPreset(savedPreset as BetPresetKey | 'custom');
  }, []);
  const updateBetParams = useCallback((params: BetStrategyParams) => {
    setBetParams(params);
    localStorage.setItem('keiba_bet_params', JSON.stringify(params));
  }, []);
  const updateBetPreset = useCallback((preset: BetPresetKey) => {
    setBetPreset(preset);
    const params = { ...BET_PRESETS[preset] };
    setBetParams(params);
    localStorage.setItem('keiba_bet_preset', preset);
    localStorage.setItem('keiba_bet_params', JSON.stringify(params));
  }, []);
  const updateBetParamsCustom = useCallback((params: BetStrategyParams) => {
    setBetPreset('custom');
    setBetParams(params);
    localStorage.setItem('keiba_bet_preset', 'custom');
    localStorage.setItem('keiba_bet_params', JSON.stringify(params));
  }, []);

  // TARGET PD CSV
  const [betSyncing, setBetSyncing] = useState(false);
  const [betSyncResult, setBetSyncResult] = useState<{ totalBets: number; winBets: number; placeBets: number; racesWritten: number; totalAmount: number; filePath: string } | null>(null);

  const isToday = useMemo(() => {
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    return data.date === todayStr;
  }, [data.date]);

  const raceIds = useMemo(() => data.races.map(r => r.race_id), [data.races]);

  // --- データフェッチ ---

  const fetchAllOdds = useCallback(async () => {
    try {
      const ts = Date.now();
      const results = await Promise.all(
        raceIds.map(id =>
          fetch(`/api/odds/db-latest?raceId=${id}&_t=${ts}`, { cache: 'no-store' })
            .then(r => r.json() as Promise<DbOddsResponse>)
            .catch(() => null)
        )
      );

      const newOdds: OddsMap = {};
      let src = '';
      let time: string | null = null;

      for (const result of results) {
        if (!result || !result.horses) continue;
        const h: Record<number, { winOdds: number; placeOddsMin: number | null; placeOddsMax: number | null }> = {};
        for (const horse of result.horses) {
          if (horse.winOdds && horse.winOdds > 0) {
            h[horse.umaban] = {
              winOdds: horse.winOdds,
              placeOddsMin: horse.placeOddsMin ?? null,
              placeOddsMax: horse.placeOddsMax ?? null,
            };
          }
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

  const fetchDbResults = useCallback(async () => {
    try {
      const resp = await fetch(`/api/results/db-results?date=${data.date}`);
      const json = await resp.json() as DbResultsResponse;
      if (json.results && json.totalRaces > 0) {
        const map: DbResultsMap = {};
        for (const [raceId, entries] of Object.entries(json.results)) {
          map[raceId] = {};
          for (const e of entries) {
            map[raceId][e.umaban] = e;
          }
        }
        setDbResults(map);
      }
    } catch {
      // ignore
    }
  }, [data.date]);

  useEffect(() => {
    fetchAllOdds();
    fetchDbResults();
    if (isToday) {
      const interval = setInterval(() => { fetchAllOdds(); fetchDbResults(); }, 30000);
      return () => clearInterval(interval);
    }
  }, [fetchAllOdds, fetchDbResults, isToday]);

  const { races, summary } = data;

  // --- 派生データ ---

  const venues = useMemo(() => {
    const set = new Set<string>();
    for (const race of races) set.add(race.venue_name);
    return Array.from(set);
  }, [races]);

  const raceNumbers = useMemo(() => {
    const filtered = venueFilter === 'all' ? races : races.filter(r => r.venue_name === venueFilter);
    const nums = new Set<number>();
    for (const race of filtered) nums.add(race.race_number);
    return Array.from(nums).sort((a, b) => a - b);
  }, [races, venueFilter]);

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

  const filteredVBEntries = useMemo(() => {
    let entries = allVBEntries;
    if (minGap > 3) entries = entries.filter(e => e.entry.vb_gap >= minGap);
    if (venueFilter !== 'all') entries = entries.filter(e => e.race.venue_name === venueFilter);
    if (trackFilter !== 'all') {
      entries = entries.filter(e =>
        trackFilter === 'turf' ? isTurf(e.race.track_type) : isDirt(e.race.track_type)
      );
    }
    if (raceNumFilter > 0) entries = entries.filter(e => e.race.race_number === raceNumFilter);
    if (minEv > 0) {
      entries = entries.filter(e => {
        const winOdds = getWinOdds(oddsMap, e.race.race_id, e.entry.umaban, e.entry.odds);
        const ev = calcWinEv(e.entry, winOdds);
        return ev !== null && ev >= minEv;
      });
    }
    return entries;
  }, [allVBEntries, venueFilter, trackFilter, raceNumFilter, minGap, minEv, oddsMap]);

  const filteredVenueGroups = useMemo(() => {
    let filtered = races;
    if (venueFilter !== 'all') filtered = filtered.filter(r => r.venue_name === venueFilter);
    if (trackFilter !== 'all') {
      filtered = filtered.filter(r =>
        trackFilter === 'turf' ? isTurf(r.track_type) : isDirt(r.track_type)
      );
    }
    if (raceNumFilter > 0) filtered = filtered.filter(r => r.race_number === raceNumFilter);
    const map = new Map<string, PredictionRace[]>();
    for (const race of filtered) {
      const group = map.get(race.venue_name) || [];
      group.push(race);
      map.set(race.venue_name, group);
    }
    return map;
  }, [races, venueFilter, trackFilter, raceNumFilter]);

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
        const ev = calcWinEv(entry, odds);
        if (ev !== null && ev >= 1.0) evPositiveCount++;
      }
    }

    return { totalVB, totalEntries, venueMap, evPositiveCount };
  }, [races, oddsMap]);

  const hasOdds = Object.keys(oddsMap).length > 0;
  const hasDbResults = Object.keys(dbResults).length > 0;
  const hasResults = hasDbResults || (results ? Object.keys(results).length > 0 : false);

  const getFinishPos = useCallback((raceId: string, umaban: number): number => {
    const dbEntry = dbResults[raceId]?.[umaban];
    if (dbEntry) return dbEntry.finishPosition;
    const jsonEntry = results?.[raceId]?.[umaban];
    return jsonEntry?.finish_position ?? 0;
  }, [dbResults, results]);

  // --- TARGET連携 ---

  const syncVbMarks = useCallback(async () => {
    setMarkSyncing(true);
    setMarkResult(null);
    try {
      const res = await fetch('/api/target-marks/auto-vb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: isArchive ? currentDate : undefined }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setMarkResult({ marks: data.summary.marks, markedHorses: data.summary.markedHorses });
    } catch (error) {
      console.error('[syncVbMarks] Error:', error);
      setMarkResult(null);
      alert(`VB印反映に失敗しました: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setMarkSyncing(false);
    }
  }, [isArchive, currentDate]);

  // --- 推奨買い目 ---
  // バックテスト実績確率ベースのEV + Kelly + 同一レース単勝制約

  const betRecommendations = useMemo<BetRecommendation[]>(() => {
    const recs: BetRecommendation[] = [];
    for (const race of races) {
      const danger = getRaceDanger(race.entries, betParams.dangerThreshold);
      const effectiveMinGap = danger.isDanger ? betParams.minGapDanger : betParams.minGap;

      for (const entry of race.entries) {
        if (entry.vb_gap < effectiveMinGap) continue;

        const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
        const placeOddsMin = getPlaceOddsMin(oddsMap, race.race_id, entry.umaban) ?? entry.place_odds_min ?? null;

        // EV = バックテストROI（gap別の実績回収率）
        const empirical = getEmpiricalRates(entry.vb_gap);
        const wEv = winOdds && winOdds > 0 ? empirical.winRoi : null;
        const pEv = placeOddsMin && placeOddsMin > 0 ? empirical.placeRoi : null;

        const hasWinEv = wEv !== null && wEv > betParams.minEvThreshold;
        const hasPlaceEv = pEv !== null && pEv > betParams.minEvThreshold;
        if (!hasWinEv && !hasPlaceEv) continue;

        const headRatio = calcHeadRatio(entry.pred_proba_wv, entry.pred_proba_v);
        const rec = getBuyRecommendation(
          race.track_type, entry.vb_gap, entry.rank_v, winOdds,
          betParams.betTypeMode, headRatio, betParams.headRatioThreshold,
        );
        if (!rec.type) continue;

        // Kelly: バックテスト実績確率ベース、Kelly fractionにキャップ
        const kellyWinRaw = winOdds && winOdds > 0 ? calcKellyFraction(empirical.winHitRate, winOdds) : 0;
        const kellyPlaceRaw = placeOddsMin && placeOddsMin > 0 ? calcKellyFraction(empirical.placeHitRate, placeOddsMin) : 0;
        const kellyWin = Math.min(kellyWinRaw, betParams.kellyCap);
        const kellyPlace = Math.min(kellyPlaceRaw, betParams.kellyCap);

        let finalType = rec.type;
        let useWin = finalType === '単勝' || finalType === '単複';
        let usePlace = finalType === '複勝' || finalType === '単複';

        // Place Kelly が0以下なら単勝にフォールバック
        if (usePlace && kellyPlace <= 0) {
          if (kellyWin > 0 && hasWinEv) {
            finalType = '単勝';
            useWin = true;
            usePlace = false;
          } else if (!useWin) {
            continue;
          }
        }
        // 単複で単勝Kellyが0以下 → 複勝のみに
        if (useWin && kellyWin <= 0) {
          if (usePlace && kellyPlace > 0) {
            finalType = '複勝';
            useWin = false;
          } else if (!usePlace) {
            continue;
          }
        }

        // 両方のKellyが0以下なら除外（単複で10≤odds<18.6の中穴馬で発生）
        if (kellyWin <= 0 && kellyPlace <= 0) continue;

        recs.push({
          race, entry,
          betType: finalType,
          strength: rec.strength,
          winEv: wEv,
          placeEv: pEv,
          kellyWin,
          kellyPlace,
          betAmountWin: 0,
          betAmountPlace: 0,
          danger: danger.isDanger ? danger : undefined,
        });
      }
    }

    // 同一レース単勝制約: 1レースで最もWin EVの高い馬のみ単勝
    const winByRace = new Map<string, BetRecommendation>();
    for (const r of recs) {
      if (r.betType === '単勝' || r.betType === '単複') {
        const existing = winByRace.get(r.race.race_id);
        if (!existing || (r.winEv ?? 0) > (existing.winEv ?? 0)) {
          winByRace.set(r.race.race_id, r);
        }
      }
    }
    // 単勝が選ばれなかった馬: 複勝にダウングレード or 除外
    for (const r of recs) {
      const isWinType = r.betType === '単勝' || r.betType === '単複';
      if (isWinType && winByRace.get(r.race.race_id) !== r) {
        if (r.betType === '単複') {
          r.betType = '複勝';
        } else {
          if (r.kellyPlace > 0 && r.placeEv && r.placeEv > betParams.minEvThreshold) {
            r.betType = '複勝';
          } else {
            r.betAmountWin = -1;  // 除外マーク
          }
        }
      }
    }
    const validRecs = recs.filter(r => r.betAmountWin !== -1);

    // Kelly金額計算
    const budget = dailyBudget;
    let totalRaw = 0;
    for (const r of validRecs) {
      const useWin = r.betType === '単勝' || r.betType === '単複';
      const usePlace = r.betType === '複勝' || r.betType === '単複';
      if (useWin) totalRaw += r.kellyWin * betParams.kellyFraction * budget;
      if (usePlace) totalRaw += r.kellyPlace * betParams.kellyFraction * budget;
    }

    const scale = totalRaw > budget ? budget / totalRaw : 1.0;

    for (const r of validRecs) {
      r.betAmountWin = 0;
      r.betAmountPlace = 0;
      const useWin = r.betType === '単勝' || r.betType === '単複';
      const usePlace = r.betType === '複勝' || r.betType === '単複';
      if (useWin && r.kellyWin > 0) {
        const raw = r.kellyWin * betParams.kellyFraction * budget * scale;
        r.betAmountWin = Math.max(BET_CONFIG.minBet, Math.round(raw / BET_CONFIG.betUnit) * BET_CONFIG.betUnit);
      }
      if (usePlace && r.kellyPlace > 0) {
        const raw = r.kellyPlace * betParams.kellyFraction * budget * scale;
        r.betAmountPlace = Math.max(BET_CONFIG.minBet, Math.round(raw / BET_CONFIG.betUnit) * BET_CONFIG.betUnit);
      }
    }

    // 単複で複勝≥単勝を保証
    for (const r of validRecs) {
      if (r.betType === '単複' && r.betAmountPlace < r.betAmountWin) {
        r.betAmountPlace = r.betAmountWin;
      }
    }

    validRecs.sort((a, b) => (b.betAmountWin + b.betAmountPlace) - (a.betAmountWin + a.betAmountPlace));
    return validRecs;
  }, [races, oddsMap, dailyBudget, betParams]);

  const betSummary = useMemo(() => {
    let winCount = 0, placeCount = 0, winTotal = 0, placeTotal = 0, evSum = 0, evCount = 0;
    const dangerRaceIds = new Set<string>();
    for (const r of betRecommendations) {
      if (r.betAmountWin > 0) { winCount++; winTotal += r.betAmountWin; }
      if (r.betAmountPlace > 0) { placeCount++; placeTotal += r.betAmountPlace; }
      // 期待回収額: 補正EVベース（バックテスト実績に基づく現実的な期待値）
      if (r.winEv && r.betAmountWin > 0) { evSum += r.winEv * r.betAmountWin; evCount += r.betAmountWin; }
      if (r.placeEv && r.betAmountPlace > 0) { evSum += r.placeEv * r.betAmountPlace; evCount += r.betAmountPlace; }
      if (r.danger?.isDanger) dangerRaceIds.add(r.race.race_id);
    }
    const avgEv = evCount > 0 ? evSum / evCount : 0;
    const totalAmount = winTotal + placeTotal;
    const expectedReturn = Math.round(evSum);
    return { winCount, placeCount, winTotal, placeTotal, totalAmount, avgEv, expectedReturn, totalBets: betRecommendations.length, dangerRaces: dangerRaceIds.size };
  }, [betRecommendations]);

  // --- 危険馬一覧 ---
  const dangerHorses = useMemo<DangerHorseEntry[]>(() => {
    const entries: DangerHorseEntry[] = [];
    for (const race of races) {
      for (const e of race.entries) {
        if (e.odds_rank > 0 && e.odds_rank <= 3) {
          const gap = e.rank_v - e.odds_rank;
          if (gap >= 5) {
            entries.push({ race, entry: e, dangerScore: gap, oddsRank: e.odds_rank, rankV: e.rank_v });
          }
        }
      }
    }
    entries.sort((a, b) => a.race.race_number - b.race.race_number || b.dangerScore - a.dangerScore);
    return entries;
  }, [races]);

  const sortedBetRecommendations = useMemo(() => {
    let recs = [...betRecommendations];
    if (venueFilter !== 'all') recs = recs.filter(r => r.race.venue_name === venueFilter);
    if (trackFilter !== 'all') recs = recs.filter(r => trackFilter === 'turf' ? isTurf(r.race.track_type) : isDirt(r.race.track_type));
    if (raceNumFilter > 0) recs = recs.filter(r => r.race.race_number === raceNumFilter);

    const { key, dir } = betSort;
    const mul = dir === 'asc' ? 1 : -1;
    recs.sort((a, b) => {
      let va: number, vb: number;
      switch (key) {
        case 'race': va = a.race.race_number; vb = b.race.race_number; break;
        case 'umaban': va = a.entry.umaban; vb = b.entry.umaban; break;
        case 'winEv': va = a.winEv ?? -1; vb = b.winEv ?? -1; break;
        case 'placeEv': va = a.placeEv ?? -1; vb = b.placeEv ?? -1; break;
        case 'gap': va = a.entry.vb_gap; vb = b.entry.vb_gap; break;
        case 'kelly': {
          const ka = a.betType === '複勝' ? a.kellyPlace : a.kellyWin;
          const kb = b.betType === '複勝' ? b.kellyPlace : b.kellyWin;
          va = ka; vb = kb; break;
        }
        case 'odds': {
          va = getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds) ?? 9999;
          vb = getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds) ?? 9999;
          break;
        }
        case 'head': {
          va = calcHeadRatio(a.entry.pred_proba_wv, a.entry.pred_proba_v) ?? -1;
          vb = calcHeadRatio(b.entry.pred_proba_wv, b.entry.pred_proba_v) ?? -1;
          break;
        }
        case 'danger': va = a.danger?.dangerScore ?? 0; vb = b.danger?.dangerScore ?? 0; break;
        default: va = a.betAmountWin + a.betAmountPlace; vb = b.betAmountWin + b.betAmountPlace; break;
      }
      return (va - vb) * mul;
    });
    return recs;
  }, [betRecommendations, betSort, venueFilter, trackFilter, raceNumFilter, oddsMap]);

  const syncBetMarks = useCallback(async () => {
    setBetSyncing(true);
    setBetSyncResult(null);
    try {
      await fetchAllOdds();
      await new Promise(r => setTimeout(r, 500));

      const bets = sortedBetRecommendations.flatMap(r => {
        const items: { raceId: string; umaban: number; betType: number; amount: number }[] = [];
        if (r.betAmountWin > 0) {
          items.push({ raceId: r.race.race_id, umaban: r.entry.umaban, betType: 0, amount: r.betAmountWin });
        }
        if (r.betAmountPlace > 0) {
          items.push({ raceId: r.race.race_id, umaban: r.entry.umaban, betType: 1, amount: r.betAmountPlace });
        }
        return items;
      });

      if (bets.length === 0) {
        alert('書込み対象の買い目がありません');
        return;
      }

      const res = await fetch('/api/target-marks/auto-bet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bets }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setBetSyncResult({
        totalBets: data.summary.totalBets,
        winBets: data.summary.winBets,
        placeBets: data.summary.placeBets,
        racesWritten: data.summary.racesWritten,
        totalAmount: data.summary.totalAmount,
        filePath: data.summary.filePath,
      });
    } catch (error) {
      console.error('[syncBetMarks] Error:', error);
      setBetSyncResult(null);
      alert(`TARGET書込み失敗: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBetSyncing(false);
    }
  }, [sortedBetRecommendations, fetchAllOdds]);

  // VBテーブル ソート
  const sortedVBEntries = useMemo(() => {
    const arr = [...filteredVBEntries];
    const { key, dir } = vbSort;
    const mul = dir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (key) {
        case 'race': va = a.race.race_number; vb = b.race.race_number; break;
        case 'umaban': va = a.entry.umaban; vb = b.entry.umaban; break;
        case 'rank_v': va = a.entry.rank_v; vb = b.entry.rank_v; break;
        case 'odds_rank': va = a.entry.odds_rank || 999; vb = b.entry.odds_rank || 999; break;
        case 'odds': {
          va = getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds) ?? 9999;
          vb = getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds) ?? 9999;
          break;
        }
        case 'ev': {
          va = getEmpiricalRates(a.entry.vb_gap).winRoi;
          vb = getEmpiricalRates(b.entry.vb_gap).winRoi;
          break;
        }
        case 'place_ev': {
          va = getEmpiricalRates(a.entry.vb_gap).placeRoi;
          vb = getEmpiricalRates(b.entry.vb_gap).placeRoi;
          break;
        }
        case 'head_ratio': {
          va = calcHeadRatio(a.entry.pred_proba_wv, a.entry.pred_proba_v) ?? -1;
          vb = calcHeadRatio(b.entry.pred_proba_wv, b.entry.pred_proba_v) ?? -1;
          break;
        }
        case 'prob_a': va = a.entry.pred_proba_a; vb = b.entry.pred_proba_a; break;
        case 'prob_v': va = a.entry.pred_proba_v; vb = b.entry.pred_proba_v; break;
        case 'win_gap': va = a.entry.win_vb_gap ?? -999; vb = b.entry.win_vb_gap ?? -999; break;
        case 'finish': {
          const pa = getFinishPos(a.race.race_id, a.entry.umaban);
          const pb = getFinishPos(b.race.race_id, b.entry.umaban);
          va = pa > 0 ? pa : 999;
          vb = pb > 0 ? pb : 999;
          break;
        }
        default: va = a.entry.vb_gap; vb = b.entry.vb_gap; break;
      }
      return (va - vb) * mul;
    });
    return arr;
  }, [filteredVBEntries, vbSort, oddsMap, getFinishPos]);

  // ROI計算
  const roiStats = useMemo(() => {
    if (!hasResults) return null;

    type TrackROI = {
      vbCount: number; winHits: number; placeHits: number;
      winPayout: number; placePayout: number; placeBetCount: number;
      hasAnyPlaceOdds: boolean;
    };
    const initTrack = (): TrackROI => ({ vbCount: 0, winHits: 0, placeHits: 0, winPayout: 0, placePayout: 0, placeBetCount: 0, hasAnyPlaceOdds: false });
    const all = initTrack();
    const turf = initTrack();
    const dirt = initTrack();

    for (const { race, entry } of filteredVBEntries) {
      const pos = getFinishPos(race.race_id, entry.umaban);
      if (pos <= 0) continue;

      const buckets = [all];
      if (isTurf(race.track_type)) buckets.push(turf);
      if (isDirt(race.track_type)) buckets.push(dirt);

      for (const b of buckets) {
        b.vbCount++;
        const placeLimit = getPlaceLimit(race.num_runners);
        const dbEntry = dbResults[race.race_id]?.[entry.umaban];
        const confirmedWinOdds = dbEntry?.confirmedWinOdds ?? (results?.[race.race_id]?.[entry.umaban]?.odds ?? 0);

        if (pos === 1 && confirmedWinOdds > 0) {
          b.winHits++;
          b.winPayout += confirmedWinOdds * 100;
        }

        if (placeLimit > 0) {
          const plOddsMin = dbEntry?.confirmedPlaceOddsMin ?? getPlaceOddsMin(oddsMap, race.race_id, entry.umaban);
          if (plOddsMin && plOddsMin > 0) {
            b.hasAnyPlaceOdds = true;
            b.placeBetCount++;
            if (pos <= placeLimit) {
              b.placeHits++;
              b.placePayout += plOddsMin * 100;
            }
          }
        }
      }
    }

    if (all.vbCount === 0) return null;

    const calcROI = (b: TrackROI) => ({
      vbCount: b.vbCount,
      winHits: b.winHits,
      placeHits: b.placeHits,
      placeBetCount: b.placeBetCount,
      winROI: b.vbCount > 0 ? (b.winPayout / (b.vbCount * 100)) * 100 : 0,
      placeROI: b.placeBetCount > 0 ? (b.placePayout / (b.placeBetCount * 100)) * 100 : 0,
      winProfit: b.winPayout - b.vbCount * 100,
      placeProfit: b.placeBetCount > 0 ? b.placePayout - b.placeBetCount * 100 : 0,
      hasAnyPlaceOdds: b.hasAnyPlaceOdds,
    });

    return { all: calcROI(all), turf: calcROI(turf), dirt: calcROI(dirt) };
  }, [filteredVBEntries, dbResults, results, hasResults, oddsMap, getFinishPos]);

  // --- レンダリング ---

  return (
    <div className="py-6">
      {/* 日付ナビゲーション */}
      {availableDates.length > 0 && (
        <DateNav dates={availableDates} currentDate={currentDate} isArchive={isArchive} />
      )}

      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Value Bet</h1>
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
      <SummaryCards
        totalRaces={summary.total_races}
        totalEntries={summary.total_entries}
        totalVB={stats.totalVB}
        evPositiveCount={stats.evPositiveCount}
        hasOdds={hasOdds}
        venueNames={Array.from(stats.venueMap.keys())}
      />

      {/* フィルタバー */}
      <FilterBar
        venues={venues}
        venueFilter={venueFilter}
        setVenueFilter={setVenueFilter}
        raceNumbers={raceNumbers}
        raceNumFilter={raceNumFilter}
        setRaceNumFilter={setRaceNumFilter}
        trackFilter={trackFilter}
        setTrackFilter={setTrackFilter}
        minGap={minGap}
        setMinGap={setMinGap}
        minEv={minEv}
        setMinEv={setMinEv}
        filteredCount={filteredVBEntries.length}
        totalCount={allVBEntries.length}
      />

      {/* セクションナビ */}
      <SectionNav
        hasResults={hasResults && roiStats != null}
        hasBets={betRecommendations.length > 0}
        hasVB={filteredVBEntries.length > 0}
        hasDanger={dangerHorses.length > 0}
      />

      {/* ROIサマリー */}
      {hasResults && roiStats && (
        <RoiSummary all={roiStats.all} turf={roiStats.turf} dirt={roiStats.dirt} />
      )}

      {/* 危険馬結果一覧 */}
      <DangerResults
        dangerHorses={dangerHorses}
        oddsMap={oddsMap}
        dbResults={dbResults}
        results={results}
        getFinishPos={getFinishPos}
      />

      {/* 推奨買い目 */}
      <BetRecommendations
        betRecommendations={betRecommendations}
        sortedBetRecommendations={sortedBetRecommendations}
        betSummary={betSummary}
        oddsMap={oddsMap}
        oddsLoading={oddsLoading}
        dailyBudget={dailyBudget}
        updateBudget={updateBudget}
        fetchAllOdds={fetchAllOdds}
        syncBetMarks={syncBetMarks}
        betSyncing={betSyncing}
        betSyncResult={betSyncResult}
        betSort={betSort}
        setBetSort={setBetSort}
        betParams={betParams}
        betPreset={betPreset}
        onPresetChange={updateBetPreset}
        onParamsChange={updateBetParamsCustom}
      />

      {/* VB候補 */}
      <VBTable
        sortedVBEntries={sortedVBEntries}
        filteredVBEntries={filteredVBEntries}
        oddsMap={oddsMap}
        dbResults={dbResults}
        results={results}
        hasResults={hasResults}
        getFinishPos={getFinishPos}
        vbSort={vbSort}
        setVbSort={setVbSort}
        syncVbMarks={syncVbMarks}
        markSyncing={markSyncing}
        markResult={markResult}
      />

      {/* 開催場別レース一覧 */}
      <div id="section-races" className="space-y-8">
        {Array.from(filteredVenueGroups.entries()).map(([venue, venueRaces]) => (
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
                <RaceCard key={race.race_id} race={race} oddsMap={oddsMap} results={results} dbResults={dbResults} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
