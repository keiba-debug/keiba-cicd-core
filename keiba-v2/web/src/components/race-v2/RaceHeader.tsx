'use client';

/**
 * レース情報ヘッダーコンポーネント（新方式）
 */

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { RaceInfo, RaceMeta, getTrackLabel } from '@/types/race-data';
import { Badge } from '@/components/ui/badge';
import { Calendar, MapPin, Clock, MessageCircle, TrendingUp, TrendingDown, Minus, Activity, BarChart3 } from 'lucide-react';
import type { CourseRpciInfo, RpciTrend } from '@/lib/data/rpci-standards-reader';
import type { BabaCondition } from '@/lib/data/baba-reader';
import type { TrackBias } from '@/lib/data/jrdb-kaa-reader';
import { getConditionBadgeClassBySurface, getSurfaceInfo, getWeatherIcon, getWeatherFromCode, getBiasLabel } from '@/lib/data/baba-utils';
import type { LapsData } from '@/types/race-data';
import { RACE_TREND_V2_LABELS, RACE_TREND_V2_COLORS, getLap33Interpretation, type RaceTrendV2Type } from '@/lib/data/rpci-utils';

interface ExternalLinks {
  paddockUrl: string | null;
  raceUrl: string | null;
  patrolUrl: string | null;
  keibabookUrl: string | null;
  netkeibaUrl: string | null;
  netkeibaBbsUrl: string | null;
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
  /** JRDB KAA トラックバイアス */
  trackBias?: TrackBias | null;
  /** JRA-VAN形式のレースID（オッズ表用） */
  jraRaceId?: string | null;
  /** ラップデータ（ペース傾向バッジ表示用） */
  laps?: LapsData | null;
  /** 差し決着度（closing model） */
  closingRaceProba?: number | null;
  /** 指数表ページURL */
  idmCompareUrl?: string;
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
  trackBias,
  jraRaceId,
  laps,
  closingRaceProba,
  idmCompareUrl,
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
            {/* 1行目: 発走時刻 + クラス + レース名 */}
            <div className="flex items-center gap-3 mb-2">
              {/* 発走時刻（目立つ） */}
              {(raceInfo.post_time || raceInfo.start_time) && (
                <span className="text-2xl font-bold text-blue-600 dark:text-blue-400 font-mono">
                  {raceInfo.start_time || raceInfo.post_time}
                </span>
              )}
              
              {/* クラス（レース名） */}
              <div className="flex items-center gap-2">
                {raceInfo.race_condition && (
                  <span className="text-lg font-bold text-gray-700 dark:text-gray-300">
                    {raceInfo.race_condition}
                  </span>
                )}
                {raceInfo.race_name && raceInfo.race_name !== raceInfo.race_condition && (
                  <h1 className="text-lg font-bold">{raceInfo.race_name}</h1>
                )}
              </div>
            </div>
            
