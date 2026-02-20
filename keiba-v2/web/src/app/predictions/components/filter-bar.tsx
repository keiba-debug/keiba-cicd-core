interface FilterBarProps {
  venues: string[];
  venueFilter: string;
  setVenueFilter: (v: string) => void;
  raceNumbers: number[];
  raceNumFilter: number;
  setRaceNumFilter: (n: number) => void;
  trackFilter: string;
  setTrackFilter: (v: string) => void;
  minGap: number;
  setMinGap: (g: number) => void;
  minEv: number;
  setMinEv: (v: number) => void;
  filteredCount: number;
  totalCount: number;
}

export function FilterBar({
  venues, venueFilter, setVenueFilter,
  raceNumbers, raceNumFilter, setRaceNumFilter,
  trackFilter, setTrackFilter,
  minGap, setMinGap,
  minEv, setMinEv,
  filteredCount, totalCount,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg bg-gray-50 dark:bg-gray-900/50 p-3 mb-6">
      {/* 場所 */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">場所:</span>
        {['all', ...venues].map(v => (
          <button
            key={v}
            onClick={() => setVenueFilter(v)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              venueFilter === v
                ? 'bg-blue-600 text-white shadow-sm'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            {v === 'all' ? '全て' : v}
          </button>
        ))}
      </div>

      {/* レース番号 */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">R:</span>
        <button
          onClick={() => setRaceNumFilter(0)}
          className={`px-2.5 py-1 text-xs rounded transition-colors ${
            raceNumFilter === 0
              ? 'bg-purple-600 text-white shadow-sm'
              : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
          }`}
        >
          全て
        </button>
        {raceNumbers.map(n => (
          <button
            key={n}
            onClick={() => setRaceNumFilter(n)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              raceNumFilter === n
                ? 'bg-purple-600 text-white shadow-sm'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            {n}
          </button>
        ))}
      </div>

      {/* 芝/ダート */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">馬場:</span>
        {[
          { v: 'all', l: '全て', cls: 'bg-gray-600' },
          { v: 'turf', l: '芝', cls: 'bg-green-600' },
          { v: 'dirt', l: 'ダート', cls: 'bg-amber-600' },
        ].map(({ v, l, cls }) => (
          <button
            key={v}
            onClick={() => setTrackFilter(v)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              trackFilter === v
                ? `${cls} text-white shadow-sm`
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {/* Gap */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">Gap:</span>
        {[3, 4, 5].map(g => (
          <button
            key={g}
            onClick={() => setMinGap(g)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              minGap === g
                ? 'bg-orange-600 text-white shadow-sm'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            &ge;{g}
          </button>
        ))}
      </div>

      {/* EV */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">EV:</span>
        {[
          { v: 0, l: '全て' },
          { v: 0.8, l: '\u22650.8' },
          { v: 1.0, l: '\u22651.0' },
          { v: 1.2, l: '\u22651.2' },
        ].map(({ v, l }) => (
          <button
            key={v}
            onClick={() => setMinEv(v)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              minEv === v
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {/* 件数表示 */}
      <span className="text-xs text-muted-foreground ml-auto">
        {filteredCount !== totalCount
          ? `${filteredCount} / ${totalCount} 件`
          : `${totalCount} 件`}
      </span>
    </div>
  );
}
