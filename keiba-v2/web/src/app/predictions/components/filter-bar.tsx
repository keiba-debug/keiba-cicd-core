interface FilterBarProps {
  venues: string[];
  venueFilter: string;
  setVenueFilter: (v: string) => void;
  raceNumbers: number[];
  raceNumFilter: number | string;
  setRaceNumFilter: (n: number | string) => void;
  trackFilter: string;
  setTrackFilter: (v: string) => void;
  minEv: number;
  setMinEv: (v: number) => void;
  minArd: number | null;
  setMinArd: (m: number | null) => void;
  betOnly: boolean;
  setBetOnly: (b: boolean) => void;
  noveltyFilter: 'all' | 'safe' | 'novel';
  setNoveltyFilter: (v: 'all' | 'safe' | 'novel') => void;
  filteredCount: number;
  totalCount: number;
}

export function FilterBar({
  venues, venueFilter, setVenueFilter,
  raceNumbers, raceNumFilter, setRaceNumFilter,
  trackFilter, setTrackFilter,
  minEv, setMinEv,
  minArd, setMinArd,
  betOnly, setBetOnly,
  noveltyFilter, setNoveltyFilter,
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

      {/* レース番号（レンジ + 個別） */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">R:</span>
        {([
          { v: 0 as number | string, l: '全て' },
          { v: '1-4', l: '1-4' },
          { v: '5-8', l: '5-8' },
          { v: '9-12', l: '9-12' },
        ] as const).map(({ v, l }) => (
          <button
            key={String(v)}
            onClick={() => setRaceNumFilter(v)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              raceNumFilter === v
                ? 'bg-purple-600 text-white shadow-sm'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            {l}
          </button>
        ))}
        <span className="text-gray-300 dark:text-gray-600 mx-0.5">|</span>
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

      {/* ARd (AR偏差値) */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1" title="ARd (AR偏差値) — レース内相対評価（mean=50, std=10）。50=平均">ARd:</span>
        {[
          { v: null as number | null, l: '全て' },
          { v: 55, l: '\u226555' },
          { v: 50, l: '\u226550' },
          { v: 45, l: '\u226545' },
        ].map(({ v, l }) => (
          <button
            key={String(v)}
            onClick={() => setMinArd(v)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              minArd === v
                ? 'bg-teal-600 text-white shadow-sm'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {/* EV(複勝) */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1" title="複勝EV（Place側のみ有効）">EV(複勝):</span>
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

      {/* bet推奨のみ */}
      <label className="flex items-center gap-1.5 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={betOnly}
          onChange={(e) => setBetOnly(e.target.checked)}
          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
        />
        <span className="text-xs text-muted-foreground">投資対象のみ</span>
      </label>

      {/* 未知数度フィルタ (Session 119) */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">未知数:</span>
        {([
          { v: 'all', label: '全て', cls: 'bg-blue-600' },
          { v: 'safe', label: '低 (≤1)', cls: 'bg-emerald-600' },
          { v: 'novel', label: '高 (≥3)', cls: 'bg-rose-600' },
        ] as const).map((opt) => (
          <button
            key={opt.v}
            onClick={() => setNoveltyFilter(opt.v)}
            title={
              opt.v === 'safe' ? '初芝/初距離/初コース等が少ない安定馬のみ' :
              opt.v === 'novel' ? '未知数フラグが3つ以上立っている馬のみ (人間判断補強用)' :
              '全ての注目馬'
            }
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              noveltyFilter === opt.v
                ? `${opt.cls} text-white shadow-sm`
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 件数表示 */}
      <span className="text-xs text-muted-foreground ml-auto">
        {filteredCount !== totalCount
          ? `${filteredCount} / ${totalCount} 件`
          : `${totalCount} 件`}
        {betOnly && ' (システム投資)'}
      </span>
    </div>
  );
}
