/**
 * 運用ステータス API（ダッシュボード主役化・Session 159）
 * GET /api/admin/ops-status?date=YYYY-MM-DD
 *
 * data-status API がカバーしない「2つの盲点」を1本で返す:
 *   1. ML特徴量キャッシュ鮮度（Session 151 の3ヶ月凍結事故・ml.cache_freshness 相当）
 *   2. vb_refresh タスクスケジューラの稼働（買い目が当日朝に確定する生命線）
 * さらに当日サマリー（指定日の準備完了度）を1行で返す。
 *
 * ML鮮度は ml/cache_freshness.py のロジックを Node 側で再実装（--quick 相当）。
 * race_date_index.json（505KB・軽量）の最大日付だけで Session 151 の凍結は捕捉できる
 * （凍結時は index も history も同時に止まっていたため）。237MB の horse_history は読まない。
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// ml.cache_freshness の DEFAULT_WARN_THRESHOLD_DAYS と揃える
const WARN_THRESHOLD_DAYS = 14;

// ML用インデックス（Python build_race_index.py が書く。web用 *_web.json とは別物）
const ML_INDEX_FILE = path.join(DATA3_ROOT, 'indexes', 'race_date_index.json');
const HISTORY_CACHE_FILE = path.join(DATA3_ROOT, 'ml', 'horse_history_cache.json');
const VB_TASK_NAME = 'KeibaCICD_vb_refresh';

interface MlCacheStatus {
  /** index_max が target に対し warn 閾値内なら fresh */
  isStale: boolean;
  indexMaxDate: string | null;
  indexGapDays: number | null;
  /** horse_history_cache.json の mtime（最大日付は237MB読むので mtime で代替表示）*/
  historyMtime: string | null;
  warnThresholdDays: number;
}

interface VbTaskStatus {
  /** schtasks が引けたか（タスク登録済みか）*/
  registered: boolean;
  /** 'Ready' | 'Running' | 'Disabled' など、取れなければ null */
  state: string | null;
  lastRunTime: string | null;
  lastResult: string | null;
  nextRunTime: string | null;
}

function daysBetween(from: string, to: string): number {
  const a = new Date(`${from}T00:00:00Z`).getTime();
  const b = new Date(`${to}T00:00:00Z`).getTime();
  return Math.round((b - a) / 86400000);
}

/** race_date_index.json の最大キー（YYYY-MM-DD）を読む。軽量。 */
async function getMlCacheStatus(targetDate: string): Promise<MlCacheStatus> {
  let indexMaxDate: string | null = null;
  try {
    const raw = await fs.readFile(ML_INDEX_FILE, 'utf-8');
    const idx = JSON.parse(raw) as Record<string, unknown>;
    const keys = Object.keys(idx);
    if (keys.length > 0) {
      indexMaxDate = keys.reduce((mx, k) => (k > mx ? k : mx), keys[0]);
    }
  } catch {
    /* ファイルが無い/壊れている → indexMaxDate=null（後段で stale 扱い）*/
  }

  let historyMtime: string | null = null;
  try {
    const st = await fs.stat(HISTORY_CACHE_FILE);
    historyMtime = st.mtime.toISOString();
  } catch {
    /* ignore */
  }

  const indexGapDays = indexMaxDate ? daysBetween(indexMaxDate, targetDate) : null;
  // index が読めない、または gap が閾値超なら stale
  const isStale = indexGapDays === null || indexGapDays > WARN_THRESHOLD_DAYS;

  return {
    isStale,
    indexMaxDate,
    indexGapDays,
    historyMtime,
    warnThresholdDays: WARN_THRESHOLD_DAYS,
  };
}

// State enum (Get-ScheduledTask): https://learn.microsoft.com/powershell/module/scheduledtasks
const TASK_STATE_LABEL: Record<number, string> = {
  0: 'Unknown',
  1: 'Disabled',
  2: 'Queued',
  3: 'Ready',
  4: 'Running',
};

/**
 * vb_refresh タスクの稼働状況を取得（Windows専用）。
 *
 * schtasks /query の list 出力は日本語ロケールだと CP932 で返り Node の toString() で文字化けし
 * 正規表現が効かない。Get-ScheduledTask + Get-ScheduledTaskInfo は構造化 JSON（State は数値 enum・
 * ロケール非依存）を返すのでこちらを使う。日付は PowerShell 側で ISO 文字列に整形してから渡す。
 */
function getVbTaskStatus(): Promise<VbTaskStatus> {
  return new Promise((resolve) => {
    const fallback: VbTaskStatus = {
      registered: false,
      state: null,
      lastRunTime: null,
      lastResult: null,
      nextRunTime: null,
    };
    const ps = [
      `$ErrorActionPreference='Stop';`,
      `try {`,
      `  $t = Get-ScheduledTask -TaskName '${VB_TASK_NAME}';`,
      `  $i = $t | Get-ScheduledTaskInfo;`,
      `  $o = [pscustomobject]@{`,
      `    state = [int]$t.State;`,
      `    lastRunTime = if ($i.LastRunTime) { $i.LastRunTime.ToString('o') } else { $null };`,
      `    lastResult = $i.LastTaskResult;`,
      `    nextRunTime = if ($i.NextRunTime) { $i.NextRunTime.ToString('o') } else { $null };`,
      `  };`,
      `  $o | ConvertTo-Json -Compress;`,
      `} catch { Write-Output 'NOTFOUND' }`,
    ].join(' ');

    try {
      const proc = spawn(
        'powershell',
        ['-NoProfile', '-NonInteractive', '-Command', ps],
        { windowsHide: true },
      );
      let out = '';
      const timer = setTimeout(() => {
        proc.kill();
        resolve(fallback);
      }, 8000);
      proc.stdout.on('data', (c) => {
        out += c.toString();
      });
      proc.on('error', () => {
        clearTimeout(timer);
        resolve(fallback);
      });
      proc.on('close', () => {
        clearTimeout(timer);
        const trimmed = out.trim();
        if (!trimmed || trimmed.includes('NOTFOUND')) {
          resolve(fallback);
          return;
        }
        try {
          const j = JSON.parse(trimmed) as {
            state: number;
            lastRunTime: string | null;
            lastResult: number | null;
            nextRunTime: string | null;
          };
          resolve({
            registered: true,
            state: TASK_STATE_LABEL[j.state] ?? `State${j.state}`,
            lastRunTime: j.lastRunTime,
            lastResult: j.lastResult != null ? String(j.lastResult) : null,
            nextRunTime: j.nextRunTime,
          });
        } catch {
          resolve(fallback);
        }
      });
    } catch {
      resolve(fallback);
    }
  });
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const targetDate =
    searchParams.get('date') || new Date().toISOString().substring(0, 10);

  const [mlCache, vbTask] = await Promise.all([
    getMlCacheStatus(targetDate),
    getVbTaskStatus(),
  ]);

  return NextResponse.json({
    targetDate,
    mlCache,
    vbTask,
    generatedAt: new Date().toISOString(),
  });
}
