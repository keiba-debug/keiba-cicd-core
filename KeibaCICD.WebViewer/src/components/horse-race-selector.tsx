'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

type VideoType = 'paddock' | 'race' | 'patrol';

const VIDEO_OPTIONS: { type: VideoType; label: string; color: string }[] = [
  { type: 'paddock', label: 'パドック', color: 'text-blue-700' },
  { type: 'race', label: 'レース', color: 'text-red-700' },
  { type: 'patrol', label: 'パトロール', color: 'text-amber-700' },
];

const MAX_SELECTIONS = Number.POSITIVE_INFINITY;

const multiViewWindows = new Map<string, Window | null>();

const formatDistance = (raw: string) => {
  const value = raw.replace(/\s+/g, '');
  if (!value) return '';
  if (value.startsWith('ダート')) return value;
  if (value.startsWith('ダ')) return `ダート${value.slice(1)}`;
  if (value.startsWith('障')) return `障害${value.slice(1)}`;
  return value;
};

interface PastRace {
  date: string;       // 2025/11/02
  track: string;      // 4東京11
  raceName: string;   // 天皇賞（秋）
  raceNumber?: number;
  result: string;     // 着順
  distance: string;   // 芝2000
  umaban?: string;    // 馬番（出走番号）- オプショナル
}

interface HorseRaceSelectorProps {
  horseId: string;
  horseName: string;
  pastRaces: PastRace[];
}

