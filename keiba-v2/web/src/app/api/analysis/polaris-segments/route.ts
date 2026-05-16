/**
 * GET /api/analysis/polaris-segments
 *   → list all run_ids (meta only, newest first)
 *
 * GET /api/analysis/polaris-segments?run_id=xxx
 *   → return full segments.json + period_compare.json + meta.json for that run
 */
import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';

const SEGMENTS_ROOT = path.join(KEIBA_DATA_ROOT, 'analysis', 'polaris_segments');

interface RunMeta {
  run_id: string;
  generated_at?: string;
  model?: string;
  total_races?: number;
  total_entries?: number;
  split_date?: string;
}

function listRuns(): RunMeta[] {
  if (!fs.existsSync(SEGMENTS_ROOT)) return [];
  const dirs = fs
    .readdirSync(SEGMENTS_ROOT, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  const runs: RunMeta[] = [];
  for (const run_id of dirs) {
    const metaPath = path.join(SEGMENTS_ROOT, run_id, 'meta.json');
    if (!fs.existsSync(metaPath)) continue;
    try {
      const meta = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
      runs.push({ run_id, ...meta });
    } catch {
      runs.push({ run_id });
    }
  }
  // newest first (by generated_at if present, else lexicographic run_id desc)
  runs.sort((a, b) => {
    const ka = a.generated_at || a.run_id;
    const kb = b.generated_at || b.run_id;
    return kb.localeCompare(ka);
  });
  return runs;
}

function loadRunDetail(run_id: string) {
  const dir = path.join(SEGMENTS_ROOT, run_id);
  if (!fs.existsSync(dir)) return null;

  const read = (name: string) => {
    const p = path.join(dir, name);
    if (!fs.existsSync(p)) return null;
    try {
      return JSON.parse(fs.readFileSync(p, 'utf-8'));
    } catch {
      return null;
    }
  };

  const segments = read('segments.json');
  if (!segments) return null;

  return {
    run_id,
    meta: read('meta.json'),
    segments,
    period_compare: read('period_compare.json'),
  };
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const run_id = searchParams.get('run_id');

  if (run_id) {
    const detail = loadRunDetail(run_id);
    if (!detail) {
      return NextResponse.json({ error: `run_id "${run_id}" not found` }, { status: 404 });
    }
    return NextResponse.json(detail);
  }

  return NextResponse.json({ runs: listRuns() });
}
