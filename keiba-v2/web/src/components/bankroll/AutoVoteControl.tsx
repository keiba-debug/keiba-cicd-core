'use client';

/**
 * AutoVoteControl — freebudget 自動投票スケジューラの web コントロールパネル。
 * (Session 139 / Stream B = 「朝ブラウザから 開始/dry-run/停止 + 当日の投票状況を監視」)
 *
 * SoT = Python (freebudget_scheduler が書く state)。 このパネルは
 *   - GET  /api/freebudget/status : 当日 state を読んで表示 (15秒ポーリング)
 *   - POST /api/freebudget/start  : 単発パスを起動 (dry-run / LIVE、 SSE ログ)
 *   - POST /api/freebudget/halt   : 当日 halt (緊急ブレーキ)
 *
 * ★安全設計★:
 *   - LIVE (実投票) ボタンは funded artifact (freebudget_bets.json) がある時だけ活性。
 *     押すと金額確認ダイアログ → チェックボックス必須 → confirmed_total_yen を送信。
 *     API 側が artifact の total_yen と再照合 (二重ゲート。 画面の金額と実投票の一致保証)。
 *   - halt は安全側操作 (止めるだけ) かつ sticky (web から再開不可)。
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import {
  Play, Loader2, CheckCircle2, XCircle, OctagonX, RefreshCw,
  ShieldAlert, AlertTriangle, Clock, CircleSlash, Ban,
} from 'lucide-react';
import type {
  SchedulerStatus, VoteEntry, FundedBet,
} from '@/lib/data/freebudget-scheduler-reader';

// ── ヘルパ ──

function todayStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function yen(n: number | null | undefined): string {
  return n == null ? '—' : `¥${n.toLocaleString()}`;
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('ja-JP', {
      month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// 投票結果 exit_code → 表示 (0=成功 / -1=missed / 5,7,8=halt系 / 他=失敗)
function voteOutcome(v: VoteEntry): { icon: React.ReactNode; label: string; cls: string } {
  if (v.mode === 'dry-run') {
    return { icon: <Play className="h-3.5 w-3.5" />, label: 'dry-run(予定)', cls: 'text-blue-500' };
  }
  if (v.exit_code === 0) {
    return { icon: <CheckCircle2 className="h-3.5 w-3.5" />, label: '投票成立', cls: 'text-green-600' };
  }
  if (v.exit_code === -1) {
    return { icon: <CircleSlash className="h-3.5 w-3.5" />, label: '締切超過(未投票)', cls: 'text-gray-400' };
  }
  if ([5, 7, 8].includes(v.exit_code)) {
    return { icon: <OctagonX className="h-3.5 w-3.5" />, label: `停止系(exit ${v.exit_code})`, cls: 'text-red-600' };
  }
  return { icon: <XCircle className="h-3.5 w-3.5" />, label: `失敗(exit ${v.exit_code})`, cls: 'text-orange-500' };
}

// funded artifact の鮮度 (時間) — 古いと LIVE 前に警告
function fundedAgeHours(generatedAt: string | null): number | null {
  if (!generatedAt) return null;
  const t = new Date(generatedAt).getTime();
  if (Number.isNaN(t)) return null;
  return (Date.now() - t) / 3_600_000;
}

const FUNDED_STALE_WARN_H = 6; // この時間を超える funded artifact は LIVE 前に警告

// ── コンポーネント ──

export function AutoVoteControl() {
  const [date, setDate] = useState(todayStr());
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [busy, setBusy] = useState<'dryrun' | 'live' | 'halt' | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [logStatus, setLogStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');

  const [liveDialogOpen, setLiveDialogOpen] = useState(false);
  const [liveAck, setLiveAck] = useState(false);
  const [haltDialogOpen, setHaltDialogOpen] = useState(false);

  const logRef = useRef<HTMLDivElement>(null);

  const fetchStatus = useCallback(async (d: string) => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const res = await fetch(`/api/freebudget/status?date=${d}`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: SchedulerStatus = await res.json();
      setStatus(data);
    } catch (e) {
      setStatusError(String(e));
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  // 初回 + 日付変更でロード、 15秒ポーリング (アクション実行中は止める)
  useEffect(() => {
    fetchStatus(date);
    const id = setInterval(() => {
      if (busy === null) fetchStatus(date);
    }, 15_000);
    return () => clearInterval(id);
  }, [date, busy, fetchStatus]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  // 単発パス起動 (dry-run / LIVE) — SSE ログ消費
  const runStart = useCallback(async (live: boolean) => {
    setBusy(live ? 'live' : 'dryrun');
    setLog([]);
    setLogStatus('running');
    const body: Record<string, unknown> = { date, confirm: live };
    if (live) {
      body.acknowledged = true;
      body.confirmed_total_yen = status?.funded_total_yen ?? null;
    }
    try {
      const res = await fetch('/api/freebudget/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        // start は live 事前ゲート違反を SSE を開く前に 400 + JSON で返す
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        setLog((p) => [...p, `Error: ${err.error || res.statusText}`]);
        setLogStatus('error');
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) { setLogStatus('error'); return; }
      const decoder = new TextDecoder();
      let buffer = '';
      let sawError = false;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === 'log') setLog((p) => [...p, ev.message]);
            else if (ev.type === 'error') { sawError = true; setLog((p) => [...p, `Error: ${ev.message}`]); }
            else if (ev.type === 'done') setLog((p) => [...p, `── 完了 (${ev.mode}) ──`]);
          } catch { /* non-JSON */ }
        }
      }
      setLogStatus(sawError ? 'error' : 'success');
    } catch (e) {
      setLog((p) => [...p, `Error: ${String(e)}`]);
      setLogStatus('error');
    } finally {
      setBusy(null);
      fetchStatus(date);
    }
  }, [date, status, fetchStatus]);

  // 当日 halt
  const doHalt = useCallback(async () => {
    setBusy('halt');
    try {
      const res = await fetch('/api/freebudget/halt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date, reason: 'manual_stop_via_web' }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) setLog((p) => [...p, `⛔ 停止しました: ${data.output ?? ''}`]);
      else setLog((p) => [...p, `Error: ${data.error ?? `HTTP ${res.status}`}`]);
    } catch (e) {
      setLog((p) => [...p, `Error: ${String(e)}`]);
    } finally {
      setBusy(null);
      setHaltDialogOpen(false);
      fetchStatus(date);
    }
  }, [date, fetchStatus]);

  const hasFunded = (status?.funded_total_yen ?? null) != null && (status?.funded_n_bets ?? 0) > 0;
  const halted = status?.halted ?? false;
  const running = status?.running ?? false;
  const isToday = date === todayStr();
  const fundedAge = fundedAgeHours(status?.funded_generated_at ?? null);
  const fundedStale = fundedAge != null && fundedAge > FUNDED_STALE_WARN_H;
  // LIVE 可否: 当日のみ / funded あり / 停止中でない / 別パス実行中でない / 何も busy でない
  // (🔴-2: 過去日・未来日への誤投票を構造的に防ぐ。 dry-run は任意日OK)
  const liveEnabled = isToday && hasFunded && !halted && !running && busy === null;
  const dryEnabled = !running && busy === null;

  return (
    <Card className="border-amber-300 dark:border-amber-800">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-600" />
            自動投票コントロール
            <span className="text-xs font-normal text-muted-foreground">
              (freebudget スケジューラ)
            </span>
          </CardTitle>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value || todayStr())}
              className="rounded-md border bg-background px-2 py-1.5 text-sm"
            />
            <Button variant="outline" size="sm" onClick={() => fetchStatus(date)}
              disabled={statusLoading}>
              <RefreshCw className={`h-4 w-4 ${statusLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {statusError && (
          <div className="text-sm text-red-600">状態取得エラー: {statusError}</div>
        )}

        {/* ステータスバッジ */}
        <div className="flex items-center gap-2 flex-wrap">
          {!status?.exists ? (
            <Badge variant="outline" className="text-muted-foreground">未起動 (当日 state なし)</Badge>
          ) : (
            <Badge variant="outline" className={status.mode === 'live'
              ? 'border-red-400 text-red-600' : 'border-blue-400 text-blue-600'}>
              {status.mode === 'live' ? 'LIVE モード' : 'dry-run モード'}
            </Badge>
          )}
          {halted && (
            <Badge variant="destructive" className="gap-1">
              <Ban className="h-3 w-3" /> 停止中 (halted)
            </Badge>
          )}
          {running && (
            <Badge variant="outline" className="border-green-400 text-green-600 gap-1">
              <Loader2 className="h-3 w-3 animate-spin" /> パス実行中
              {status?.lock_age_sec != null && ` (${Math.round(status.lock_age_sec)}s)`}
            </Badge>
          )}
          {(status?.consecutive_failures ?? 0) > 0 && (
            <Badge variant="outline" className="border-orange-400 text-orange-600">
              連続失敗 {status?.consecutive_failures}回
            </Badge>
          )}
        </div>

        {halted && (
          <div className="rounded-md bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 p-3 text-sm">
            <div className="font-medium text-red-700 dark:text-red-400 flex items-center gap-1">
              <Ban className="h-4 w-4" /> 当日は停止中です
            </div>
            <div className="text-red-600/90 mt-1">{status?.halt_reason}</div>
            <div className="text-xs text-muted-foreground mt-1">
              ※ 停止は安全機構です。 web からは再開できません (再開には state ファイルの手動操作が必要)。
            </div>
          </div>
        )}

        {/* 当日投票額 vs 日次上限 (= 本日のスタート額/入金額。 朝に凍結) */}
        <div>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-muted-foreground">本日の投票額 (成立分)</span>
            <span className="font-mono font-bold">
              {yen(status?.voted_yen)} / {yen(status?.per_day_max_yen)}
            </span>
          </div>
          <Progress
            value={status?.per_day_max_yen
              ? Math.min(100, ((status?.voted_yen ?? 0) / status.per_day_max_yen) * 100)
              : 0}
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground mt-1">
            <span>
              {status?.day_budget_source
                ? `上限の根拠: ${status.day_budget_source}`
                : '上限: 既定値 (本日のスタート額 未設定)'}
            </span>
            <span className="font-mono">
              残 {yen(Math.max(0, (status?.per_day_max_yen ?? 0) - (status?.voted_yen ?? 0)))}
            </span>
          </div>
        </div>

        {/* 見送り (per-race スキップ理由) — halted でなくても「なぜ買わなかったか」を出す (穴B) */}
        {(status?.skips?.length ?? 0) > 0 && (
          <div className="rounded-md border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/20 p-3 text-sm">
            <div className="font-medium text-amber-700 dark:text-amber-400 flex items-center gap-1 mb-1">
              <CircleSlash className="h-4 w-4" /> 見送り {status?.skips.length}件 (理由つき)
            </div>
            <div className="space-y-0.5">
              {status!.skips.map((s) => (
                <div key={s.race_id} className="text-xs text-amber-700/90 dark:text-amber-300/80 font-mono">
                  {s.reason}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* funded artifact (買い目=金額確認の原本) */}
        <div className="rounded-md border p-3 text-sm bg-muted/30">
          <div className="flex items-center justify-between">
            <span className="font-medium">本日の買い目 (funded)</span>
            {hasFunded ? (
              <span className="font-mono">
                {status?.funded_n_bets}点 / 計 {yen(status?.funded_total_yen)}
              </span>
            ) : (
              <span className="text-muted-foreground">未生成</span>
            )}
          </div>
          {hasFunded && (
            <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
              <Clock className="h-3 w-3" /> 生成: {fmtTime(status?.funded_generated_at)}
              {fundedStale && (
                <span className="text-orange-600 flex items-center gap-0.5">
                  <AlertTriangle className="h-3 w-3" />
                  {fundedAge?.toFixed(0)}時間前 — 鮮度に注意
                </span>
              )}
            </div>
          )}
          {!hasFunded && (
            <div className="text-xs text-muted-foreground mt-1">
              LIVE 投票には買い目生成が必要: <code className="text-[11px]">freebudget_gen.bat {date} 10000</code>
            </div>
          )}
          {hasFunded && (status?.funded_bets?.length ?? 0) > 0 && (
            <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-1 text-xs">
              {status!.funded_bets.map((b: FundedBet, i) => (
                <div key={`${b.race_id}-${b.umaban}-${i}`}
                  className="flex justify-between gap-2 rounded bg-background px-2 py-1">
                  <span className="truncate">{b.umaban}番 {b.horse_name ?? ''}</span>
                  <span className="font-mono shrink-0">{yen(b.amount)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* アクションボタン */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" onClick={() => runStart(false)} disabled={!dryEnabled}>
            {busy === 'dryrun'
              ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              : <Play className="h-4 w-4 mr-2" />}
            dry-run で確認
          </Button>
          <Button
            className="bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
            onClick={() => { setLiveAck(false); fetchStatus(date); setLiveDialogOpen(true); }}
            disabled={!liveEnabled}
            title={!isToday ? 'LIVE 投票は当日のみ可能です (dry-run は任意日OK)'
              : !hasFunded ? '買い目 (funded) が未生成です'
              : halted ? '当日は停止中です' : running ? 'パス実行中です' : ''}
          >
            {busy === 'live'
              ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              : <ShieldAlert className="h-4 w-4 mr-2" />}
            本番投票を実行 (LIVE)
          </Button>
          <Button variant="outline"
            className="border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 ml-auto"
            onClick={() => setHaltDialogOpen(true)}
            disabled={busy !== null || halted}>
            <OctagonX className="h-4 w-4 mr-2" />
            停止 (当日halt)
          </Button>
        </div>

        {/* 実行ログ */}
        {log.length > 0 && (
          <div>
            <div className="text-xs font-medium flex items-center gap-1 mb-1">
              {logStatus === 'running' && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />}
              {logStatus === 'success' && <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />}
              {logStatus === 'error' && <XCircle className="h-3.5 w-3.5 text-red-500" />}
              実行ログ
            </div>
            <div ref={logRef}
              className="bg-gray-950 text-gray-300 rounded-md p-3 text-xs font-mono max-h-56 overflow-y-auto whitespace-pre-wrap">
              {log.map((line, i) => (
                <div key={i} className={line.startsWith('Error') ? 'text-red-400' : ''}>{line}</div>
              ))}
            </div>
          </div>
        )}

        {/* 投票一覧 */}
        {(status?.votes?.length ?? 0) > 0 && (
          <div>
            <div className="text-sm font-medium mb-2">本日の投票記録 ({status?.votes.length}件)</div>
            <div className="space-y-1">
              {status!.votes.map((v) => {
                const o = voteOutcome(v);
                return (
                  <div key={v.race_id}
                    className="flex items-center gap-2 text-sm border-b py-1.5">
                    <span className={`flex items-center gap-1 shrink-0 ${o.cls}`}>
                      {o.icon}
                    </span>
                    <span className="font-medium w-28 shrink-0 truncate">{v.label || v.race_id}</span>
                    <span className="text-xs text-muted-foreground w-24 shrink-0">{o.label}</span>
                    <span className="font-mono text-xs">単{(v.umaban || []).join('/')}</span>
                    <span className="font-mono ml-auto shrink-0">{yen(v.amount)}</span>
                    <span className="text-xs text-muted-foreground w-12 text-right shrink-0">
                      {v.at ? new Date(v.at).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>

      {/* LIVE 金額確認ダイアログ (二重ゲートの web 側) */}
      <Dialog open={liveDialogOpen} onOpenChange={setLiveDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <ShieldAlert className="h-5 w-5" /> 本番投票 (LIVE) の確認
            </DialogTitle>
            <DialogDescription>
              実際の馬券を購入します。 下記の金額・買い目を確認してください。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="rounded-md bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 p-3">
              <div className="flex justify-between text-sm">
                <span>対象日</span><span className="font-mono font-bold">{date}</span>
              </div>
              <div className="flex justify-between text-sm mt-1">
                <span>本日の買い目合計</span>
                <span className="font-mono font-bold text-red-600 text-lg">
                  {yen(status?.funded_total_yen)}
                </span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>点数 / 日次上限</span>
                <span className="font-mono">{status?.funded_n_bets}点 / {yen(status?.per_day_max_yen)}</span>
              </div>
            </div>

            {fundedStale && (
              <div className="text-xs text-orange-600 flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5" />
                買い目は {fundedAge?.toFixed(0)} 時間前の生成です。 最新オッズで作り直すことを推奨します。
              </div>
            )}

            {(status?.funded_bets?.length ?? 0) > 0 && (
              <div className="max-h-40 overflow-y-auto text-xs space-y-1">
                {status!.funded_bets.map((b, i) => (
                  <div key={`${b.race_id}-${b.umaban}-dlg${i}`}
                    className="flex justify-between border-b py-1">
                    <span>{b.race_id.slice(8)} {b.umaban}番 {b.horse_name ?? ''}</span>
                    <span className="font-mono">{yen(b.amount)}</span>
                  </div>
                ))}
              </div>
            )}

            <label className="flex items-start gap-2 text-sm cursor-pointer select-none">
              <input type="checkbox" checked={liveAck}
                onChange={(e) => setLiveAck(e.target.checked)}
                className="mt-0.5 h-4 w-4" />
              <span>上記の金額・買い目を確認しました (この内容で実投票します)</span>
            </label>
            <div className="text-[11px] text-muted-foreground space-y-1">
              <p>※ 投票は「発走 6〜2 分前」のレースのみ。 全レースを今すぐ買うわけではありません。</p>
              <p>
                ⚠ 上の金額は<strong>生成時点の朝の計画額</strong>です。 実際の投票は各レースの
                ウィンドウ到達時に<strong>最新オッズで再計算</strong>されるため、 確認額・買い目と
                変動しえます (実投票は日次上限 {yen(status?.per_day_max_yen)}・レース上限の範囲内)。
                送信時はサーバが計画額の一致を確認します。
              </p>
              <p>
                ⚠ LIVE 実行中はタブを閉じても投票は<strong>継続します</strong>。 止めるには
                [停止] を使ってください。
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setLiveDialogOpen(false)}>
              キャンセル
            </Button>
            <Button
              className="bg-red-600 hover:bg-red-700 text-white"
              disabled={!liveAck || !hasFunded}
              onClick={() => { setLiveDialogOpen(false); runStart(true); }}
            >
              <ShieldAlert className="h-4 w-4 mr-2" />
              {yen(status?.funded_total_yen)} を投票実行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 停止確認ダイアログ */}
      <Dialog open={haltDialogOpen} onOpenChange={setHaltDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <OctagonX className="h-5 w-5 text-red-600" /> 当日の自動投票を停止
            </DialogTitle>
            <DialogDescription>
              {date} の以降の自動投票を全て停止します。
            </DialogDescription>
          </DialogHeader>
          <div className="text-sm text-muted-foreground">
            ⚠ 停止すると当日は <strong>web から再開できません</strong> (再開には state ファイルの手動操作が必要)。
            既に投票成立した馬券は取り消されません。
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setHaltDialogOpen(false)} disabled={busy === 'halt'}>
              キャンセル
            </Button>
            <Button className="bg-red-600 hover:bg-red-700 text-white"
              onClick={doHalt} disabled={busy === 'halt'}>
              {busy === 'halt' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <OctagonX className="h-4 w-4 mr-2" />}
              停止する
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
