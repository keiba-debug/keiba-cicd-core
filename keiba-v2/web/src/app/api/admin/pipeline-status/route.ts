/**
 * パイプラインステータスAPI
 * GET /api/admin/pipeline-status?date=YYYY-MM-DD
 *
 * 選択日付のファイル状態から各アクションの実行状況を検出して返す
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface StepStatus {
  done: boolean;
  timestamp: string | null; // ISO date string
  detail?: string;
}

interface PipelineStatus {
  date: string;
  /** race_*.json の存在 */
  batch_prepare: StepStatus;
  /** kb_paddock の存在 */
  batch_morning: StepStatus;
  /** finish_position が non-null */
  batch_after_race: StepStatus;
  /** jrdb_pre_idm の存在 */
  jrdb_download: StepStatus;
  /** predictions.json の存在 */
  v4_predict: StepStatus;
  /** predictions.json 内 recommendations */
  vb_refresh: StepStatus;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const date = searchParams.get('date');
  if (!date) {
    return NextResponse.json({ error: 'date parameter required' }, { status: 400 });
  }

  const [y, m, d] = date.split('-');
  if (!y || !m || !d) {
    return NextResponse.json({ error: 'Invalid date format' }, { status: 400 });
  }

  const dateDir = path.join(DATA3_ROOT, 'races', y, m, d);

  const status: PipelineStatus = {
    date,
    batch_prepare: { done: false, timestamp: null },
    batch_morning: { done: false, timestamp: null },
    batch_after_race: { done: false, timestamp: null },
    jrdb_download: { done: false, timestamp: null },
    v4_predict: { done: false, timestamp: null },
    vb_refresh: { done: false, timestamp: null },
  };

  try {
    await fs.access(dateDir);
  } catch {
    // ディレクトリが存在しない → 全て未実行
    return NextResponse.json(status);
  }

  // race_*.json を列挙
  const files = await fs.readdir(dateDir);
  const raceFiles = files.filter(
    (f) => f.startsWith('race_') && f.endsWith('.json') && /^race_\d+\.json$/.test(f)
  );

  // --- batch_prepare: race JSONの存在 ---
  if (raceFiles.length > 0) {
    // 最初のrace JSONからmeta.created_atを取得
    let earliestTs: string | null = null;
    try {
      const firstRace = await fs.readFile(path.join(dateDir, raceFiles[0]), 'utf-8');
      const raceData = JSON.parse(firstRace);
      earliestTs = raceData?.meta?.created_at || null;
    } catch { /* ignore */ }
    status.batch_prepare = {
      done: true,
      timestamp: earliestTs,
      detail: `${raceFiles.length}R`,
    };
  }

  // サンプルレースJSON読み込み（他ステップの判定用）
  let sampleEntry: Record<string, unknown> | null = null;
  let hasResults = false;
  let hasPaddock = false;
  let hasJrdb = false;

  if (raceFiles.length > 0) {
    try {
      const content = await fs.readFile(path.join(dateDir, raceFiles[0]), 'utf-8');
      const raceData = JSON.parse(content);
      const entries = raceData?.entries || [];
      if (entries.length > 0) {
        sampleEntry = entries[0];
        // 成績情報: finish_position が非nullのエントリがあるか
        hasResults = entries.some(
          (e: Record<string, unknown>) => e.finish_position != null && e.finish_position !== ''
        );
        // パドック: kb_paddock があるか
        hasPaddock = entries.some(
          (e: Record<string, unknown>) => e.kb_paddock != null || e.paddock_comment != null
        );
        // JRDB: jrdb_pre_idm があるか
        hasJrdb = entries.some(
          (e: Record<string, unknown>) => e.jrdb_pre_idm != null
        );
      }
    } catch { /* ignore */ }
  }

  // --- batch_morning: パドック情報 ---
  if (hasPaddock) {
    status.batch_morning = { done: true, timestamp: null, detail: 'パドック取得済' };
  }

  // --- batch_after_race: 成績情報 ---
  if (hasResults) {
    status.batch_after_race = { done: true, timestamp: null, detail: '成績取得済' };
  }

  // --- jrdb_download: JRDB指標 ---
  if (hasJrdb) {
    status.jrdb_download = { done: true, timestamp: null, detail: 'JRDB付与済' };
  }

  // --- predictions.json ---
  const predPath = path.join(dateDir, 'predictions.json');
  try {
    const predContent = await fs.readFile(predPath, 'utf-8');
    const pred = JSON.parse(predContent);

    // v4_predict
    if (pred.races && pred.races.length > 0) {
      status.v4_predict = {
        done: true,
        timestamp: pred.created_at || null,
        detail: `${pred.races.length}R / VB:${pred.summary?.value_bets ?? '?'}`,
      };
    }

    // vb_refresh: bets.json or predictions.json内recommendations存在チェック
    let hasRecs = false;
    let recsTs: string | null = null;

    // 新形式: bets.json
    const betsPath = path.join(dateDir, 'bets.json');
    try {
      const betsContent = await fs.readFile(betsPath, 'utf-8');
      const betsData = JSON.parse(betsContent);
      if (betsData.recommendations && Object.keys(betsData.recommendations).length > 0) {
        hasRecs = true;
        recsTs = betsData.bets_generated_at || null;
      }
    } catch { /* bets.json not found */ }

    // 旧形式フォールバック: predictions.json内
    if (!hasRecs) {
      hasRecs =
        (pred.recommendations && typeof pred.recommendations === 'object'
          && Object.keys(pred.recommendations).length > 0);
      recsTs = pred.odds_updated_at || pred.created_at || null;
    }

    if (hasRecs) {
      status.vb_refresh = {
        done: true,
        timestamp: recsTs,
        detail: `${pred.summary?.value_bets ?? '?'} VBs`,
      };
    }
  } catch {
    // predictions.json が存在しない
  }

  return NextResponse.json(status);
}
