/**
 * 戦略プリセット定義
 *
 * 各戦略は (発動条件 + 候補フィルタ + 倍率ルール) のセット。
 * 配列に追加するだけで新戦略を増やせる構造。
 *
 * ユーザー方針:
 *   - 「印構成を見て、このレースで狙うべき券種・買い方を自動提案」
 *   - 機械的な定型ではなく、印が薄い/混戦の時にも妙味馬券を拾う
 *   - 例: ▲頭の三連単、穴絡みの三連複 など、定型外パターンも積極評価
 */

import { BetCandidate } from './ev-calculator';
import { isAnyMark } from './probability-table';

// --- 倍率ルール（共通） ---

export interface StakeRule {
  baseAmount: number; // 100円
  /** EV閾値→倍率 */
  tiers: { evGte: number; multiplier: number }[];
  /** 出力点数上限 */
  maxBets: number;
  /** 合計金額上限（円） */
  maxTotalCost: number;
}

const DEFAULT_STAKE: StakeRule = {
  baseAmount: 100,
  tiers: [
    { evGte: 1.5, multiplier: 3 },
    { evGte: 1.2, multiplier: 2 },
    { evGte: 1.0, multiplier: 1 },
  ],
  maxBets: 30,
  maxTotalCost: 3000,
};

const TIGHT_STAKE: StakeRule = {
  ...DEFAULT_STAKE,
  maxBets: 10,
  maxTotalCost: 1500,
};

const WIDE_STAKE: StakeRule = {
  ...DEFAULT_STAKE,
  maxBets: 50,
  maxTotalCost: 5000,
};

/** EV から倍率を決定 */
export function multiplierForEv(ev: number, rule: StakeRule = DEFAULT_STAKE): number {
  for (const t of rule.tiers) {
    if (ev >= t.evGte) return t.multiplier;
  }
  return 0;
}

// --- 発動条件・候補フィルタの型 ---

export interface RaceMarksContext {
  /** 馬番→印 */
  horseToMark: Record<number, string>;
  /** 印別 馬番リスト */
  byMark: Record<string, number[]>; // ◎/○/▲/△/★/穴
  /** 印有り頭数 */
  markedCount: number;
  /** 全頭数 */
  totalHorses: number;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  /** この戦略が発動する条件（印構成・候補状況から判定） */
  shouldActivate: (ctx: RaceMarksContext, candidates: BetCandidate[]) => boolean;
  /** 候補から該当買い目を抽出 */
  pickCandidates: (
    ctx: RaceMarksContext,
    candidates: BetCandidate[]
  ) => BetCandidate[];
  /** 倍率ルール */
  stake: StakeRule;
}

// --- ヘルパー ---

function evDesc(a: BetCandidate, b: BetCandidate): number {
  return b.ev - a.ev;
}

/** 1着馬の印が指定セットに含まれるか（馬連/三連単等は1番目馬で判定） */
function leadMarkIn(c: BetCandidate, marks: string[]): boolean {
  return marks.includes(c.marks[0] ?? '');
}

/** 含まれる印いずれかが指定セット */
function anyMarkIn(c: BetCandidate, marks: string[]): boolean {
  return c.marks.some((m) => marks.includes(m));
}

/** 全構成馬が「印有り or 指定セット」に収まる */
function allMarksIn(c: BetCandidate, allowed: string[]): boolean {
  return c.marks.every((m) => allowed.includes(m));
}

/** RaceMarksContext を構築 */
export function buildRaceMarksContext(
  horseToMark: Record<number, string>,
  totalHorses: number
): RaceMarksContext {
  const byMark: Record<string, number[]> = {
    '◎': [],
    '○': [],
    '▲': [],
    '△': [],
    '★': [],
    '穴': [],
  };
  let markedCount = 0;
  for (const [umaStr, mark] of Object.entries(horseToMark)) {
    if (isAnyMark(mark)) {
      byMark[mark].push(parseInt(umaStr, 10));
      markedCount++;
    }
  }
  return { horseToMark, byMark, markedCount, totalHorses };
}

// --- 戦略定義 ---

