'use client';

/**
 * レースナビゲーションバー
 * 競馬場タブ × レース番号タブ × 前後レースリンク
 *
 * /races-v2/[date]/[track]/[id]/page.tsx の navigation 部分を再利用化したもの。
 * クライアント側で /api/races/navigation を叩いて取得する。
 *
 * @param buildHref - (raceId, track) => 遷移先 URL を返す関数。
 *                    省略時は /odds-race/{raceId} （現在の主用途）。
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface NavigationResponse {
  tracks: { name: string; firstRaceId: string; raceByNumber: Record<number, string> }[];
  races: { raceNumber: number; raceId: string; raceName: string; startTime: string }[];
  allRacesByTime: { track: string; raceNumber: number; raceId: string; startTime: string }[];
  prevRace: { track: string; raceId: string } | null;
  nextRace: { track: string; raceId: string } | null;
}

interface RaceNavBarProps {
  /** YYYY-MM-DD */
  date: string;
  /** 現在の競馬場名（日本語） */
  track: string;
  /** 現在のレースID(16桁) */
  raceId: string;
  /** 現在のレース番号 (1-12) */
  raceNumber: number;
  /** 遷移先URLビルダー。default: (rid)=>`/odds-race/${rid}` */
  buildHref?: (raceId: string, track: string) => string;
}

const getTrackBgClass = (trackName: string): string => {
  const map: Record<string, string> = {
    札幌: 'bg-blue-500',
    函館: 'bg-cyan-500',
    福島: 'bg-orange-500',
    新潟: 'bg-pink-500',
    東京: 'bg-emerald-500',
    中山: 'bg-amber-500',
    中京: 'bg-violet-500',
    京都: 'bg-rose-500',
    阪神: 'bg-indigo-500',
    小倉: 'bg-teal-500',
  };
  return map[trackName] || 'bg-primary';
};

const defaultBuildHref = (rid: string): string => `/odds-race/${rid}`;

export function RaceNavBar({ date, track, raceId, raceNumber, buildHref = defaultBuildHref }: RaceNavBarProps) {
  const [nav, setNav] = useState<NavigationResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(
      `/api/races/navigation?date=${encodeURIComponent(date)}&track=${encodeURIComponent(track)}&raceNumber=${raceNumber}`,
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((data: NavigationResponse | null) => {
        if (!cancelled) setNav(data);
      })
      .catch(() => {
        if (!cancelled) setNav(null);
      });
    return () => {
      cancelled = true;
    };
  }, [date, track, raceNumber]);

  // 競馬場切り替え時に同じレース番号を維持
  const getTrackRaceId = (targetTrack: string, targetRaceNumber: number): string => {
    if (!nav) return '';
    const trackInfo = nav.tracks.find((t) => t.name === targetTrack);
    if (!trackInfo) return '';

    const byNumber = trackInfo.raceByNumber?.[targetRaceNumber];
    if (byNumber) return byNumber;

    const raceByNumber = trackInfo.raceByNumber || {};
    const availableNumbers = Object.keys(raceByNumber)
      .map(Number)
      .filter((n) => !Number.isNaN(n));
    if (availableNumbers.length > 0) {
      availableNumbers.sort((a, b) => a - b);
      const closest = availableNumbers.reduce((prev, curr) =>
        Math.abs(curr - targetRaceNumber) < Math.abs(prev - targetRaceNumber) ? curr : prev,
      );
      return raceByNumber[closest] || trackInfo.firstRaceId;
    }
    return trackInfo.firstRaceId;
  };

  if (!nav) {
    return (
      <div className="mb-4 p-3 bg-card rounded-xl border shadow-sm">
        <div className="h-9 animate-pulse bg-muted rounded" />
      </div>
    );
  }

  return (
    <div className="mb-4 p-3 bg-card rounded-xl border shadow-sm">
      <div className="flex items-center gap-3 flex-wrap">
        {/* 前のレース */}
        {nav.prevRace ? (
          <Link
            href={buildHref(nav.prevRace.raceId, nav.prevRace.track)}
            className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 active:bg-gray-300 transition-all duration-150 flex items-center justify-center shadow-sm hover:shadow"
            title={`前のレース (${nav.prevRace.track})`}
          >
            <ChevronLeft className="w-5 h-5 text-gray-600" />
          </Link>
        ) : (
          <span className="w-9 h-9 rounded-full bg-gray-50 text-gray-300 flex items-center justify-center cursor-not-allowed">
            <ChevronLeft className="w-5 h-5" />
          </span>
        )}

        {/* 競馬場タブ */}
        <div className="flex gap-1.5 bg-gray-100 p-1 rounded-lg">
          {nav.tracks.map((t) => {
            const isActive = t.name === track;
            const targetRaceId = getTrackRaceId(t.name, raceNumber);
            return (
              <Link
                key={t.name}
                href={buildHref(targetRaceId, t.name)}
                className={`px-4 py-2 text-sm font-bold rounded-md transition-all duration-200 ${
                  isActive
                    ? `${getTrackBgClass(t.name)} text-white shadow-md scale-105`
                    : 'bg-white hover:bg-gray-50 text-gray-600 hover:text-gray-900 shadow-sm hover:shadow'
                }`}
              >
                {t.name}
              </Link>
            );
          })}
        </div>

        {/* 区切り線 */}
        <div className="w-px h-8 bg-gray-200" />

        {/* レース番号タブ */}
        <div className="flex gap-1 flex-wrap bg-gray-50 p-1.5 rounded-lg">
          {nav.races.map((r) => {
            const isActive = r.raceId === raceId;
            return (
              <Link
                key={r.raceId}
                href={buildHref(r.raceId, track)}
                className={`w-8 h-8 text-xs font-bold rounded-md transition-all duration-150 flex items-center justify-center ${
                  isActive
                    ? 'bg-gray-800 text-white shadow-md scale-110'
                    : 'bg-white hover:bg-gray-100 text-gray-600 hover:text-gray-900 shadow-sm hover:shadow'
                }`}
                title={`${r.raceName} (${r.startTime})`}
              >
                {r.raceNumber}
              </Link>
            );
          })}
        </div>

        {/* 次のレース */}
        {nav.nextRace ? (
          <Link
            href={buildHref(nav.nextRace.raceId, nav.nextRace.track)}
            className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 active:bg-gray-300 transition-all duration-150 flex items-center justify-center ml-auto shadow-sm hover:shadow"
            title={`次のレース (${nav.nextRace.track})`}
          >
            <ChevronRight className="w-5 h-5 text-gray-600" />
          </Link>
        ) : (
          <span className="w-9 h-9 rounded-full bg-gray-50 text-gray-300 flex items-center justify-center cursor-not-allowed ml-auto">
            <ChevronRight className="w-5 h-5" />
          </span>
        )}
      </div>
    </div>
  );
}
