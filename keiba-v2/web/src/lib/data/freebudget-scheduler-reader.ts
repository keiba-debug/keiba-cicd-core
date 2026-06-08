/**
 * freebudget-scheduler-reader — 自動投票スケジューラの状態を読む純 TS。
 * Python/DB 不要。 SoT = Python (freebudget_scheduler が書く state ファイル)。
 * web は読むだけ (ledger-reader / predictions-reader と同じ流儀)。
 *
 * Session 139: 自動投票 ON/OFF・開始 UI 用。
 *   - freebudget_scheduler_state[_dryrun].json : 当日の halted / votes / per_day累計
 *   - freebudget_scheduler.lock                : 鮮度で running 推定 (LOCK_STALE_SEC=600)
 *   - freebudget_bets.json                     : funded 買い目 (金額確認ダイアログの原本)
 */
import fs from 'fs';
import path from 'path';

const DATA_ROOT = process.env.KEIBA_DATA_ROOT || 'C:/KEIBA-CICD/data3';

// scheduler 側の定数と整合 (freebudget_scheduler.py)
export const LOCK_STALE_SEC = 600;
export const PER_DAY_MAX_YEN = 10000;

export interface VoteEntry {
  race_id: string;
  mode: string;            // 'live' | 'dry-run' | 'missed'
  amount: number;
  umaban: number[];
  exit_code: number;       // 0=成功 / 5,7,8=halt / -1=missed / 他=失敗
  note: string;
  label?: string;
  at?: string;
}

export interface FundedBet {
  race_id: string;
  umaban: number;
  horse_name?: string;
  amount: number;
}

export interface SkipEntry {
  race_id: string;
  reason: string;
}

export interface SchedulerStatus {
  date: string;
  exists: boolean;             // state ファイルが存在するか (= 当日まだ一度も起動してない判定)
  scheduler: 'bettype' | 'freebudget' | null;  // どちらの scheduler の state を見ているか
  mode: 'live' | 'dry-run' | null;
  halted: boolean;
  halt_reason: string | null;
  consecutive_failures: number;
  running: boolean;            // lock 鮮度から推定
  lock_age_sec: number | null;
  votes: VoteEntry[];
  voted_yen: number;           // 成功投票の累計 (exit_code==0)
  per_day_max_yen: number;     // 当日上限 (= state.day_budget_yen 凍結値があればそれ)
  // 当日予算の根拠 (Session145): 「本日のスタート額(入金額)」を朝に凍結した値とその出所
  day_budget_yen: number | null;
  day_budget_source: string | null;
  // per-race スキップ理由 (穴B): halted=False でも「なぜ買わなかったか」を表示する
  skips: SkipEntry[];
  // funded artifact (金額確認ダイアログの原本)
  funded_total_yen: number | null;
  funded_n_bets: number | null;
  funded_generated_at: string | null;
  funded_bets: FundedBet[];
  // selection artifact (Phase3 の候補。 鮮度表示用)
  selection_generated_at: string | null;
}

function dayDir(date: string): string {
  const [y, m, d] = date.split('-');
  return path.join(DATA_ROOT, 'races', y, m, d);
}

function readJson<T = unknown>(p: string): T | null {
  try {
    if (!fs.existsSync(p)) return null;
    return JSON.parse(fs.readFileSync(p, 'utf-8')) as T;
  } catch {
    return null;
  }
}