export const STRATEGIES: Strategy[] = [
  // s01: 単勝堅め（◎の単勝EVが妙味）
  {
    id: 's01_tansho_honmei',
    name: '単勝堅め',
    description: '◎の単勝にEV妙味あれば1点勝負',
    shouldActivate: (ctx) => ctx.byMark['◎'].length > 0,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'tansho' &&
            ctx.byMark['◎'].includes(c.horses[0]) &&
            c.ev >= 1.0
        )
        .sort(evDesc)
        .slice(0, 1),
    stake: TIGHT_STAKE,
  },

  // s02: 単勝穴（▲or穴の単勝EV高）
  {
    id: 's02_tansho_ana',
    name: '単勝穴',
    description: '▲・穴の単勝でEV1.5超なら勝負',
    shouldActivate: (ctx) =>
      ctx.byMark['▲'].length > 0 || ctx.byMark['穴'].length > 0,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'tansho' &&
            (ctx.byMark['▲'].includes(c.horses[0]) ||
              ctx.byMark['穴'].includes(c.horses[0])) &&
            c.ev >= 1.5
        )
        .sort(evDesc)
        .slice(0, 2),
    stake: TIGHT_STAKE,
  },

  // s03: 馬連シンプル（◎-○▲）
  {
    id: 's03_umaren_honmei',
    name: '馬連本線',
    description: '◎-○▲の馬連、EV1.0超',
    shouldActivate: (ctx) =>
      ctx.byMark['◎'].length > 0 &&
      (ctx.byMark['○'].length > 0 || ctx.byMark['▲'].length > 0),
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'umaren' &&
            anyMarkIn(c, ['◎']) &&
            anyMarkIn(c, ['○', '▲']) &&
            c.ev >= 1.0
        )
        .sort(evDesc),
    stake: DEFAULT_STAKE,
  },

  // s04: ワイド広め（◎-○▲△★穴）
  {
    id: 's04_wide_box',
    name: 'ワイド広め',
    description: '◎軸ワイド ◎-○▲△★穴、EV1.0超',
    shouldActivate: (ctx) =>
      ctx.byMark['◎'].length > 0 && ctx.markedCount >= 3,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'wide' &&
            anyMarkIn(c, ['◎']) &&
            anyMarkIn(c, ['○', '▲', '△', '★', '穴']) &&
            c.ev >= 1.0
        )
        .sort(evDesc),
    stake: DEFAULT_STAKE,
  },

  // s05: 三連複軸（◎-○▲-○▲△★）
  {
    id: 's05_sanrenpuku_honmei',
    name: '三連複本線',
    description: '◎軸三連複、印3頭以上、EV1.0超',
    shouldActivate: (ctx) =>
      ctx.byMark['◎'].length > 0 && ctx.markedCount >= 3,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'sanrenpuku' &&
            anyMarkIn(c, ['◎']) &&
            allMarksIn(c, ['◎', '○', '▲', '△', '★']) &&
            c.ev >= 1.0
        )
        .sort(evDesc),
    stake: DEFAULT_STAKE,
  },

  // s06: 三連複★絡み
  {
    id: 's06_sanrenpuku_star',
    name: '三連複★絡み',
    description: '★を3着候補とした三連複、EV1.2超',
    shouldActivate: (ctx) =>
      ctx.byMark['★'].length > 0 && ctx.byMark['◎'].length > 0,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'sanrenpuku' &&
            anyMarkIn(c, ['◎']) &&
            anyMarkIn(c, ['★']) &&
            c.ev >= 1.2
        )
        .sort(evDesc),
    stake: DEFAULT_STAKE,
  },

  // s07: 三連単本線（◎→○▲△→○▲△★）
  {
    id: 's07_sanrentan_honmei',
    name: '三連単本線',
    description: '◎1着固定→○▲△→○▲△★、印4頭以上、EV1.0超',
    shouldActivate: (ctx) =>
      ctx.byMark['◎'].length > 0 && ctx.markedCount >= 4,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'sanrentan' &&
            ctx.byMark['◎'].includes(c.horses[0]) &&
            (ctx.byMark['○'].includes(c.horses[1]) ||
              ctx.byMark['▲'].includes(c.horses[1]) ||
              ctx.byMark['△'].includes(c.horses[1])) &&
            allMarksIn(c, ['◎', '○', '▲', '△', '★']) &&
            c.ev >= 1.0
        )
        .sort(evDesc),
    stake: WIDE_STAKE,
  },

  // s08: 三連単逆転▲頭（▲→◎→印有り＋無印高EV）
  {
    id: 's08_sanrentan_gyakuten_pin',
    name: '三連単逆転▲頭',
    description: '▲1着固定→◎2着→印有 or 無印高EV、EV1.5超',
    shouldActivate: (ctx) =>
      ctx.byMark['▲'].length > 0 && ctx.byMark['◎'].length > 0,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'sanrentan' &&
            ctx.byMark['▲'].includes(c.horses[0]) &&
            ctx.byMark['◎'].includes(c.horses[1]) &&
            c.ev >= 1.5
        )
        .sort(evDesc),
    stake: WIDE_STAKE,
  },

  // s09: 三連単穴頭（穴→◎○→印有）
  {
    id: 's09_sanrentan_ana_head',
    name: '三連単穴頭',
    description: '穴1着→◎○2着→印有り、EV2.0超',
    shouldActivate: (ctx) =>
      ctx.byMark['穴'].length > 0 && ctx.byMark['◎'].length > 0,
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'sanrentan' &&
            ctx.byMark['穴'].includes(c.horses[0]) &&
            (ctx.byMark['◎'].includes(c.horses[1]) ||
              ctx.byMark['○'].includes(c.horses[1])) &&
            c.ev >= 2.0
        )
        .sort(evDesc),
    stake: WIDE_STAKE,
  },

  // s10: 三連複穴絡み
  {
    id: 's10_sanrenpuku_ana',
    name: '三連複穴絡み',
    description: '穴を含む三連複、◎○いずれか含む、EV2.0超',
    shouldActivate: (ctx) =>
      ctx.byMark['穴'].length > 0 &&
      (ctx.byMark['◎'].length > 0 || ctx.byMark['○'].length > 0),
    pickCandidates: (ctx, cands) =>
      cands
        .filter(
          (c) =>
            c.betType === 'sanrenpuku' &&
            anyMarkIn(c, ['穴']) &&
            anyMarkIn(c, ['◎', '○']) &&
            c.ev >= 2.0
        )
        .sort(evDesc),
    stake: DEFAULT_STAKE,
  },

  // 参考: leadMarkIn は将来の戦略追加で使用
];

