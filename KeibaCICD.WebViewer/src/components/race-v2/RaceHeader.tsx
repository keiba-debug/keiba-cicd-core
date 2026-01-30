'use client';

/**
 * レース情報ヘッダーコンポーネント（新方式）
 */

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { RaceInfo, RaceMeta, getTrackLabel } from '@/types/race-data';
import { Badge } from '@/components/ui/badge';
import { Calendar, MapPin, Clock, MessageCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { CourseRpciInfo, RpciTrend } from '@/lib/data/rpci-standards-reader';
import type { BabaCondition } from '@/lib/data/baba-reader';
import { getConditionBadgeClass } from '@/lib/data/baba-utils';

interface ExternalLinks {
  paddockUrl: string | null;
  raceUrl: string | null;
  patrolUrl: string | null;
  keibabookUrl: string;
  netkeibaUrl: string;
  netkeibaBbsUrl: string;
}

interface RaceHeaderProps {
  raceInfo: RaceInfo;
  meta: RaceMeta;
  raceComment?: string;
  /** URLから取得した正確な日付（YYYY-MM-DD形式） - JSONデータより優先 */
  urlDate?: string;
  /** URLから取得した正確な競馬場名 - JSONデータより優先 */
  urlTrack?: string;
  /** 外部リンク */
  externalLinks?: ExternalLinks;
  /** RPCI基準値情報 */
  rpciInfo?: CourseRpciInfo | null;
  /** 馬場コンディション（クッション値・含水率） */
  babaInfo?: BabaCondition | null;
}

// 競馬場テキストカラー
const getTrackTextClass = (trackName: string) => {
  const map: Record<string, string> = {
    '中山': 'text-[var(--color-venue-nakayama)]',
    '京都': 'text-[var(--color-venue-kyoto)]',
    '小倉': 'text-[var(--color-venue-kokura)]',
    '東京': 'text-[var(--color-venue-tokyo)]',
    '阪神': 'text-[var(--color-venue-hanshin)]',
  };
  return map[trackName] || 'text-primary';
};

export default function RaceHeader({
  raceInfo,
  meta,
  raceComment,
  urlDate,
  urlTrack,
  externalLinks,
  rpciInfo,
  babaInfo,
}: RaceHeaderProps) {
  // URLパラメータを優先、なければJSONデータを使用
  const displayDate = urlDate || raceInfo.date;
  const displayVenue = urlTrack || raceInfo.venue;
  
  // コース情報
  const courseInfo = buildCourseInfo(raceInfo);
  const trackColor = getTrackTextClass(displayVenue);

  return (
    <div className="bg-white dark:bg-gray-900 border-b">
      {/* パンくずリスト */}
      <nav className="px-4 py-2 flex items-center space-x-2 text-sm text-muted-foreground border-b bg-gray-50 dark:bg-gray-800/50">
        <Link href="/" className="hover:underline">トップ</Link>
        <span>/</span>
        <Link href={`/?date=${urlDate}`} className="hover:underline">{urlDate}</Link>
        <span>/</span>
        <span className={trackColor}>{displayVenue}</span>
        <span>/</span>
        <span className="text-foreground font-medium">{raceInfo.race_number}R</span>
      </nav>

      {/* メインヘッダー */}
      <div className="px-4 py-4">
        <div className="flex items-start justify-between gap-4">
          {/* 左側: レース情報 */}
          <div className="flex-1">
            {/* 1行目: レース番号 + レース名 */}
            <div className="flex items-center gap-3 mb-2">
              <span className={`text-2xl font-bold ${trackColor}`}>{raceInfo.race_number}R</span>
              <h1 className="text-xl font-bold">{raceInfo.race_name || ''}</h1>
            </div>
            
            {/* 2行目: 競馬場 + コース + 発走時刻 + クラス */}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className={`font-bold ${trackColor}`}>{displayVenue}</span>
              
              {/* コース情報バッジ */}
              {courseInfo && (
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded-sm ${getCourseBadgeClass(raceInfo.track)}`}>
                  {courseInfo}
                </span>
              )}
              
              {/* RPCI傾向バッジ */}
              {rpciInfo && (
                <RpciBadge rpciInfo={rpciInfo} />
              )}

              {/* 馬場コンディション（クッション値・含水率） */}
              {babaInfo && (
                <BabaConditionBadge babaInfo={babaInfo} />
              )}
              
              {/* 発走時刻 */}
              {(raceInfo.post_time || raceInfo.start_time) && (
                <span className="text-muted-foreground text-xs font-mono">
                  {raceInfo.start_time || raceInfo.post_time}発走
                </span>
              )}
              
              {/* グレード/クラス */}
              {raceInfo.grade && raceInfo.grade !== '' && (
                <GradeBadge grade={raceInfo.grade} />
              )}
              
              {/* レース条件 */}
              {raceInfo.race_condition && (
                <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded-sm">
                  {raceInfo.race_condition}
                </span>
              )}
            </div>
          </div>

          {/* 右側: リンク群 */}
          {externalLinks && (
            <div className="flex items-center gap-3">
              {/* JRAビュアーリンク */}
              <div className="flex items-center gap-1">
                {externalLinks.paddockUrl && (
                  <a
                    href={externalLinks.paddockUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-8 h-8 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold hover:opacity-80 transition-opacity"
                    title="JRAレーシングビュアー パドック"
                  >
                    パ
                  </a>
                )}
                {externalLinks.raceUrl && (
                  <a
                    href={externalLinks.raceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-8 h-8 rounded-full bg-green-600 text-white flex items-center justify-center text-xs font-bold hover:opacity-80 transition-opacity"
                    title="JRAレーシングビュアー レース"
                  >
                    レ
                  </a>
                )}
                {externalLinks.patrolUrl && (
                  <a
                    href={externalLinks.patrolUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-8 h-8 rounded-full bg-rose-500 text-white flex items-center justify-center text-xs font-bold hover:opacity-80 transition-opacity"
                    title="JRAレーシングビュアー パトロール"
                  >
                    T
                  </a>
                )}
              </div>

              {/* 区切り線 */}
              <div className="w-px h-6 bg-border" />

              {/* 外部リンク */}
              <div className="flex items-center gap-1">
                <a
                  href={externalLinks.keibabookUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                  title="競馬ブック"
                >
                  <Image src="/keibabook.ico" alt="競馬ブック" width={24} height={24} className="rounded" />
                </a>
                <a
                  href={externalLinks.netkeibaUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                  title="netkeiba"
                >
                  <Image src="/netkeiba.png" alt="netkeiba" width={24} height={24} className="rounded" />
                </a>
                <a
                  href={externalLinks.netkeibaBbsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center text-blue-600"
                  title="netkeiba BBS"
                >
                  <MessageCircle className="w-5 h-5" />
                </a>
              </div>
            </div>
          )}
        </div>

        {/* 本紙見解 */}
        {raceComment && (
          <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <div className="text-xs font-medium text-amber-800 dark:text-amber-400 mb-1">
              📰 本紙の見解
            </div>
            <p className="text-sm text-gray-800 dark:text-gray-200">
              {raceComment}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * コースバッジのスタイルを取得（レース一覧と共通）
 */
function getCourseBadgeClass(track?: string): string {
  if (!track) return 'text-muted-foreground bg-muted';
  if (track === '芝' || track.startsWith('芝')) {
    return 'text-[var(--color-surface-turf)] bg-[var(--color-surface-turf)]/10';
  }
  if (track === 'ダ' || track === 'ダート' || track.startsWith('ダ')) {
    return 'text-[var(--color-surface-dirt)] bg-[var(--color-surface-dirt)]/10';
  }
  if (track === '障' || track.startsWith('障')) {
    return 'text-[var(--color-surface-steeplechase)] bg-[var(--color-surface-steeplechase)]/10';
  }
  return 'text-muted-foreground bg-muted';
}

/**
 * コース情報を構築
 */
function buildCourseInfo(raceInfo: RaceInfo): string {
  const parts: string[] = [];
  
  if (raceInfo.track) {
    parts.push(getTrackLabel(raceInfo.track));
  }
  
  if (raceInfo.distance) {
    parts.push(`${raceInfo.distance}m`);
  }
  
  if (raceInfo.direction) {
    parts.push(raceInfo.direction);
  }
  
  return parts.join(' ');
}

/**
 * グレードバッジ
 */
function GradeBadge({ grade }: { grade: string }) {
  const gradeStyles: Record<string, string> = {
    'G1': 'bg-gradient-to-r from-yellow-400 to-amber-500 text-white font-bold',
    'G2': 'bg-gradient-to-r from-red-500 to-rose-600 text-white font-bold',
    'G3': 'bg-gradient-to-r from-green-500 to-emerald-600 text-white font-bold',
    'OP': 'bg-purple-600 text-white',
    '重賞': 'bg-indigo-600 text-white',
    '特別': 'bg-blue-600 text-white',
    '1勝': 'bg-gray-500 text-white',
    '2勝': 'bg-gray-600 text-white',
    '3勝': 'bg-gray-700 text-white',
  };

  const style = gradeStyles[grade] || 'bg-gray-400 text-white';

  return (
    <Badge className={style}>
      {grade}
    </Badge>
  );
}

/**
 * RPCI傾向バッジ
 */
function RpciBadge({ rpciInfo }: { rpciInfo: CourseRpciInfo }) {
  const trendStyles: Record<RpciTrend, { bg: string; text: string; icon: React.ReactNode }> = {
    instantaneous: {
      bg: 'bg-blue-100',
      text: 'text-blue-700',
      icon: <TrendingUp className="w-3 h-3" />,
    },
    sustained: {
      bg: 'bg-red-100',
      text: 'text-red-700',
      icon: <TrendingDown className="w-3 h-3" />,
    },
    neutral: {
      bg: 'bg-gray-100',
      text: 'text-gray-600',
      icon: <Minus className="w-3 h-3" />,
    },
  };

  const style = trendStyles[rpciInfo.trend];

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${style.bg} ${style.text}`}
      title={`RPCI: ${rpciInfo.rpciMean.toFixed(1)} (n=${rpciInfo.sampleCount})${rpciInfo.similarCourses.length > 0 ? `\n類似: ${rpciInfo.similarCourses.join(', ')}` : ''}`}
    >
      {style.icon}
      <span>{rpciInfo.trendLabel}</span>
      <span className="text-[10px] opacity-70">({rpciInfo.rpciMean.toFixed(1)})</span>
    </span>
  );
}

/**
 * 馬場コンディション（クッション値・含水率）バッジ
 */
function BabaConditionBadge({ babaInfo }: { babaInfo: BabaCondition }) {
  const parts: string[] = [];
  if (babaInfo.cushion != null) {
    parts.push(`クッション ${babaInfo.cushion.toFixed(1)}${babaInfo.cushionLabel ? `（${babaInfo.cushionLabel}）` : ''}`);
  }
  if (babaInfo.moistureG != null || babaInfo.moisture4 != null) {
    const g = babaInfo.moistureG != null ? `G前 ${babaInfo.moistureG.toFixed(1)}%` : '';
    const c4 = babaInfo.moisture4 != null ? `4C ${babaInfo.moisture4.toFixed(1)}%` : '';
    parts.push([g, c4].filter(Boolean).join(' / '));
  }
  const conditionLabel = babaInfo.moistureConditionLabel
    ? `（${babaInfo.moistureConditionLabel}の目安）`
    : '';
  const label =
    parts.length > 0
      ? `馬場: ${parts.join(' / ')}${conditionLabel}`
      : '馬場: 計測なし';
  if (!label) return null;

  const badgeClass = babaInfo.moistureConditionLabel
    ? getConditionBadgeClass(babaInfo.moistureConditionLabel)
    : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200';

  return (
    <span
      className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-sm ${badgeClass}`}
      title="JRA早見表に基づく目安です。馬場状態は含水率だけで決まるものではありません。"
    >
      {label}
    </span>
  );
}