            {/* 2行目: レース番号 + 競馬場 + コース距離 */}
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-xl font-bold ${trackColor}`}>{raceInfo.race_number}R</span>
              <span className={`font-bold ${trackColor}`}>{displayVenue}</span>

              {/* コース情報バッジ */}
              {courseInfo && (
                <span className={`text-sm font-bold px-3 py-1 rounded ${getCourseBadgeClass(raceInfo.track)}`}>
                  {courseInfo}
                </span>
              )}

              {/* === 事前情報 === */}
              {(raceInfo.track_condition || babaInfo) && (
                <>
                  <span className="text-gray-300 dark:text-gray-600">|</span>
                  <TrackConditionBadge
                    raceInfo={raceInfo}
                    babaInfo={babaInfo}
                    trackBias={trackBias}
                  />
                  {babaInfo && <MoistureDetail babaInfo={babaInfo} />}
                </>
              )}

              {(rpciInfo || (closingRaceProba != null && closingRaceProba >= 0.10)) && (
                <span className="text-gray-300 dark:text-gray-600">|</span>
              )}

              {rpciInfo && (
                <RpciBadge rpciInfo={rpciInfo} />
              )}

              {closingRaceProba != null && closingRaceProba >= 0.10 && (
                <span
                  className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                    closingRaceProba >= 0.18
                      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                      : closingRaceProba >= 0.13
                      ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
                      : 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400'
                  }`}
                  title={`差し決着度: ${(closingRaceProba * 100).toFixed(1)}% — 差し/追込が好走しやすいレース`}
                >
                  差し {(closingRaceProba * 100).toFixed(0)}%
                </span>
              )}

              {/* === 結果情報（レース後のみ） === */}
              {((trackBias && trackBias.dataKubun === 4) || laps?.race_trend_v2) && (
                <>
                  <span className="text-gray-300 dark:text-gray-600">|</span>
                  <span className="text-[10px] text-muted-foreground font-medium bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">結果</span>
                </>
              )}

              {trackBias && trackBias.dataKubun === 4 && (
                <TrackBiasBadge trackBias={trackBias} surface={babaInfo?.surface ?? (raceInfo.track?.startsWith('ダ') ? 'dirt' : 'turf')} />
              )}

              {laps?.race_trend_v2 && (
                <RaceTrendBadge trendV2={laps.race_trend_v2} lap33={laps.lap33} />
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
                {externalLinks.keibabookUrl && (
                <a
                  href={externalLinks.keibabookUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                  title="競馬ブック"
                >
                  <Image src="/keibabook.ico" alt="競馬ブック" width={24} height={24} className="rounded" />
                </a>
                )}
                {externalLinks.netkeibaUrl && (
                  <a
                    href={externalLinks.netkeibaUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                    title="netkeiba"
                  >
                    <Image src="/netkeiba.png" alt="netkeiba" width={24} height={24} className="rounded" />
                  </a>
                )}
                {externalLinks.netkeibaBbsUrl && (
                  <a
                    href={externalLinks.netkeibaBbsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center text-blue-600"
                    title="netkeiba BBS"
                  >
                    <MessageCircle className="w-5 h-5" />
                  </a>
                )}
                {/* オッズ表リンク */}
                {jraRaceId && (
                  <Link
                    href={`/odds-race/${jraRaceId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center"
                    title="オッズ表"
                  >
                    <TrendingUp className="w-5 h-5 text-emerald-500" />
                  </Link>
                )}
                {/* 指数表リンク */}
                {idmCompareUrl && (
                  <Link
                    href={idmCompareUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center"
                    title="指数表"
                  >
                    <BarChart3 className="w-5 h-5 text-purple-500" />
                  </Link>
                )}
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
 * このレースの実際のペース傾向バッジ（確定レース用）
 */
function RaceTrendBadge({ trendV2, lap33 }: { trendV2: string; lap33?: number | null }) {
  const trend = trendV2 as RaceTrendV2Type;
  const label = RACE_TREND_V2_LABELS[trend];
  const colorClass = RACE_TREND_V2_COLORS[trend];
  if (!label) return null;

  const lap33Text = lap33 != null ? `33ラップ: ${lap33 > 0 ? '+' : ''}${lap33.toFixed(1)} (${getLap33Interpretation(lap33)})` : '';

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${colorClass}`}
      title={`レース実績: ${label}${lap33Text ? `\n${lap33Text}` : ''}`}
    >
      <Activity className="w-3 h-3" />
      <span>{label}</span>
      {lap33 != null && (
        <span className="text-[10px] opacity-70">({lap33 > 0 ? '+' : ''}{lap33.toFixed(1)})</span>
      )}
    </span>
  );
}

/**
 * 馬場状態バッジ（公式データ優先）
 * JRA-VAN track_condition があればそれを使用、なければ含水率から推定
 */
function TrackConditionBadge({ raceInfo, babaInfo, trackBias }: {
  raceInfo: RaceInfo;
  babaInfo?: BabaCondition | null;
  trackBias?: TrackBias | null;
}) {
  const surface = babaInfo?.surface ?? (raceInfo.track?.startsWith('ダ') ? 'dirt' : 'turf');
  const surfaceInfo = getSurfaceInfo(surface);

  // 馬場状態: JRA-VAN公式 > 含水率推定
  const condition = raceInfo.track_condition || babaInfo?.moistureConditionLabel || '';
  const isOfficial = !!raceInfo.track_condition;

  // 天候: JRA-VAN > JRDB
  const weather = raceInfo.weather || (trackBias ? getWeatherFromCode(trackBias.weatherCode) : '');
  const weatherIcon = getWeatherIcon(weather);

  // 色分け
  const colors = condition
    ? getConditionBadgeClassBySurface(condition, surface)
    : {
        bgClass: 'bg-gray-100 dark:bg-gray-800',
        textClass: 'text-gray-700 dark:text-gray-300',
        borderClass: 'border-gray-300 dark:border-gray-600',
      };

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-md border ${colors.bgClass} ${colors.textClass} ${colors.borderClass}`}
      title={isOfficial ? 'JRA-VAN 公式馬場状態' : '含水率に基づく推定（参考値）'}
    >
      <span className={surfaceInfo.colorClass}>{surfaceInfo.label}</span>
      {condition && <span>{condition}</span>}
      {weatherIcon && <span>{weatherIcon}</span>}
    </span>
  );
}

/**
 * 含水率・クッション値の詳細テキスト
 */
function MoistureDetail({ babaInfo }: { babaInfo: BabaCondition }) {
  const parts: string[] = [];

  // クッション値（芝のみ）
  if (babaInfo.surface === 'turf' && babaInfo.cushion != null) {
    parts.push(`C:${babaInfo.cushion.toFixed(1)}${babaInfo.cushionLabel ? `(${babaInfo.cushionLabel})` : ''}`);
  }

  // 含水率
  const moistureG = babaInfo.moistureG != null ? `G前${babaInfo.moistureG.toFixed(1)}%` : null;
  const moisture4 = babaInfo.moisture4 != null ? `4C${babaInfo.moisture4.toFixed(1)}%` : null;
  const moisture = [moistureG, moisture4].filter(Boolean).join('/');
  if (moisture) {
    parts.push(`水:${moisture}`);
  }

  if (parts.length === 0) return null;

  return (
    <span
      className="text-[11px] text-muted-foreground"
      title="クッション値・含水率（JRA発表）"
    >
      {parts.join(' ')}
    </span>
  );
}

/**
 * トラックバイアスバッジ（JRDB KAA 確定データ）
 */
function TrackBiasBadge({ trackBias, surface }: { trackBias: TrackBias; surface: 'turf' | 'dirt' }) {
  const sa = surface === 'turf' ? trackBias.turfSa : trackBias.dirtSa;
  const bias = getBiasLabel(sa);

  const colorMap = {
    inner: 'bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-700',
    outer: 'bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-400 dark:border-red-700',
    flat: 'bg-gray-100 text-gray-600 border-gray-300 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600',
  };

  // 内/中/外の詳細
  const inner = surface === 'turf' ? trackBias.turfInner : trackBias.dirtInner;
  const middle = surface === 'turf' ? trackBias.turfMiddle : trackBias.dirtMiddle;
  const outer = surface === 'turf' ? trackBias.turfOuter : trackBias.dirtOuter;
  const pathLabel = (v: number) => v === 1 ? '○' : v === 3 ? '×' : '—';

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${colorMap[bias.level]}`}
      title={`JRDB馬場バイアス（差値: ${sa}）\n内:${pathLabel(inner)} 中:${pathLabel(middle)} 外:${pathLabel(outer)}`}
    >
      <span>{bias.label}</span>
      <span className="text-[10px] opacity-70">({sa})</span>
    </span>
  );
}
