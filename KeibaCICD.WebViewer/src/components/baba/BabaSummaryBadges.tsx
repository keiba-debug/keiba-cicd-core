'use client';

/**
 * レース一覧ヘッダー用の馬場情報バッジ
 * 競馬場ごとに芝・ダート両方の馬場状態を表示
 */

import type { VenueBabaSummary } from '@/lib/data/baba-reader';
import { getConditionBadgeClassBySurface, getSurfaceInfo } from '@/lib/data/baba-utils';

interface BabaSummaryBadgesProps {
  summary: VenueBabaSummary | null;
}

/**
 * 芝/ダート個別の馬場バッジ
 */
function SurfaceBadge({
  surface,
  condition,
  moistureG,
  moisture4,
}: {
  surface: 'turf' | 'dirt';
  condition?: string;
  moistureG?: number;
  moisture4?: number;
}) {
  const surfaceInfo = getSurfaceInfo(surface);
  const colors = condition
    ? getConditionBadgeClassBySurface(condition, surface)
    : {
        bgClass: 'bg-gray-100 dark:bg-gray-800',
        textClass: 'text-gray-500 dark:text-gray-400',
        borderClass: 'border-gray-200 dark:border-gray-700',
      };

  // 含水率の表示
  const moisture = moistureG ?? moisture4;
  const moistureText = moisture != null ? `${moisture.toFixed(1)}%` : '-';

  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border ${colors.bgClass} ${colors.textClass} ${colors.borderClass}`}
      title={`${surfaceInfo.label}: ${condition || 'データなし'}（含水率: ${moistureText}）`}
    >
      <span className={`font-bold ${surfaceInfo.colorClass}`}>
        {surfaceInfo.label}
      </span>
      {condition && (
        <span className="font-bold">{condition}</span>
      )}
      {moisture != null && (
        <span className="opacity-75 text-[9px]">{moistureText}</span>
      )}
    </span>
  );
}

/**
 * 競馬場ヘッダー用の馬場情報バッジ（芝・ダート両方表示）
 */
export function BabaSummaryBadges({ summary }: BabaSummaryBadgesProps) {
  if (!summary || !summary.hasData) {
    return null;
  }

  return (
    <div className="flex items-center gap-1">
      {/* 芝の馬場情報 */}
      {summary.turf && (
        <SurfaceBadge
          surface="turf"
          condition={summary.turf.moistureConditionLabel}
          moistureG={summary.turf.moistureG}
          moisture4={summary.turf.moisture4}
        />
      )}
      
      {/* ダートの馬場情報 */}
      {summary.dirt && (
        <SurfaceBadge
          surface="dirt"
          condition={summary.dirt.moistureConditionLabel}
          moistureG={summary.dirt.moistureG}
          moisture4={summary.dirt.moisture4}
        />
      )}
    </div>
  );
}

/**
 * 馬場情報がない場合のプレースホルダー
 */
export function BabaNoDataBadge() {
  return (
    <span className="text-[10px] text-muted-foreground/60 italic">
      馬場情報なし
    </span>
  );
}
