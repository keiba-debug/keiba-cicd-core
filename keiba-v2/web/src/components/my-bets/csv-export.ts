/**
 * 戦略の買い目を TARGET FF CSV として書き込む（既存 /api/target-marks/auto-bet 経由）
 *
 * 書込み先: C:\TFJV\TXT\FFyyyymmdd_HHmmss.CSV
 * TARGET側で「買い目取り込み」メニューから読み込む。
 */

import { BetCandidate, BET_TYPE_FF_CODE, StrategyResult } from './types';

interface AutoBetInput {
  raceId: string;
  betType: number;
  umaban: number;
  umaban2?: number;
  umaban3?: number;
  amount: number;
}

function toAutoBetInputs(
  raceId: string,
  bets: BetCandidate[]
): AutoBetInput[] {
  return bets
    .filter((b) => (b.stake ?? 0) > 0)
    .map((b) => {
      const code = BET_TYPE_FF_CODE[b.betType];
      return {
        raceId,
        betType: code,
        umaban: b.horses[0],
        umaban2: b.horses[1],
        umaban3: b.horses[2],
        amount: b.stake ?? 0,
      };
    });
}

async function postAutoBet(inputs: AutoBetInput[]): Promise<{
  filePath: string;
  totalAmount: number;
  totalBets: number;
}> {
  if (inputs.length === 0) {
    throw new Error('書込み対象の買い目がありません');
  }
  const res = await fetch('/api/target-marks/auto-bet', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ bets: inputs }),
  });
  const json = await res.json();
  if (!res.ok || !json.success) {
    throw new Error(json.error ?? `HTTP ${res.status}`);
  }
  return {
    filePath: json.summary.filePath,
    totalAmount: json.summary.totalAmount,
    totalBets: json.summary.totalBets,
  };
}

export async function downloadFfCsv(
  raceId: string,
  bets: BetCandidate[]
): Promise<void> {
  const inputs = toAutoBetInputs(raceId, bets);
  const r = await postAutoBet(inputs);
  alert(
    `FF CSV書込み完了\n${r.totalBets}点 ¥${r.totalAmount.toLocaleString()}\n${r.filePath}`
  );
}

export async function downloadStrategyCsv(
  raceId: string,
  strategy: StrategyResult
): Promise<void> {
  await downloadFfCsv(raceId, strategy.bets);
}
