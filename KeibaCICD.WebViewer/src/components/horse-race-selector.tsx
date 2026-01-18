'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface PastRace {
  date: string;       // 2025/11/02
  track: string;      // 4東京11
  raceName: string;   // 天皇賞（秋）
  result: string;     // 着順
  distance: string;   // 芝2000
  umaban: string;     // 馬番（出走番号）
}

interface HorseRaceSelectorProps {
  horseId: string;
  horseName: string;
  pastRaces: PastRace[];
}

export function HorseRaceSelector({ horseId, horseName, pastRaces }: HorseRaceSelectorProps) {
  const [selectedRaces, setSelectedRaces] = useState<Set<number>>(new Set());
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Map<number, { found: boolean; raceNumber?: number; error?: string }>>(new Map());

  const toggleRace = (index: number) => {
    setSelectedRaces(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else if (newSet.size < 4) { // 最大4つまで
        newSet.add(index);
      }
      return newSet;
    });
  };

  const searchRaceInfo = async () => {
    if (selectedRaces.size === 0) return;
    
    setIsSearching(true);
    const results = new Map<number, { found: boolean; raceNumber?: number; error?: string }>();
    
    for (const index of selectedRaces) {
      const race = pastRaces[index];
      try {
        // 競馬場名を抽出（4東京11 → 東京）
        const trackMatch = race.track.match(/\d*([^\d]+)\d*/);
        const trackName = trackMatch ? trackMatch[1] : race.track;
        
        const response = await fetch(
          `/api/race-lookup?date=${encodeURIComponent(race.date)}&track=${encodeURIComponent(trackName)}&raceName=${encodeURIComponent(race.raceName)}`
        );
        
        if (response.ok) {
          const data = await response.json();
          if (data.race) {
            results.set(index, { found: true, raceNumber: data.race.raceNumber });
          } else {
            results.set(index, { found: false, error: 'レースが見つかりません' });
          }
        } else {
          results.set(index, { found: false, error: 'レース情報の取得に失敗' });
        }
      } catch {
        results.set(index, { found: false, error: 'エラーが発生しました' });
      }
    }
    
    setSearchResults(results);
    setIsSearching(false);
  };

  const openMultiView = () => {
    // 選択されたレースでマルチビューを開く
    const selectedRaceData = Array.from(selectedRaces).map(index => {
      const race = pastRaces[index];
      const result = searchResults.get(index);
      const trackMatch = race.track.match(/\d*([^\d]+)\d*/);
      const trackName = trackMatch ? trackMatch[1] : race.track;
      
      return {
        date: race.date,
        track: trackName,
        raceNumber: result?.raceNumber || 0,
        raceName: race.raceName,
        umaban: race.umaban,
      };
    }).filter(r => r.raceNumber > 0);
    
    if (selectedRaceData.length === 0) {
      alert('レース番号が取得できたレースがありません。先に「レース情報を検索」を実行してください。');
      return;
    }
    
    // クエリパラメータとしてレース情報を渡す
    const params = new URLSearchParams();
    params.set('horseId', horseId);
    params.set('horse', horseName);
    params.set('races', JSON.stringify(selectedRaceData));
    
    window.open(`/multi-view?${params.toString()}`, '_blank');
  };

  if (pastRaces.length === 0) {
    return null;
  }

  return (
    <div className="border rounded-lg p-4 my-6 bg-card">
      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
        📺 過去レース映像比較
        <Badge variant="secondary">{selectedRaces.size}/4 選択中</Badge>
      </h3>
      
      <p className="text-sm text-muted-foreground mb-4">
        過去レースを選択して、パドック・レース映像を比較できます（最大4レース）
      </p>

      <div className="space-y-2 max-h-64 overflow-y-auto mb-4">
        {pastRaces.slice(0, 20).map((race, index) => {
          const result = searchResults.get(index);
          const isSelected = selectedRaces.has(index);
          
          return (
            <label
              key={index}
              className={`flex items-center gap-3 p-2 rounded cursor-pointer transition-colors
                ${isSelected ? 'bg-primary/10' : 'hover:bg-muted'}`}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => toggleRace(index)}
                disabled={!isSelected && selectedRaces.size >= 4}
                className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <span className="flex-1 text-sm">
                <span className="font-mono">{race.date}</span>
                <span className="mx-2">{race.track}</span>
                <span className="font-medium">{race.raceName}</span>
                <span className="ml-2 text-muted-foreground">{race.distance}</span>
                {race.umaban && (
                  <span className="ml-2 px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-xs font-bold">
                    {race.umaban}番
                  </span>
                )}
                <span className="ml-2">{race.result}着</span>
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
            </label>
          );
        })}
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={searchRaceInfo}
          disabled={selectedRaces.size === 0 || isSearching}
        >
          {isSearching ? '検索中...' : '🔍 レース情報を検索'}
        </Button>
        <Button
          size="sm"
          onClick={openMultiView}
          disabled={selectedRaces.size === 0 || searchResults.size === 0}
          className="bg-blue-600 hover:bg-blue-700"
        >
          📺 マルチビューで開く
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
