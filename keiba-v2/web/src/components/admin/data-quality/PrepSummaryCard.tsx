'use client';

/**
 * 次開催日の準備サマリーカード（ダッシュボード主役化・Session 159）
 *
 * 「次に来る開催日の準備が整っているか」を1枚で示す。data-status の対象日行
 * （インデックス/race JSON/JRDB/予測）に、ops-status の2盲点
 * （MLキャッシュ鮮度・vb_refresh タスク稼働）を重ねて全項目 ◯/△/× で表示する。
 *
 * 今回（6/14 が web に出なかった件）のような「ML予測は揃っているのに web 表示
 * インデックス未反映」を、このカードの『web表示』項目だけ見れば即検知できるのが狙い。
 */

import React, { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import type { DateDataStatus } from '@/app/api/admin/data-status/route';

interface OpsStatus {
  targetDate: string;
  mlCache: {
    isStale: boolean;
    indexMaxDate: string | null;
    indexGapDays: number | null;
    historyMtime: string | null;
    warnThresholdDays: number;
  };
  vbTask: {
    registered: boolean;
    state: string | null;
    lastRunTime: string | null;
    lastResult: string | null;
    nextRunTime: string | null;
  };
}

type Level = 'ok' | 'warn' | 'bad' | 'na';

function Pill({ level, children }: { level: Level; children: React.ReactNode }) {
  const map: Record<Level, string> = {
    ok: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    warn: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    bad: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
    na: 'bg-muted text-muted-foreground',
  };
  const icon = { ok: '✓', warn: '△', bad: '✗', na: '—' }[level];
  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${map[level]}`}>
      {icon} {children}
    </span>
  );
}

function Row({ label, level, detail }: { label: string; level: Level; detail?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        {detail && <span className="text-xs text-muted-foreground font-mono">{detail}</span>}
        <Pill level={level}>{LEVEL_TEXT[level]}</Pill>
      </div>
    </div>
  );
}

const LEVEL_TEXT: Record<Level, string> = { ok: 'OK', warn: '注意', bad: 'NG', na: '—' };

/** dates から「次に来る開催日」を選ぶ。未来で最も近い日、無ければ最新日。 */
function pickTargetDate(dates: DateDataStatus[]): DateDataStatus | null {
  if (dates.length === 0) return null;
  const today = new Date().toISOString().substring(0, 10);
  // dates は降順。今日以降で最も近い（=最小の future）を選ぶ。
  const futureOrToday = dates.filter((d) => d.date >= today);
  if (futureOrToday.length > 0) {
    return futureOrToday[futureOrToday.length - 1]; // 降順配列の末尾＝最も近い未来
  }
  return dates[0]; // 全部過去なら最新
}

export function PrepSummaryCard() {
  const [target, setTarget] = useState<DateDataStatus | null>(null);
  const [ops, setOps] = useState<OpsStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const dsRes = await fetch('/api/admin/data-status');
      const ds = await dsRes.json();
      if (ds.error) throw new Error(ds.error);
      const tgt = pickTargetDate(ds.dates ?? []);
      setTarget(tgt);

      if (tgt) {
        const opsRes = await fetch(`/api/admin/ops-status?date=${tgt.date}`);
        setOps(await opsRes.json());
      }
      setRefreshedAt(new Date().toLocaleTimeString('ja-JP'));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // ── 各項目のレベル判定 ──
  const indexLevel: Level = !target ? 'na' : target.indexCount > 0 ? 'ok' : 'bad';
  const raceJsonLevel: Level = !target
    ? 'na'
    : target.raceJsonCount === 0
      ? 'bad'
      : target.indexCount > 0 && target.raceJsonCount < target.indexCount
        ? 'warn'
        : 'ok';
  const jrdbLevel: Level = !target
    ? 'na'
    : target.raceJsonCount === 0
      ? 'na'
      : target.jrdbRate >= 100
        ? 'ok'
        : target.jrdbRate > 0
          ? 'warn'
          : 'bad';
  const predLevel: Level = !target ? 'na' : target.hasPredictions ? 'ok' : 'bad';

  // 盲点1: web表示インデックス（data-status は web_index ファイルを読むので indexCount>0 = web に出る）
  const webLevel: Level = !target ? 'na' : target.indexCount > 0 ? 'ok' : 'bad';

  // 盲点2: MLキャッシュ鮮度
  const mlLevel: Level = !ops ? 'na' : ops.mlCache.isStale ? 'bad' : 'ok';

  // 盲点3: vb_refresh タスク
  const vbLevel: Level = !ops
    ? 'na'
    : !ops.vbTask.registered
      ? 'bad'
      : ops.vbTask.state === 'Disabled'
        ? 'bad'
        : ops.vbTask.lastResult && ops.vbTask.lastResult !== '0'
          ? 'warn'
          : 'ok';

  // 総合判定
  const levels = [indexLevel, raceJsonLevel, jrdbLevel, predLevel, webLevel, mlLevel, vbLevel];
  const overall: Level = levels.includes('bad')
    ? 'bad'
    : levels.includes('warn')
      ? 'warn'
      : levels.includes('na')
        ? 'na'
        : 'ok';
  const overallText = { ok: '準備完了', warn: '一部注意あり', bad: '未完了あり', na: '不明' }[overall];
  const overallIcon = { ok: '✅', warn: '⚠️', bad: '❌', na: '—' }[overall];

  return (
    <Card className="border-2 border-blue-200 dark:border-blue-800 shadow-lg">
      <CardHeader className="pb-3 bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-950 dark:to-cyan-950">
        <CardTitle className="text-lg flex items-center justify-between">
          <span className="flex items-center gap-2">
            <span className="text-2xl">{overallIcon}</span>
            <span>次開催の準備サマリー</span>
            {target && (
              <span className="text-sm font-normal text-muted-foreground font-mono">
                {target.date}
              </span>
            )}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{overallText}</span>
            <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4">
        {error && (
          <div className="mb-3 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}
        {!target && !loading ? (
          <p className="text-sm text-muted-foreground">対象開催日が見つかりません。</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">データ生成</div>
              <Row label="インデックス" level={indexLevel} detail={target ? `${target.indexCount}R` : undefined} />
              <Row
                label="race JSON"
                level={raceJsonLevel}
                detail={target ? `${target.raceJsonCount}/${target.indexCount}` : undefined}
              />
              <Row label="JRDB統合" level={jrdbLevel} detail={target ? `${target.jrdbRate}%` : undefined} />
              <Row label="ML予測" level={predLevel} detail={target?.predictionsAt?.replace('T', ' ').substring(5, 16)} />
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">表示・運用（盲点チェック）</div>
              <Row label="web出馬表に表示" level={webLevel} />
              <Row
                label="MLキャッシュ鮮度"
                level={mlLevel}
                detail={ops?.mlCache.indexMaxDate ?? undefined}
              />
              <Row
                label="vb_refreshタスク"
                level={vbLevel}
                detail={ops?.vbTask.state ?? undefined}
              />
              {ops?.vbTask.nextRunTime && (
                <div className="text-[11px] text-muted-foreground mt-0.5 text-right">
                  次回 {ops.vbTask.nextRunTime.replace('T', ' ').substring(5, 16)}
                </div>
              )}
            </div>
          </div>
        )}
        {refreshedAt && (
          <p className="text-[11px] text-muted-foreground mt-3">最終更新: {refreshedAt}</p>
        )}
      </CardContent>
    </Card>
  );
}