export function HorseRaceSelector({ horseId, horseName, pastRaces }: HorseRaceSelectorProps) {
  const [selectedVideos, setSelectedVideos] = useState<Map<number, Set<VideoType>>>(new Map());
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Map<number, { found: boolean; raceNumber?: number; error?: string }>>(new Map());

  const getSelectedCount = (map: Map<number, Set<VideoType>>) => {
    let count = 0;
    map.forEach((types) => {
      count += types.size;
    });
    return count;
  };

  const toggleVideo = (index: number, videoType: VideoType) => {
    setSelectedVideos((prev) => {
      const next = new Map(prev);
      const current = new Set(next.get(index) ?? []);
      const isChecked = current.has(videoType);

      if (isChecked) {
        current.delete(videoType);
      } else {
        if (getSelectedCount(prev) >= MAX_SELECTIONS) return prev;
        current.add(videoType);
      }

      if (current.size > 0) {
        next.set(index, current);
      } else {
        next.delete(index);
      }
      return next;
    });
  };

  const clearSelection = () => {
    setSelectedVideos(new Map());
    setSearchResults(new Map());
  };

  const fetchRaceResults = async () => {
    if (selectedVideos.size === 0) return new Map<number, { found: boolean; raceNumber?: number; error?: string }>();
    
    setIsSearching(true);
    const results = new Map<number, { found: boolean; raceNumber?: number; error?: string }>();
    
    for (const index of selectedVideos.keys()) {
      const race = pastRaces[index];
      try {
        // 競馬場名を抽出（4東京11 → 東京）
        const trackMatch = race.track.match(/\d*([^\d]+)\d*/);
        const trackName = trackMatch ? trackMatch[1] : race.track;
        
        const distanceParam = race.distance
          ? `&distance=${encodeURIComponent(race.distance)}`
          : '';
        const url = race.raceNumber
          ? `/api/race-lookup?date=${encodeURIComponent(race.date)}&track=${encodeURIComponent(trackName)}&raceNumber=${race.raceNumber}${distanceParam}`
          : `/api/race-lookup?date=${encodeURIComponent(race.date)}&track=${encodeURIComponent(trackName)}&raceName=${encodeURIComponent(race.raceName)}${distanceParam}`;
        const response = await fetch(url);
        
        const data = await response.json();
        if (response.ok) {
          if (data.race) {
            results.set(index, { found: true, raceNumber: data.race.raceNumber });
          } else {
            results.set(index, { found: false, error: 'レースが見つかりません' });
          }
        } else {
          results.set(index, { found: false, error: data?.error || 'レース情報の取得に失敗' });
        }
      } catch {
        results.set(index, { found: false, error: 'エラーが発生しました' });
      }
    }
    
    setSearchResults(results);
    setIsSearching(false);
    return results;
  };

  const openMultiView = async () => {
    // 選択された映像でマルチビューを開く（レース単位で複数映像可）
    const effectiveResults =
      searchResults.size > 0 ? searchResults : await fetchRaceResults();
    const selectedVideoData: Array<{
      date: string;
      track: string;
      raceNumber: number;
      raceName: string;
      umaban?: string;
      videoType: VideoType;
    }> = [];

    selectedVideos.forEach((types, index) => {
      const race = pastRaces[index];
      const result = effectiveResults.get(index);
      const trackMatch = race.track.match(/\d*([^\d]+)\d*/);
      const trackName = trackMatch ? trackMatch[1] : race.track;
      const raceNumber = result?.raceNumber || 0;

      if (raceNumber <= 0) return;

      types.forEach((videoType) => {
        selectedVideoData.push({
          date: race.date,
          track: trackName,
          raceNumber,
          raceName: race.raceName,
          umaban: race.umaban,
          videoType,
        });
      });
    });
    
    if (selectedVideoData.length === 0) {
      alert('レース番号が取得できた映像がありません。先に「レース情報を検索」を実行してください。');
      return;
    }
    
    const windowKey = horseId ? `horse:${horseId}` : 'default';
    const windowName = horseId ? `keiba-multi-view-${horseId}` : 'keiba-multi-view';
    const currentWindow = multiViewWindows.get(windowKey);
    const targetWindow = currentWindow && !currentWindow.closed ? currentWindow : null;
    if (targetWindow) {
      selectedVideoData.forEach((race, idx) => {
        const add = `${Date.now()}-${idx}`;
        targetWindow.postMessage(
          {
            type: 'keiba:multi-view:add',
            payload: {
              add,
              date: race.date,
              track: race.track,
              raceNumber: String(race.raceNumber),
              videoType: race.videoType,
              raceName: race.raceName,
              umaban: race.umaban,
            },
          },
          window.location.origin
        );
      });
      targetWindow.focus();
      return;
    }

    // クエリパラメータとしてレース情報を渡す（初回起動）
    const params = new URLSearchParams();
    params.set('horseId', horseId);
    params.set('horse', horseName);
    params.set('races', JSON.stringify(selectedVideoData));
    const opened = window.open(`/multi-view?${params.toString()}`, windowName);
    if (opened) {
      multiViewWindows.set(windowKey, opened);
    }
  };

  if (pastRaces.length === 0) {
    return null;
  }

  const selectedCount = getSelectedCount(selectedVideos);

  return (
    <div className="border rounded-lg p-4 my-6 bg-card">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          📺 過去レース映像比較
          <Badge variant="secondary">{selectedCount} 選択中</Badge>
        </h3>
        <Button
          size="sm"
          variant="outline"
          onClick={clearSelection}
          disabled={selectedCount === 0 || isSearching}
          className="h-7 px-2 text-xs"
        >
          解除
        </Button>
      </div>
      
      <p className="text-sm text-muted-foreground mb-4">
        過去レースの映像を選択して、マルチビューに一括追加できます
      </p>

      <div className="space-y-2 max-h-64 overflow-y-auto mb-4">
        {pastRaces.slice(0, 20).map((race, index) => {
          const result = searchResults.get(index);
          const selectedTypes = selectedVideos.get(index) ?? new Set<VideoType>();
          
          return (
            <div
              key={index}
              className={`flex items-center gap-3 p-2 rounded transition-colors
                ${selectedTypes.size > 0 ? 'bg-primary/10' : 'hover:bg-muted'}`}
            >
              <div className="flex items-center gap-2">
                {VIDEO_OPTIONS.map((option) => {
                  const isChecked = selectedTypes.has(option.type);
                  return (
                    <label key={option.type} className="flex items-center gap-1 text-xs">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleVideo(index, option.type)}
                        disabled={false}
                        className="w-3.5 h-3.5 rounded border-gray-300 text-primary focus:ring-primary"
                      />
                      <span className={option.color}>{option.label}</span>
                    </label>
                  );
                })}
              </div>
              <span className="flex-1 text-sm">
                <span className="font-mono">{race.date}</span>
                <span className="mx-2">/</span>
                <span>{race.track}</span>
                <span className="mx-2">/</span>
                <span className="font-medium">{race.raceName}</span>
                {race.distance && (
                  <>
                    <span className="mx-2">/</span>
                    <span className="text-muted-foreground">
                      {formatDistance(race.distance)}
                    </span>
                  </>
                )}
                {race.umaban && (
                  <span className="ml-2 px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-xs font-bold">
                    馬番{race.umaban}
                  </span>
                )}
                {race.result && <span className="ml-2">着順{race.result}</span>}
              </span>
              {result && (
                result.found ? (
                  <Badge variant="outline" className="bg-green-50 text-green-700">
                    {result.raceNumber}R ✓
                  </Badge>
                ) : (
                  <Badge variant="outline" className="bg-red-50 text-red-700">
                    {result.error}
                  </Badge>
                )
              )}
            </div>
          );
        })}
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={fetchRaceResults}
          disabled={selectedCount === 0 || isSearching}
        >
          {isSearching ? '検索中...' : '🔍 レース情報を検索'}
        </Button>
        <Button
          size="sm"
          onClick={openMultiView}
          disabled={selectedCount === 0 || isSearching}
          className="bg-blue-600 hover:bg-blue-700"
        >
          📺 マルチビューに追加
        </Button>
      </div>

      <p className="text-xs text-muted-foreground mt-2">
        ※ 2024年1月以降のJRA主催レースのみ対応
      </p>
    </div>
  );
}