/** 今日 (ローカル) を YYYY-MM-DD で。 引数 'today' / undefined を解決。 */
export function resolveDate(date?: string): string {
  if (!date || date === 'today') {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  return date;
}

/** state ファイルの votes (object) を配列に正規化 */
function normalizeVotes(votesObj: Record<string, VoteEntry> | undefined): VoteEntry[] {
  if (!votesObj) return [];
  return Object.entries(votesObj).map(([race_id, v]) => ({
    race_id,
    mode: v.mode ?? '',
    amount: v.amount ?? 0,
    umaban: v.umaban ?? [],
    exit_code: v.exit_code ?? 0,
    note: v.note ?? '',
    label: v.label,
    at: v.at,
  }));
}

/**
 * 当日の自動投票スケジューラ状態を読む。
 * live state を優先し、 無ければ dry-run state を読む (どちらも無ければ exists=false)。
 */
export function getSchedulerStatus(dateInput?: string): SchedulerStatus {
  const date = resolveDate(dateInput);
  const dir = dayDir(date);

  // 穴A: bettype (multi-bettype = 現行本番) と freebudget (単勝) の両 state を見る。
  //   優先順: live を dry-run より、 同 mode では bettype を freebudget より優先
  //   (1日に走るのはどちらか一方なので実質「存在する方」を拾う)。
  const candidates: {
    sched: 'bettype' | 'freebudget';
    mode: 'live' | 'dry-run';
    file: string;
    lock: string;
  }[] = [
    { sched: 'bettype', mode: 'live', file: 'bettype_scheduler_state.json', lock: 'bettype_scheduler.lock' },
    { sched: 'freebudget', mode: 'live', file: 'freebudget_scheduler_state.json', lock: 'freebudget_scheduler.lock' },
    { sched: 'bettype', mode: 'dry-run', file: 'bettype_scheduler_state_dryrun.json', lock: 'bettype_scheduler.lock' },
    { sched: 'freebudget', mode: 'dry-run', file: 'freebudget_scheduler_state_dryrun.json', lock: 'freebudget_scheduler.lock' },
  ];
  let state: Record<string, unknown> | null = null;
  let scheduler: 'bettype' | 'freebudget' | null = null;
  let mode: 'live' | 'dry-run' | null = null;
  let lockFile = 'freebudget_scheduler.lock';
  for (const c of candidates) {
    const s = readJson<Record<string, unknown>>(path.join(dir, c.file));
    if (s) {
      state = s;
      scheduler = c.sched;
      mode = c.mode;
      lockFile = c.lock;
      break;
    }
  }

  // lock 鮮度 → running 推定 (採用した scheduler の lock を見る)
  let running = false;
  let lockAge: number | null = null;
  const lockPath = path.join(dir, lockFile);
  try {
    if (fs.existsSync(lockPath)) {
      const mtime = fs.statSync(lockPath).mtimeMs;
      lockAge = (Date.now() - mtime) / 1000;
      running = lockAge < LOCK_STALE_SEC;
    }
  } catch {
    /* ignore */
  }

  // funded artifact (freebudget_bets.json)
  const funded = readJson<{
    total_yen?: number;
    n_bets?: number;
    generated_at?: string;
    bets?: FundedBet[];
  }>(path.join(dir, 'freebudget_bets.json'));

  // selection artifact (betting_selection.json) — 鮮度のみ
  const selection = readJson<{ generated_at?: string }>(
    path.join(dir, 'betting_selection.json'));

  const votes = normalizeVotes(
    (state?.votes as Record<string, VoteEntry>) ?? undefined);
  const votedYen = votes
    .filter((v) => v.exit_code === 0)
    .reduce((s, v) => s + (v.amount ?? 0), 0);

  // 当日上限: scheduler が朝に凍結した day_budget_yen を最優先。 無ければ state の
  //   per_day_max_yen、 それも無ければ定数フォールバック。
  const dayBudget = typeof state?.day_budget_yen === 'number'
    ? (state.day_budget_yen as number)
    : null;
  const perDay = dayBudget
    ?? (typeof state?.per_day_max_yen === 'number'
      ? (state.per_day_max_yen as number)
      : PER_DAY_MAX_YEN);

  // 穴B: per-race スキップ理由 (state.skips: { race_id: reason })
  const skipsObj = (state?.skips as Record<string, string>) ?? {};
  const skips: SkipEntry[] = Object.entries(skipsObj)
    .map(([race_id, reason]) => ({ race_id, reason }));

  return {
    date,
    exists: state != null,
    scheduler,
    mode,
    halted: Boolean(state?.halted),
    halt_reason: (state?.halt_reason as string) ?? null,
    consecutive_failures: (state?.consecutive_failures as number) ?? 0,
    running,
    lock_age_sec: lockAge,
    votes,
    voted_yen: votedYen,
    per_day_max_yen: perDay,
    day_budget_yen: dayBudget,
    day_budget_source: (state?.day_budget_source as string) ?? null,
    skips,
    funded_total_yen: funded?.total_yen ?? null,
    funded_n_bets: funded?.n_bets ?? null,
    funded_generated_at: funded?.generated_at ?? null,
    funded_bets: funded?.bets ?? [],
    selection_generated_at: selection?.generated_at ?? null,
  };
}

/**
 * funded artifact の合計金額を返す (start API の confirmed_total_yen 照合用)。
 * 無ければ null。
 */
export function getFundedTotalYen(dateInput?: string): number | null {
  const date = resolveDate(dateInput);
  const funded = readJson<{ total_yen?: number }>(
    path.join(dayDir(date), 'freebudget_bets.json'));
  return funded?.total_yen ?? null;
}
