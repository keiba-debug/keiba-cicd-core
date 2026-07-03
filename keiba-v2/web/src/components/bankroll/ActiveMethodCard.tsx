'use client';

/**
 * ActiveMethodCard — 自動投票画面に「今どんな買い目を狙っているか」を出すカード (Session 176/177)。
 *
 * ふくだ要望: 「こういう単勝狙ってるよ」という ★狙い（エッジの中身）★ を画面で分かるように。
 * SoT = /api/bankroll/active-method（bettype_auto.bat の起動行 + bankroll/config.json）。
 * S177 §8-4: 複数スリーブ並行運用に対応し、有効/停止スリーブを一覧で並べる。
 */

import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Target, ArrowRight, CheckCircle2, PauseCircle, Loader2 } from 'lucide-react';

interface MethodInfo {
  key: string;
  label: string;
  thesis: string;
  betType: string;
  resultsLink: string | null;
  hasMasterSwitch: boolean;
}
interface SleeveParams {
  initialBankrollYen: number;
  betPct: number;
  dayPct: number;
}
interface SleeveInfo {
  method: MethodInfo;
  active: boolean;
  params: SleeveParams;
}
interface ActiveMethod {
  method: MethodInfo;
  active: boolean;
  gap: SleeveParams & { enabled: boolean };
  sleeves?: SleeveInfo[];
  totalDayCapYen?: number;
}

function yen(n: number): string {
  return `¥${n.toLocaleString()}`;
}

/** 1スリーブ／1方式のカード本体 (単一・複数で共通)。 */
function MethodCardBody({ method, active, params }: {
  method: MethodInfo;
  active: boolean;
  params?: SleeveParams;
}) {
  return (
    <Card className="border-amber-300 dark:border-amber-800 bg-amber-50/40 dark:bg-amber-950/10">
      <CardContent className="py-4 space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Target className="h-5 w-5 text-amber-600" />
            <span className="text-xs text-muted-foreground">現在狙っている買い目</span>
            <span className="text-base font-bold">{method.label}</span>
          </div>
          {active ? (
            // ★稼働中バッジは「状態の色」=緑で統一 (BudgetForm と一致)。card の amber はスリーブ枠の色。
            <Badge className="bg-green-600 hover:bg-green-600 text-white gap-1">
              <CheckCircle2 className="h-3 w-3" /> 稼働中
            </Badge>
          ) : (
            <Badge variant="outline" className="text-muted-foreground gap-1">
              <PauseCircle className="h-3 w-3" /> 停止中{method.hasMasterSwitch ? '（有効化待ち）' : ''}
            </Badge>
          )}
        </div>

        <p className="text-sm leading-relaxed">{method.thesis}</p>

        <div className="flex items-center gap-2 flex-wrap text-xs">
          <Badge variant="outline">{method.betType}</Badge>
          {params && method.hasMasterSwitch && (
            <>
              <Badge variant="outline">初期 {yen(params.initialBankrollYen)}</Badge>
              <Badge variant="outline">
                {method.key === 'comment_a' ? '1単位' : '1点'} 残高×{params.betPct}%
              </Badge>
              <Badge variant="outline">日次上限 残高×{params.dayPct}%</Badge>
            </>
          )}
        </div>

        {method.resultsLink && (
          <a
            href={method.resultsLink}
            className="inline-flex items-center gap-1 text-sm text-amber-700 dark:text-amber-400 hover:underline font-medium"
          >
            検証結果を見る
            <ArrowRight className="h-3.5 w-3.5" />
          </a>
        )}

        {method.hasMasterSwitch && !active && (
          <p className="text-xs text-muted-foreground">
            ※ 現在は停止中です。<a href="/bankroll" className="underline">資金管理</a>で「有効にする」を選んで保存すると稼働します。
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function ActiveMethodCard() {
  const [data, setData] = useState<ActiveMethod | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch('/api/bankroll/active-method', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive && d && d.method) setData(d); })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-4 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> 現在の買い目方式を確認中…
        </CardContent>
      </Card>
    );
  }
  if (!data) return null;

  // ★複数スリーブ並行 (S177)★: sleeves 配列があれば一覧で並べる。
  if (data.sleeves && data.sleeves.length > 0) {
    return (
      <div className="space-y-2">
        {data.sleeves.map((sl) => (
          <MethodCardBody
            key={sl.method.key}
            method={sl.method}
            active={sl.active}
            params={sl.params}
          />
        ))}
        {(data.totalDayCapYen ?? 0) > 0 && (
          <p className="text-xs text-muted-foreground px-1">
            スリーブ全体の日次上限: {yen(data.totalDayCapYen!)}（合算がこれを超えると優先度の低い方から脚を落とす）
          </p>
        )}
      </div>
    );
  }

  // 単一方式 (combo 系・freebudget 等)。
  return (
    <MethodCardBody
      method={data.method}
      active={data.active}
      params={data.method.key === 'gap_tansho' ? data.gap : undefined}
    />
  );
}