/**
 * 馬プロファイルMDのHTMLから過去成績を抽出
 */
export function extractPastRacesFromHtml(htmlContent: string): PastRace[] {
  const races: PastRace[] = [];
  
  // 完全成績テーブルの行を抽出
  // | 日付 | 競馬場 | レース | 着順 | ... | 距離 | ...
  const tableRowRegex = /\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*(\d{4}\/\d{1,2}\/\d{1,2})\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|/g;
  
  // HTMLからテキストを抽出するためのDOM操作はサーバーサイドでは難しいため、
  // 正規表現でTDを探す
  const tdRowRegex = /<tr[^>]*>(?:<t[dh][^>]*>([^<]*)<\/t[dh]>)+<\/tr>/gi;
  
  let match;
  while ((match = tdRowRegex.exec(htmlContent)) !== null) {
    const row = match[0];
    const cells: string[] = [];
    const cellRegex = /<t[dh][^>]*>([^<]*)<\/t[dh]>/gi;
    let cellMatch;
    while ((cellMatch = cellRegex.exec(row)) !== null) {
      cells.push(cellMatch[1].trim());
    }
    
    // 完全成績テーブル: コメント | 本誌 | 日付 | 競馬場 | レース | ...
    // 日付がYYYY/MM/DD形式かチェック
    const dateIndex = cells.findIndex(c => /^\d{4}\/\d{1,2}\/\d{1,2}$/.test(c));
    if (dateIndex >= 0 && cells.length > dateIndex + 4) {
      const date = cells[dateIndex];
      const track = cells[dateIndex + 1];
      const raceName = cells[dateIndex + 2];
      
      // 距離を探す（芝XXXX or ダートXXXX形式）
      const distanceCell = cells.find(c => /^[芝ダ].+\d+/.test(c));
      const distance = distanceCell || '';
      
      // 着順を探す（数字のみ）
      const resultIndex = cells.findIndex((c, i) => i > dateIndex + 3 && /^\d+$/.test(c));
      const result = resultIndex >= 0 ? cells[resultIndex] : '';
      
      if (date && track && raceName) {
        races.push({ date, track, raceName, result, distance });
      }
    }
  }
  
  return races;
}
