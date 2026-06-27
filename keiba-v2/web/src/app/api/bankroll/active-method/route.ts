/**
 * 現在の自動投票「買い目選定方式」を返す API (Session 176)
 *
 * 自動投票画面に「今どんな買い目を狙っているか」を出すための情報源。
 * 推測でなく ★実体★ から判定する:
 *   - scripts/bettype_auto.bat の python 起動行 = Task Scheduler が実際に回す方式
 *   - bankroll/config.json = gap の有効/無効・比率・初期残高
 *
 * GET /api/bankroll/active-method
 */
import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import { SCRIPTS_PATH } from '@/lib/config';
import { loadConfig } from '@/lib/bankroll/limit-resolver';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BAT_PATH = path.join(SCRIPTS_PATH, 'bettype_auto.bat');

type MethodKey = 'gap_tansho' | 'honmei_ev' | 'sanrentan_formation' | 'wide_anaba' | 'shobu_rate'
  | 'fixed_grade_v2' | 'freebudget' | 'unknown';

interface MethodInfo {
  key: MethodKey;
  label: string;          // 短い方式名
  thesis: string;         // 「こういう買い目を狙ってるよ」(人間語)
  betType: string;        // 主な券種
  resultsLink: string | null;   // 検証結果ページ
  hasMasterSwitch: boolean;     // gap のように有効/無効トグルがあるか
}

const METHODS: Record<MethodKey, MethodInfo> = {
  gap_tansho: {
    key: 'gap_tansho',
    label: '逆張り単（ぎゃくばりたん）',
    thesis:
      '市場が見限った（人気薄の）馬を、AIの勝率評価が上回る「過小評価」のときだけ' +
      '単勝で買う高配狙いのスリーブ。gap≥5（AI上位なのに人気薄）を未勝利・条件・重賞クラスに限定。' +
      '市場較正監査で実在を確認したエッジ（in-sample ROI 130%・p=0.026）を、' +
      '残高×比率の比例ベットで1点ずつ拾う。',
    betType: '単勝1点（逆張り・高配狙い）',
    resultsLink: '/analysis/edge-validation',
    hasMasterSwitch: true,
  },
  honmei_ev: {
    key: 'honmei_ev',
    label: '本命EV単（ほんめいいーぶぃーたん）',
    thesis:
      'AIの本命（勝率1位）を、市場がまだ過小評価していて（gap≥3）・期待値が高く（EV≥1.3）・' +
      '接戦で勝ち切れる（margin≤60）ときだけ単勝1点で買う本命妙味のスリーブ。' +
      '推奨馬券画面の主力プリセット tansho_ippon と同一条件（現行シミュ Flat ROI 108.3%）。',
    betType: '単勝1点（本命・妙味/期待値狙い）',
    resultsLink: '/analysis/honmei-ev-validation',
    hasMasterSwitch: true,
  },
  sanrentan_formation: {
    key: 'sanrentan_formation',
    label: '三連単フォーメーション（combo）',
    thesis:
      '◎を2-3着に流し、頭は妙味馬で配当の天井を狙う三連単フォメ。' +
      'ハーヴィルEVで点を絞り、◎が過剰人気なら見送る。',
    betType: '三連単フォーメーション',
    resultsLink: '/analysis/edge-validation',
    hasMasterSwitch: false,
  },
  wide_anaba: {
    key: 'wide_anaba',
    label: 'ワイド堅実党（combo）',
    thesis: '通常R=ワイド◎流し+三連複、勝負R=単勝。投資額連動。',
    betType: 'ワイド / 三連複 / 単勝',
    resultsLink: '/analysis/bet-lab',
    hasMasterSwitch: false,
  },
  shobu_rate: {
    key: 'shobu_rate',
    label: '勝負レート（combo）',
    thesis: '勝負条件レースだけ rank_w◎ の単勝を厚く、他は combo。',
    betType: '単勝 / combo',
    resultsLink: '/analysis/bet-lab',
    hasMasterSwitch: false,
  },
  fixed_grade_v2: {
    key: 'fixed_grade_v2',
    label: '評価ベース固定配分（combo）',
    thesis: '◎の格で単/複/comboの配分を固定。',
    betType: '単勝 / 複勝 / combo',
    resultsLink: '/analysis/bet-lab',
    hasMasterSwitch: false,
  },
  freebudget: {
    key: 'freebudget',
    label: '単勝Kelly（freebudget）',
    thesis: 'freebudget が選ぶ単勝を Kelly で。',
    betType: '単勝',
    resultsLink: null,
    hasMasterSwitch: false,
  },
  unknown: {
    key: 'unknown',
    label: '不明',
    thesis: 'bettype_auto.bat の起動行から方式を判定できませんでした。',
    betType: '—',
    resultsLink: null,
    hasMasterSwitch: false,
  },
};