void leadMarkIn;

// --- 戦略実行・整形 ---

export interface StrategyResult {
  strategyId: string;
  name: string;
  description: string;
  activated: boolean;
  /** 採用買い目 */
  bets: (BetCandidate & { stake: number })[];
  totalCost: number;
  totalBets: number;
  /** EV平均（採用買い目） */
  avgEv: number;
}

export function runStrategy(
  strategy: Strategy,
  ctx: RaceMarksContext,
  candidates: BetCandidate[]
): StrategyResult {
  const activated = strategy.shouldActivate(ctx, candidates);
  if (!activated) {
    return {
      strategyId: strategy.id,
      name: strategy.name,
      description: strategy.description,
      activated: false,
      bets: [],
      totalCost: 0,
      totalBets: 0,
      avgEv: 0,
    };
  }

  const picked = strategy.pickCandidates(ctx, candidates);
  // 倍率付与 + 上限制約
  const stakes: (BetCandidate & { stake: number })[] = [];
  let totalCost = 0;
  for (const c of picked) {
    if (stakes.length >= strategy.stake.maxBets) break;
    const mult = multiplierForEv(c.ev, strategy.stake);
    if (mult <= 0) continue;
    const stake = strategy.stake.baseAmount * mult;
    if (totalCost + stake > strategy.stake.maxTotalCost) break;
    stakes.push({ ...c, stake });
    totalCost += stake;
  }

  const avgEv =
    stakes.length > 0 ? stakes.reduce((s, c) => s + c.ev, 0) / stakes.length : 0;

  return {
    strategyId: strategy.id,
    name: strategy.name,
    description: strategy.description,
    activated: true,
    bets: stakes,
    totalCost,
    totalBets: stakes.length,
    avgEv,
  };
}

export function runAllStrategies(
  ctx: RaceMarksContext,
  candidates: BetCandidate[]
): StrategyResult[] {
  return STRATEGIES.map((s) => runStrategy(s, ctx, candidates));
}
