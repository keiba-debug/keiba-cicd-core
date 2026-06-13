/**
 * E-006 データ鮮度ヘッダ — 分析画面共通。
 *
 * coverage.to_date（被覆末日）を主役に鮮度バッジを出す。生成時刻(created_at)は補助表示。
 * 凍結検知: to_date が古いと赤「要更新」が出る（jockey 3ヶ月凍結インシデントの再発を表で気づける）。
 */
'use client';

import { AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { computeFreshness, freshnessClass } from '@/lib/freshness';

export interface FreshnessHeaderProps {
  coverage?: { from_date?: string; to_date?: string } | null;
  createdAt?: string | null;   // created_at / generated_at
  schemaVersion?: string | null;
  /** 追加注記（例: 出遅れの最新年は部分年で不安定） */
  note?: string;
}

export function FreshnessHeader({ coverage, createdAt, schemaVersion, note }: FreshnessHeaderProps) {
  const toDate = coverage?.to_date ?? null;
  const fresh = computeFreshness(toDate);
  const Icon =
    fresh.level === 'fresh' ? CheckCircle2 :
    fresh.level === 'stale' ? AlertTriangle : Clock;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border font-bold ${freshnessClass(fresh.level)}`}
        title={
          toDate
            ? `データ被覆: ${coverage?.from_date ?? '?'} 〜 ${toDate}` +
              (fresh.daysBehind != null ? `（${fresh.daysBehind}日前まで）` : '')
            : 'coverage 情報なし'
        }
      >
        <Icon className="w-3.5 h-3.5" />
        鮮度: {fresh.label}
        {toDate && <span className="font-normal">（〜{toDate}）</span>}
      </span>

      {fresh.level === 'stale' && (
        <span className="text-red-600 dark:text-red-400">
          ⚠ 集計が古い可能性。再生成を確認してください。
        </span>
      )}

      {createdAt && (
        <span className="text-gray-500">
          生成 {new Date(createdAt).toLocaleDateString('ja-JP')}
        </span>
      )}
      {schemaVersion && (
        <span className="text-gray-400 font-mono">{schemaVersion}</span>
      )}
      {note && (
        <span className="text-amber-600 dark:text-amber-400">※ {note}</span>
      )}
    </div>
  );
}