/** bat の python 起動行から方式キーを判定（live 行 = --confirm を含む行を優先）。 */
function detectMethod(bat: string): MethodKey {
  const lines = bat
    .split(/\r?\n/)
    .filter((l) => /python\s+-m\s+ml\.strategies\./.test(l)
      && /(scheduler|orchestrator)/.test(l));
  // live 起動行を優先（無ければ最初の起動行）
  const line = lines.find((l) => /--confirm/.test(l)) ?? lines[0] ?? '';
  // sleeve_orchestrator (S176 §8-1): 有効スリーブを回す。 現状スリーブは gap のみなので
  //   稼働方式 = 逆張り単(gap)。 active は gap_enabled で判定（下の hasMasterSwitch 経路）。
  //   ★将来★: 複数スリーブ化したら API を「有効スリーブ配列」に拡張する（§8-4 表示一覧化）。
  if (/sleeve_orchestrator/.test(line)) return 'gap_tansho';
  if (/gap_tansho_scheduler/.test(line)) return 'gap_tansho';
  if (/freebudget_scheduler/.test(line)) return 'freebudget';
  if (/bettype_scheduler/.test(line)) {
    const m = line.match(/--sizing\s+([a-z_0-9]+)/);
    const sizing = m?.[1];
    if (sizing && sizing in METHODS) return sizing as MethodKey;
    return 'sanrentan_formation'; // sizing 不明だが bettype = combo 系
  }
  return 'unknown';
}

/** sleeve_orchestrator 起動か（= 複数スリーブ並行運用モード）。 */
function isOrchestrator(bat: string): boolean {
  return /python\s+-m\s+ml\.strategies\.sleeve_orchestrator/.test(bat);
}

export async function GET() {
  try {
    let bat = '';
    try {
      bat = await fs.readFile(BAT_PATH, 'latin1'); // SJIS bat。 判定は ASCII 部分のみなので latin1 で十分
    } catch {
      // bat 読めない → unknown で返す（画面は出す）
    }
    const key = bat ? detectMethod(bat) : 'unknown';
    const info = METHODS[key];

    const config = await loadConfig();
    const s = config.settings ?? {};
    const gap = {
      enabled: Boolean(s.gap_enabled),
      initialBankrollYen: s.gap_initial_bankroll_yen ?? 300000,
      betPct: s.gap_bet_pct ?? 1.0,
      dayPct: s.gap_day_pct ?? 5.0,
    };

    // ★複数スリーブ並行 (S177 §8-4)★: orchestrator なら有効スリーブ配列を返す。
    //   優先度順 = registry と同じ [honmei_ev, gap_tansho]。各スリーブの master switch + パラメータ。
    let sleeves: Array<{
      method: MethodInfo;
      active: boolean;
      params: { initialBankrollYen: number; betPct: number; dayPct: number };
    }> = [];
    if (bat && isOrchestrator(bat)) {
      sleeves = [
        {
          method: METHODS.honmei_ev,
          active: Boolean(s.tansho_ev_enabled),
          params: {
            initialBankrollYen: s.tansho_ev_initial_bankroll_yen ?? 300000,
            betPct: s.tansho_ev_bet_pct ?? 2.0,
            dayPct: s.tansho_ev_day_pct ?? 10.0,
          },
        },
        {
          method: METHODS.gap_tansho,
          active: gap.enabled,
          params: {
            initialBankrollYen: gap.initialBankrollYen,
            betPct: gap.betPct,
            dayPct: gap.dayPct,
          },
        },
      ];
    }

    // 稼働中か: gap は master switch (gap_enabled)。 combo 系は bat が指していれば稼働。
    //   orchestrator なら「いずれかのスリーブが有効」で稼働。
    const active = sleeves.length > 0
      ? sleeves.some((sl) => sl.active)
      : info.hasMasterSwitch ? gap.enabled : key !== 'unknown';

    return NextResponse.json({
      method: info,
      active,
      gap,
      sleeves,
      totalDayCapYen: s.sleeve_total_day_cap_yen ?? 0,
      sourceBat: 'scripts/bettype_auto.bat',
      detectedFrom: bat ? 'bat' : 'fallback',
    });
  } catch (error) {
    return NextResponse.json(
      { error: '方式の取得に失敗しました', message: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
