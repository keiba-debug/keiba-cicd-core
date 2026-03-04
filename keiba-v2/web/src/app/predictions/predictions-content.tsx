'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Badge } from '@/components/ui/badge';
import type { PredictionsLive, PredictionRace, PredictionEntry, RaceResultsMap } from '@/lib/data/predictions-reader';

// lib
import type { DbOddsResponse, OddsMap, DbResultsMap, DbResultEntry, DbResultsResponse, BetRecommendation, DangerHorseEntry, SortState } from './lib/types';
import {
  getWinOdds, getPlaceOddsMin, calcWinEv, calcPlaceEv, calcHeadRatio,
  isTurf, isDirt, getPlaceLimit, getRaceDanger, getStarScore,
} from './lib/helpers';
import { BET_CONFIG, BUDGET_PCT_OPTIONS, rescaleBudget, equalDistribute, type ServerPresetKey, type AllocMode } from './lib/bet-logic';
import { generateLiveRecommendations } from './lib/bet-engine';

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
import { MultiLegRecommendations } from './components/multi-leg-recommendations';

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
  const [minEv, setMinEv] = useState<number>(0);
  const [minArd, setMinArd] = useState<number | null>(null);
  const [betOnly, setBetOnly] = useState<boolean>(false);

  // ソート
  const [vbSort, setVbSort] = useState<SortState>({ key: 'race_number', dir: 'asc' });
  const [betSort, setBetSort] = useState<SortState>({ key: 'race_number', dir: 'asc' });

  // TARGET馬印2 VB印反映
  const [markSyncing, setMarkSyncing] = useState(false);
  const [markResult, setMarkResult] = useState<{ marks: Record<string, number>; markedHorses: number } | null>(null);
  const [dangerMarkSyncing, setDangerMarkSyncing] = useState(false);
  const [dangerMarkResult, setDangerMarkResult] = useState<{ markedHorses: number } | null>(null);

  // 推奨買い目 予算設定（bankroll連動）
  const [dailyBudget, setDailyBudget] = useState<number>(BET_CONFIG.defaultBudget);
  const [bankrollBalance, setBankrollBalance] = useState<number | null>(null);
  const [bankrollBudget, setBankrollBudget] = useState<number | null>(null); // 計算済み日次予算
  const [budgetLinked, setBudgetLinked] = useState<boolean>(true); // bankroll連動モード
  const [dailyLimitPct, setDailyLimitPct] = useState<number>(2); // 日次予算率(%) — v7.3推奨2%

  // bankroll予算を計算するヘルパー
  const computeBudget = useCallback((balance: number, pct: number) => {
    return Math.max(1000, Math.floor(balance * pct / 100 / 1000) * 1000);
  }, []);

  // bankroll API から現在資金と設定を取得
  useEffect(() => {
    const savedLinked = localStorage.getItem('keiba_budget_linked');
    if (savedLinked !== null) setBudgetLinked(savedLinked === 'true');

    const savedPct = localStorage.getItem('keiba_daily_limit_pct');
    if (savedPct !== null) setDailyLimitPct(Number(savedPct));

    Promise.all([
      fetch('/api/bankroll/fund').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/bankroll/config').then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([fund, config]) => {
      if (fund?.current_balance != null) {
        setBankrollBalance(fund.current_balance);
        const pct = savedPct !== null ? Number(savedPct) : (config?.settings?.daily_limit_percent ?? 5.0);
        setDailyLimitPct(pct);
        const computed = computeBudget(fund.current_balance, pct);
        setBankrollBudget(computed);

        // 連動モードならbankroll予算を適用
        const isLinked = savedLinked !== null ? savedLinked === 'true' : true;
        if (isLinked) {
          setDailyBudget(computed);
          return; // localStorage の値は使わない
        }
      }
      // 連動なし or 取得失敗 → localStorage
      const saved = localStorage.getItem('keiba_daily_budget');
      if (saved) setDailyBudget(Number(saved));
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateBudget = useCallback((value: number) => {
    const v = Math.max(1000, Math.round(value / 1000) * 1000);
    setDailyBudget(v);
    localStorage.setItem('keiba_daily_budget', String(v));
    // 手動変更したら連動解除
    if (bankrollBudget !== null && v !== bankrollBudget) {
      setBudgetLinked(false);
      localStorage.setItem('keiba_budget_linked', 'false');
    }
  }, [bankrollBudget]);

  const toggleBudgetLink = useCallback(() => {
    const next = !budgetLinked;
    setBudgetLinked(next);
    localStorage.setItem('keiba_budget_linked', String(next));
    if (next && bankrollBalance !== null) {
      const computed = computeBudget(bankrollBalance, dailyLimitPct);
      setBankrollBudget(computed);
      setDailyBudget(computed);
    }
  }, [budgetLinked, bankrollBalance, dailyLimitPct, computeBudget]);

  // 予算率変更
  const updateDailyLimitPct = useCallback((pct: number) => {
    setDailyLimitPct(pct);
    localStorage.setItem('keiba_daily_limit_pct', String(pct));

    // bankroll連動なら即座に予算再計算
    if (bankrollBalance !== null) {
      const computed = computeBudget(bankrollBalance, pct);
      setBankrollBudget(computed);
      if (budgetLinked) {
        setDailyBudget(computed);
      }
    }

    // config.json にも永続化 (fire-and-forget)
    fetch('/api/bankroll/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ daily_limit_percent: pct }),
    }).catch(() => {/* ignore */});
  }, [bankrollBalance, budgetLinked, computeBudget]);

  // 推奨買い目 プリセット選択（デフォルト: intersection）
  const [preset, setPreset] = useState<ServerPresetKey>('intersection');
  useEffect(() => {
    const saved = localStorage.getItem('keiba_bet_preset');
    if (saved && ['intersection', 'relaxed', 'ev_focus'].includes(saved)) {
      setPreset(saved as ServerPresetKey);
    }
  }, []);
  const updatePreset = useCallback((p: ServerPresetKey) => {
    setPreset(p);
    localStorage.setItem('keiba_bet_preset', p);
  }, []);

  // 配分モード（Kelly / 均等）— Intersection Filterでは均等配分が基本
  const [allocMode, setAllocMode] = useState<AllocMode>('equal');
  const updateAllocMode = useCallback((m: AllocMode) => {
    setAllocMode(m);
  }, []);

  // TARGET My印
  const [targetMarks, setTargetMarks] = useState<Record<string, Record<number, string>>>({});

  // TARGET PD CSV
  const [betSyncing, setBetSyncing] = useState(false);
  const [betSyncResult, setBetSyncResult] = useState<{ totalBets: number; winBets: number; placeBets: number; racesWritten: number; totalAmount: number; filePath: string } | null>(null);

  const isToday = useMemo(() => {
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    return data.date === todayStr;
  }, [data.date]);

  const raceIds = useMemo(() => data.races.map(r => r.race_id), [data.races]);

  // TARGET My印 一括フェッチ
  const fetchTargetMarks = useCallback(async () => {
    try {
      const res = await fetch('/api/target-marks/batch-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ races: data.races.map(r => ({ race_id: r.race_id, venue_name: r.venue_name })) }),
      });
      if (res.ok) {
        const json = await res.json();
        setTargetMarks(json.marks || {});
      }
    } catch {
      // ignore - marks are optional
    }
  }, [data.races]);

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
    fetchTargetMarks();
    if (isToday) {
      const interval = setInterval(() => { fetchAllOdds(); fetchDbResults(); }, 30000);
      return () => clearInterval(interval);
    }
  }, [fetchAllOdds, fetchDbResults, fetchTargetMarks, isToday]);

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

  // リアルタイムオッズから人気順を再計算（全レース共通）
  const liveRankingMap = useMemo(() => {
    const map: Record<string, Record<number, number>> = {};
    for (const race of races) {
      const raceOdds = oddsMap[race.race_id];
      if (!raceOdds) continue;
      const sorted = race.entries
        .map(e => ({ umaban: e.umaban, odds: raceOdds[e.umaban]?.winOdds ?? e.odds ?? 999 }))
        .filter(e => e.odds > 0)
        .sort((a, b) => a.odds - b.odds);
      const ranking: Record<number, number> = {};
      sorted.forEach((e, i) => { ranking[e.umaban] = i + 1; });
      map[race.race_id] = ranking;
    }
    return map;
  }, [races, oddsMap]);

  /** リアルタイムGap = liveOddsRank - rank_p（フォールバック: entry.vb_gap） */
  const getLiveGap = useCallback((raceId: string, entry: PredictionEntry) => {
    const liveRank = liveRankingMap[raceId]?.[entry.umaban];
    if (liveRank != null && liveRank > 0) return liveRank - entry.rank_p;
    return entry.vb_gap;
  }, [liveRankingMap]);

  const allVBEntries = useMemo(() => {
    const entries: Array<{ race: PredictionRace; entry: PredictionEntry }> = [];
    for (const race of races) {
      for (const entry of race.entries) {
        if (entry.is_value_bet) entries.push({ race, entry });
      }
    }
    entries.sort((a, b) => getLiveGap(b.race.race_id, b.entry) - getLiveGap(a.race.race_id, a.entry));
    return entries;
  }, [races, getLiveGap]);

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
      // フィルタ適用: 表示中のレースのみ対象
      let targetRaces = races;
      if (venueFilter !== 'all') targetRaces = targetRaces.filter(r => r.venue_name === venueFilter);
      if (trackFilter !== 'all') {
        targetRaces = targetRaces.filter(r =>
          trackFilter === 'turf' ? isTurf(r.track_type) : isDirt(r.track_type)
        );
      }
      if (raceNumFilter > 0) targetRaces = targetRaces.filter(r => r.race_number === raceNumFilter);

      // liveGapsを計算してAPIに送信（リアルタイムodds連動）
      const liveGaps: Record<string, Record<number, number>> = {};
      for (const race of targetRaces) {
        const gapMap: Record<number, number> = {};
        for (const entry of race.entries) {
          gapMap[entry.umaban] = getLiveGap(race.race_id, entry);
        }
        liveGaps[race.race_id] = gapMap;
      }
      const res = await fetch('/api/target-marks/auto-vb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: isArchive ? currentDate : undefined,
          liveGaps,
          raceIds: targetRaces.map(r => r.race_id),
        }),
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
  }, [isArchive, currentDate, races, venueFilter, trackFilter, raceNumFilter, getLiveGap]);

  // --- 推奨買い目 ---
  // ライブオッズがある場合は TypeScript bet-engine で再計算
  // フォールバック: サーバー側 bet_engine.py の静的 recommendations

  // オッズ取得済みなら常にTS版エンジンで再計算（最新ロジック適用）
  // 当日: ライブオッズで直前再計算 / アーカイブ: 確定オッズで再計算（max_win=2等の最新ルール適用）
  const hasLiveOdds = Object.keys(oddsMap).length > 0;

  const betRecommendations = useMemo<BetRecommendation[]>(() => {
    // オッズ取得済み → TS版エンジンで再計算
    const serverRecs = hasLiveOdds
      ? generateLiveRecommendations(races, oddsMap, preset, dailyBudget, allocMode)
      : (() => {
          const presetData = data.recommendations?.[preset];
          if (!presetData) return [];
          return allocMode === 'equal'
            ? equalDistribute(presetData.bets, dailyBudget)
            : rescaleBudget(presetData.bets, dailyBudget);
        })();

    if (serverRecs.length === 0) return [];

    // race/entry ルックアップ構築
    const raceMap = new Map<string, PredictionRace>();
    const entryMap = new Map<string, PredictionEntry>();
    for (const race of races) {
      raceMap.set(race.race_id, race);
      for (const entry of race.entries) {
        entryMap.set(`${race.race_id}-${entry.umaban}`, entry);
      }
    }

    const displayRecs: BetRecommendation[] = [];
    for (const sr of serverRecs) {
      const race = raceMap.get(sr.race_id);
      const entry = entryMap.get(`${sr.race_id}-${sr.umaban}`);
      if (!race || !entry) continue;

      const danger = getRaceDanger(race.entries);

      displayRecs.push({
        race,
        entry,
        betType: sr.bet_type,
        strength: sr.strength,
        winEv: sr.win_ev,
        placeEv: sr.place_ev,
        kellyFraction: sr.kelly_capped,
        betAmountWin: sr.win_amount,
        betAmountPlace: sr.place_amount,
        gap: sr.gap,
        devGap: sr.dev_gap ?? 0,
        vbScore: sr.vb_score ?? 0,
        winGap: sr.win_gap,
        predictedMargin: sr.predicted_margin,
        isDanger: sr.is_danger,
        danger: danger.isDanger ? danger : undefined,
      });
    }

    displayRecs.sort((a, b) => (b.betAmountWin + b.betAmountPlace) - (a.betAmountWin + a.betAmountPlace));
    return displayRecs;
  }, [data.recommendations, preset, dailyBudget, allocMode, races, oddsMap, hasLiveOdds]);

  // VBエントリ→bet推奨ルックアップ (race_id-umaban → BetRecommendation)
  const betRecMap = useMemo(() => {
    const m = new Map<string, BetRecommendation>();
    for (const r of betRecommendations) {
      m.set(`${r.race.race_id}-${r.entry.umaban}`, r);
    }
    return m;
  }, [betRecommendations]);

  const filteredVBEntries = useMemo(() => {
    let entries = allVBEntries;
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
    if (minArd !== null) {
      entries = entries.filter(e => e.entry.ar_deviation != null && e.entry.ar_deviation >= minArd);
    }
    if (betOnly) {
      entries = entries.filter(e => betRecMap.has(`${e.race.race_id}-${e.entry.umaban}`));
    }
    return entries;
  }, [allVBEntries, venueFilter, trackFilter, raceNumFilter, minEv, minArd, betOnly, oddsMap, getLiveGap, betRecMap]);

  const betSummary = useMemo(() => {
    let winCount = 0, placeCount = 0, winTotal = 0, placeTotal = 0;
    const dangerRaceIds = new Set<string>();
    for (const r of betRecommendations) {
      if (r.betAmountWin > 0) { winCount++; winTotal += r.betAmountWin; }
      if (r.betAmountPlace > 0) { placeCount++; placeTotal += r.betAmountPlace; }
      if (r.danger?.isDanger) dangerRaceIds.add(r.race.race_id);
    }
    const totalAmount = winTotal + placeTotal;
    return { winCount, placeCount, winTotal, placeTotal, totalAmount, totalBets: betRecommendations.length, dangerRaces: dangerRaceIds.size };
  }, [betRecommendations]);

  // --- 危険馬一覧 ---
  const dangerHorses = useMemo<DangerHorseEntry[]>(() => {
    const entries: DangerHorseEntry[] = [];
    for (const race of races) {
      for (const e of race.entries) {
        // 危険馬条件: odds<=8 & ARd<53 & P%<15% (v5.33)
        const liveOdds = oddsMap[race.race_id]?.[e.umaban]?.winOdds ?? e.odds;
        const ard = e.ar_deviation ?? 999;
        const predV = e.pred_proba_p ?? 0;
        if (liveOdds > 0 && liveOdds <= 8.0 && ard < 53 && predV < 0.15) {
          const oddsRank = liveRankingMap[race.race_id]?.[e.umaban] ?? e.odds_rank;
          entries.push({ race, entry: e, oddsRank, odds: liveOdds, ard, predV });
        }
      }
    }
    entries.sort((a, b) => a.race.race_number - b.race.race_number || a.race.race_id.localeCompare(b.race.race_id));
    return entries;
  }, [races, liveRankingMap, oddsMap]);

  const filteredDangerHorses = useMemo(() => {
    let entries = dangerHorses;
    if (venueFilter !== 'all') entries = entries.filter(d => d.race.venue_name === venueFilter);
    if (trackFilter !== 'all') entries = entries.filter(d => trackFilter === 'turf' ? isTurf(d.race.track_type) : isDirt(d.race.track_type));
    if (raceNumFilter > 0) entries = entries.filter(d => d.race.race_number === raceNumFilter);
    return entries;
  }, [dangerHorses, venueFilter, trackFilter, raceNumFilter]);

  const syncDangerMarks = useCallback(async () => {
    setDangerMarkSyncing(true);
    setDangerMarkResult(null);
    try {
      // フィルタ適用: 表示中のレースのみ対象
      let targetRaces = races;
      if (venueFilter !== 'all') targetRaces = targetRaces.filter(r => r.venue_name === venueFilter);
      if (trackFilter !== 'all') {
        targetRaces = targetRaces.filter(r =>
          trackFilter === 'turf' ? isTurf(r.track_type) : isDirt(r.track_type)
        );
      }
      if (raceNumFilter > 0) targetRaces = targetRaces.filter(r => r.race_number === raceNumFilter);

      // 危険馬リストを構築
      const dangerList: Array<{ raceId: string; umaban: number }> = [];
      const targetRaceIds = new Set(targetRaces.map(r => r.race_id));
      for (const dh of dangerHorses) {
        if (targetRaceIds.has(dh.race.race_id)) {
          dangerList.push({ raceId: dh.race.race_id, umaban: dh.entry.umaban });
        }
      }

      const res = await fetch('/api/target-marks/auto-danger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: isArchive ? currentDate : undefined,
          dangerHorses: dangerList,
          raceIds: targetRaces.map(r => r.race_id),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setDangerMarkResult({ markedHorses: data.summary.markedHorses });
    } catch (error) {
      console.error('[syncDangerMarks] Error:', error);
      setDangerMarkResult(null);
      alert(`DA印反映に失敗しました: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setDangerMarkSyncing(false);
    }
  }, [isArchive, currentDate, races, dangerHorses, venueFilter, trackFilter, raceNumFilter]);

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
        case 'race_number': {
          const rn = a.race.race_number - b.race.race_number;
          if (rn !== 0) return rn * mul;
          return a.race.race_id.localeCompare(b.race.race_id) * mul;
        }
        case 'umaban': va = a.entry.umaban; vb = b.entry.umaban; break;
        case 'winEv': va = a.winEv ?? -1; vb = b.winEv ?? -1; break;
        case 'placeEv': va = a.placeEv ?? -1; vb = b.placeEv ?? -1; break;
        case 'gap': va = getLiveGap(a.race.race_id, a.entry); vb = getLiveGap(b.race.race_id, b.entry); break;
        case 'devGap': va = a.devGap ?? 0; vb = b.devGap ?? 0; break;
        case 'vbScore': va = a.vbScore ?? 0; vb = b.vbScore ?? 0; break;
        case 'star': {
          va = getStarScore(getLiveGap(a.race.race_id, a.entry), a.predictedMargin);
          vb = getStarScore(getLiveGap(b.race.race_id, b.entry), b.predictedMargin);
          break;
        }
        case 'odds': {
          va = getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds) ?? 9999;
          vb = getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds) ?? 9999;
          break;
        }
        case 'head': {
          va = calcHeadRatio(a.entry.pred_proba_w, a.entry.pred_proba_p) ?? -1;
          vb = calcHeadRatio(b.entry.pred_proba_w, b.entry.pred_proba_p) ?? -1;
          break;
        }
        case 'margin': va = a.predictedMargin ?? -1; vb = b.predictedMargin ?? -1; break;
        case 'ar_dev': va = a.entry.ar_deviation ?? -1; vb = b.entry.ar_deviation ?? -1; break;
        case 'danger': va = a.danger?.isDanger ? 1 : 0; vb = b.danger?.isDanger ? 1 : 0; break;
        case 'strength': va = a.strength === 'strong' ? 1 : 0; vb = b.strength === 'strong' ? 1 : 0; break;
        case 'finish': {
          const fa = getFinishPos(a.race.race_id, a.entry.umaban);
          const fb = getFinishPos(b.race.race_id, b.entry.umaban);
          va = fa > 0 ? fa : 999;
          vb = fb > 0 ? fb : 999;
          break;
        }
        default: va = a.betAmountWin + a.betAmountPlace; vb = b.betAmountWin + b.betAmountPlace; break;
      }
      return (va - vb) * mul;
    });
    return recs;
  }, [betRecommendations, betSort, venueFilter, trackFilter, raceNumFilter, oddsMap, getLiveGap, getFinishPos]);

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
        case 'race_number': {
          const rn = a.race.race_number - b.race.race_number;
          if (rn !== 0) return rn * mul;
          return a.race.race_id.localeCompare(b.race.race_id) * mul;
        }
        case 'umaban': va = a.entry.umaban; vb = b.entry.umaban; break;
        case 'rank_p': va = a.entry.rank_p; vb = b.entry.rank_p; break;
        case 'odds_rank': va = a.entry.odds_rank || 999; vb = b.entry.odds_rank || 999; break;
        case 'odds': {
          va = getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds) ?? 9999;
          vb = getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds) ?? 9999;
          break;
        }
        case 'ev': {
          va = a.entry.win_ev ?? -1;
          vb = b.entry.win_ev ?? -1;
          break;
        }
        case 'place_ev': {
          va = a.entry.place_ev ?? -1;
          vb = b.entry.place_ev ?? -1;
          break;
        }
        case 'head_ratio': {
          va = calcHeadRatio(a.entry.pred_proba_w, a.entry.pred_proba_p) ?? -1;
          vb = calcHeadRatio(b.entry.pred_proba_w, b.entry.pred_proba_p) ?? -1;
          break;
        }
        case 'prob_p': va = a.entry.pred_proba_p; vb = b.entry.pred_proba_p; break;
        case 'win_gap': va = a.entry.win_vb_gap ?? -999; vb = b.entry.win_vb_gap ?? -999; break;
        case 'margin': va = a.entry.predicted_margin ?? -1; vb = b.entry.predicted_margin ?? -1; break;
        case 'ar_dev': va = a.entry.ar_deviation ?? -1; vb = b.entry.ar_deviation ?? -1; break;
        case 'rating': va = a.entry.kb_rating || 0; vb = b.entry.kb_rating || 0; break;
        case 'finish': {
          const pa = getFinishPos(a.race.race_id, a.entry.umaban);
          const pb = getFinishPos(b.race.race_id, b.entry.umaban);
          va = pa > 0 ? pa : 999;
          vb = pb > 0 ? pb : 999;
          break;
        }
        default: va = getLiveGap(a.race.race_id, a.entry); vb = getLiveGap(b.race.race_id, b.entry); break;
      }
      return (va - vb) * mul;
    });
    return arr;
  }, [filteredVBEntries, vbSort, oddsMap, getFinishPos, getLiveGap]);

  // ROI計算
  const roiStats = useMemo(() => {
    if (!hasResults) return null;

    type TrackROI = {
      vbCount: number; winHits: number; placeHits: number;
      winPayout: number; placePayout: number; placeBetCount: number;
      hasAnyPlaceOdds: boolean;
    };
    const initTrack = (): TrackROI => ({ vbCount: 0, winHits: 0, placeHits: 0, winPayout: 0, placePayout: 0, placeBetCount: 0, hasAnyPlaceOdds: false });

    const addEntry = (b: TrackROI, race: PredictionRace, entry: PredictionEntry, pos: number) => {
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
    };

    const all = initTrack();
    const betExcl = initTrack();

    // 全体 + 非推奨: VB候補ベース
    for (const { race, entry } of filteredVBEntries) {
      const pos = getFinishPos(race.race_id, entry.umaban);
      if (pos <= 0) continue;
      addEntry(all, race, entry, pos);
      if (!betRecMap.has(`${race.race_id}-${entry.umaban}`)) {
        addEntry(betExcl, race, entry, pos);
      }
    }

    // 購入プラン: betRecommendationsベース（VB外のbet recも含む）
    const betRec = initTrack();
    for (const r of betRecommendations) {
      // フィルタ適用（VBテーブルと同じ絞り込み）
      if (venueFilter !== 'all' && r.race.venue_name !== venueFilter) continue;
      if (trackFilter !== 'all') {
        if (trackFilter === 'turf' ? !isTurf(r.race.track_type) : !isDirt(r.race.track_type)) continue;
      }
      if (raceNumFilter > 0 && r.race.race_number !== raceNumFilter) continue;
      const pos = getFinishPos(r.race.race_id, r.entry.umaban);
      if (pos <= 0) continue;
      addEntry(betRec, r.race, r.entry, pos);
    }

    if (all.vbCount === 0 && betRec.vbCount === 0) return null;

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

    return { all: calcROI(all), betRec: calcROI(betRec), betExcl: calcROI(betExcl) };
  }, [filteredVBEntries, dbResults, results, hasResults, oddsMap, getFinishPos, betRecMap, betRecommendations, venueFilter, trackFilter, raceNumFilter]);

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
            {data.date} / Live Model v{data.model_version} / オッズ: {data.odds_source}
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
        betCount={betRecommendations.length}
        betTotalAmount={betSummary.totalAmount}
        hasBets={betRecommendations.length > 0}
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
        minEv={minEv}
        setMinEv={setMinEv}
        minArd={minArd}
        setMinArd={setMinArd}
        betOnly={betOnly}
        setBetOnly={setBetOnly}
        filteredCount={filteredVBEntries.length}
        totalCount={allVBEntries.length}
      />

      {/* セクションナビ */}
      <SectionNav
        hasResults={hasResults && roiStats != null}
        hasBets={betRecommendations.length > 0}
        hasVB={filteredVBEntries.length > 0}
        hasDanger={filteredDangerHorses.length > 0}
        hasMultiLeg={(data.multi_leg_recommendations?.length ?? 0) > 0}
      />

      {/* ROIサマリー */}
      {hasResults && roiStats && (
        <RoiSummary all={roiStats.all} betRec={roiStats.betRec} betExcl={roiStats.betExcl} />
      )}

      {/* 推奨買い目 */}
      <BetRecommendations
        betRecommendations={betRecommendations}
        sortedBetRecommendations={sortedBetRecommendations}
        betSummary={betSummary}
        oddsMap={oddsMap}
        getLiveGap={getLiveGap}
        oddsLoading={oddsLoading}
        dailyBudget={dailyBudget}
        updateBudget={updateBudget}
        fetchAllOdds={fetchAllOdds}
        syncBetMarks={syncBetMarks}
        betSyncing={betSyncing}
        betSyncResult={betSyncResult}
        betSort={betSort}
        setBetSort={setBetSort}
        preset={preset}
        onPresetChange={updatePreset}
        allocMode={allocMode}
        onAllocModeChange={updateAllocMode}
        dbResults={dbResults}
        getFinishPos={getFinishPos}
        bankrollBalance={bankrollBalance}
        budgetLinked={budgetLinked}
        toggleBudgetLink={toggleBudgetLink}
        dailyLimitPct={dailyLimitPct}
        onDailyLimitPctChange={updateDailyLimitPct}
        isLiveCalc={hasLiveOdds}
        isArchive={isArchive}
        oddsTime={oddsTime}
      />

      {/* マルチレグ推奨（馬単・ワイド） */}
      {data.multi_leg_recommendations && data.multi_leg_recommendations.length > 0 && (
        <MultiLegRecommendations
          recommendations={data.multi_leg_recommendations}
          results={results}
          races={races}
          venueFilter={venueFilter}
          trackFilter={trackFilter}
          raceNumFilter={raceNumFilter}
        />
      )}

      {/* VB候補 */}
      <VBTable
        sortedVBEntries={sortedVBEntries}
        filteredVBEntries={filteredVBEntries}
        oddsMap={oddsMap}
        dbResults={dbResults}
        results={results}
        hasResults={hasResults}
        getFinishPos={getFinishPos}
        getLiveGap={getLiveGap}
        vbSort={vbSort}
        setVbSort={setVbSort}
        syncVbMarks={syncVbMarks}
        markSyncing={markSyncing}
        markResult={markResult}
        betRecMap={betRecMap}
        targetMarks={targetMarks}
      />

      {/* 危険馬結果一覧 */}
      <DangerResults
        dangerHorses={filteredDangerHorses}
        getFinishPos={getFinishPos}
        syncDangerMarks={syncDangerMarks}
        dangerMarkSyncing={dangerMarkSyncing}
        dangerMarkResult={dangerMarkResult}
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
                <RaceCard key={race.race_id} race={race} oddsMap={oddsMap} results={results} dbResults={dbResults} targetMarks={targetMarks[race.race_id]} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
