import Link from 'next/link';
import { getAvailableDates, getRacesByDate } from '@/lib/data';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { JraViewerMiniLinks } from '@/components/jra-viewer-mini-links';

// 日付を年月でグループ化
function groupDatesByYearMonth(dates: string[]): Map<string, string[]> {
  const groups = new Map<string, string[]>();
  for (const date of dates) {
    const [year, month] = date.split('-');
    const key = `${year}-${month}`;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(date);
  }
  return groups;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ year?: string; month?: string }>;
}) {
  const params = await searchParams;
  const dates = await getAvailableDates();

  // 年月でグループ化
  const groupedDates = groupDatesByYearMonth(dates);
  const yearMonths = Array.from(groupedDates.keys()).sort().reverse();

  // 現在の年月を取得
  const now = new Date();
  const currentYear = now.getFullYear().toString();
  const currentMonth = (now.getMonth() + 1).toString().padStart(2, '0');

  // データがある年を取得
  const dataYears = [...new Set(yearMonths.map((ym) => ym.split('-')[0]))];

  // 選択された年月を取得（デフォルトは最新データがある年月、またはクエリパラメータ）
  const selectedYear = params.year || dataYears[0] || currentYear;

  // 表示する年のリスト（データがある年 + 選択された年の前後 + 現在年を含む）
  const yearNum = parseInt(selectedYear);
  const adjacentYears = [
    (yearNum - 1).toString(),
    selectedYear,
    (yearNum + 1).toString()
  ];
  const years = [...new Set([...dataYears, ...adjacentYears, currentYear])].sort().reverse();
  const availableMonthsInYear = yearMonths
    .filter((ym) => ym.startsWith(selectedYear))
    .map((ym) => ym.split('-')[1]);
  
  // 月は1-12月全て表示（データの有無に関わらず）
  const allMonths = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
  const selectedMonth = params.month || availableMonthsInYear[0] || currentMonth;
  const selectedYearMonth = `${selectedYear}-${selectedMonth}`;

  // 選択された年月の日付を取得
  const datesInMonth = groupedDates.get(selectedYearMonth) || [];

  // 最新日付のデータを取得
  const latestDate = datesInMonth[0];

  // 前月・次月の計算
  const selectedMonthNum = parseInt(selectedMonth);
  const selectedYearNum = parseInt(selectedYear);
  const prevMonth = selectedMonthNum === 1 
    ? { year: (selectedYearNum - 1).toString(), month: '12' }
    : { year: selectedYear, month: (selectedMonthNum - 1).toString().padStart(2, '0') };
  const nextMonth = selectedMonthNum === 12
    ? { year: (selectedYearNum + 1).toString(), month: '01' }
    : { year: selectedYear, month: (selectedMonthNum + 1).toString().padStart(2, '0') };

  // データがある月かどうかをチェック
  const hasDataInMonth = (year: string, month: string) => {
    return groupedDates.has(`${year}-${month}`);
  };

  return (
    <div className="container py-6">
      <h1 className="text-3xl font-bold mb-6">レース一覧</h1>

      {/* 年月選択 */}
      <div className="flex flex-wrap items-center gap-4 mb-6 p-4 bg-muted/30 rounded-lg border year-month-selector">
        {/* 年選択 */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">年:</span>
          <div className="flex gap-1">
            {years.map((year) => (
              <Link
                key={year}
                href={`/?year=${year}`}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors border ${
                  year === selectedYear
                    ? 'year-month-active'
                    : 'year-month-inactive'
                }`}
              >
                {year}年
              </Link>
            ))}
          </div>
        </div>

        {/* 月選択（前月・次月ナビゲーション付き） */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">月:</span>
          
          {/* 前月ボタン */}
          <Link
            href={`/?year=${prevMonth.year}&month=${prevMonth.month}`}
            className="px-2 py-1 text-sm rounded-md transition-colors border hover:bg-muted"
            title={`${prevMonth.year}年${parseInt(prevMonth.month)}月へ`}
          >
            ◀
          </Link>
          
          <div className="flex flex-wrap gap-1">
            {allMonths.map((month) => {
              const hasData = hasDataInMonth(selectedYear, month);
              return (
                <Link
                  key={month}
                  href={`/?year=${selectedYear}&month=${month}`}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors border ${
                    month === selectedMonth
                      ? 'year-month-active'
                      : hasData
                        ? 'year-month-inactive'
                        : 'year-month-inactive opacity-40'
                  }`}
                >
                  {parseInt(month)}月
                </Link>
              );
            })}
          </div>
          
          {/* 次月ボタン */}
          <Link
            href={`/?year=${nextMonth.year}&month=${nextMonth.month}`}
            className="px-2 py-1 text-sm rounded-md transition-colors border hover:bg-muted"
            title={`${nextMonth.year}年${parseInt(nextMonth.month)}月へ`}
          >
            ▶
          </Link>
        </div>
      </div>

      {/* 日付タブ */}
      {datesInMonth.length > 0 ? (
        <Tabs defaultValue={latestDate} className="w-full">
          <TabsList className="mb-4 flex-wrap h-auto gap-1 bg-muted/50 p-1">
            {datesInMonth.map((date) => {
              const [, month, day] = date.split('-');
              return (
                <TabsTrigger
                  key={date}
                  value={date}
                  className="px-4 py-2 data-[state=active]:bg-background data-[state=active]:shadow-sm"
                >
                  {parseInt(month)}/{parseInt(day)}
                </TabsTrigger>
              );
            })}
          </TabsList>

          {datesInMonth.map((date) => (
            <TabsContent key={date} value={date}>
              <DateRaces date={date} />
            </TabsContent>
          ))}
        </Tabs>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <p>この月にはレースデータがありません</p>
        </div>
      )}

      {dates.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p>レースデータがありません</p>
          <p className="text-sm mt-2">data2フォルダにデータを配置してください</p>
        </div>
      )}
    </div>
  );
}

async function DateRaces({ date }: { date: string }) {
  const data = await getRacesByDate(date);

  if (!data) {
    return <p className="text-muted-foreground">データが見つかりません</p>;
  }


  const netkeibaRaceId = (race: { track: string; raceNumber: number; kai?: number; nichi?: number; date: string }) => {
    if (!race.kai || !race.nichi) return null;
    const trackCodes: Record<string, string> = {
      '札幌': '01',
      '函館': '02',
      '福島': '03',
      '新潟': '04',
      '東京': '05',
      '中山': '06',
      '中京': '07',
      '京都': '08',
      '阪神': '09',
      '小倉': '10',
    };
    const code = trackCodes[race.track];
    if (!code) return null;
    const [year] = race.date.split('-');
    const raceNo = String(race.raceNumber).padStart(2, '0');
    const kai = String(race.kai).padStart(2, '0');
    const nichi = String(race.nichi).padStart(2, '0');
    return `${year}${code}${kai}${nichi}${raceNo}`;
  };

  const formatCondition = (distance?: string) => {
    if (!distance) return '';
    const normalized = distance.replace('：', ':').replace('・', ' ').trim();
    const withSpace = normalized.replace(':', ' ');
    return withSpace.replace(/m/gi, 'M').replace(/\s+/g, ' ');
  };

  const courseBadgeClass = (distance?: string) => {
    if (!distance) return 'border-muted-foreground/30 text-muted-foreground';
    if (distance.startsWith('芝')) return 'border-emerald-200 text-emerald-700 bg-emerald-50';
    if (distance.startsWith('ダ')) return 'border-amber-200 text-amber-700 bg-amber-50';
    if (distance.startsWith('障')) return 'border-violet-200 text-violet-700 bg-violet-50';
    return 'border-muted-foreground/30 text-muted-foreground';
  };

  // 開催情報を取得（例: "1回中山9日目"）
  const getKaisaiLabel = (track: string, races: typeof data.tracks[0]['races']) => {
    const firstRace = races[0];
    if (firstRace?.kai && firstRace?.nichi) {
      return `${firstRace.kai}回${track}${firstRace.nichi}日目`;
    }
    return `${track}`;
  };

  return (
    <div className="space-y-4">
      {/* 日付ヘッダー */}
      <h2 className="text-lg font-bold text-center py-2 bg-muted/50 rounded">
        {data.displayDate}
      </h2>

      {/* 競馬場ごとのグリッド（競馬ブック風テーブル形式） */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.tracks.map((trackGroup) => (
          <Card key={trackGroup.track} className="overflow-hidden shadow-sm">
            {/* 開催ヘッダー（競馬ブック風：青背景） */}
            <CardHeader className="py-2 px-3 bg-blue-700 text-white border-b-0">
              <CardTitle className="text-sm font-bold text-center">
                {getKaisaiLabel(trackGroup.track, trackGroup.races)}
              </CardTitle>
            </CardHeader>
            
            <CardContent className="p-0">
              <div className="divide-y divide-muted/30">
                {trackGroup.races.map((race) => {
                  return (
                    <div
                      key={race.id}
                      className="grid grid-cols-[50px_1fr_auto] gap-2 px-2 py-2 hover:bg-amber-50 transition-colors group items-center text-sm"
                    >
                      {/* レース番号 + 発走時刻（JRAビュアー風） */}
                      <Link
                        href={`/races/${date}/${trackGroup.track}/${race.id}`}
                        className="flex flex-col items-center"
                      >
                        <span className="font-bold text-blue-700 hover:text-blue-900 text-base">
                          {race.raceNumber}R
                        </span>
                        <span className="text-[11px] text-muted-foreground">
                          {race.startTime || '--:--'}
                        </span>
                      </Link>

                      {/* レース名 + コース + クラス */}
                      <Link
                        href={`/races/${date}/${trackGroup.track}/${race.id}`}
                        className="flex flex-col min-w-0"
                      >
                        <span className="font-medium truncate text-sm" title={race.raceName}>
                          {race.raceName}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-medium ${race.distance?.startsWith('芝') ? 'text-emerald-600' : race.distance?.startsWith('ダ') ? 'text-amber-700' : race.distance?.startsWith('障') ? 'text-violet-600' : 'text-muted-foreground'}`}>
                            {formatCondition(race.distance)}
                          </span>
                          {race.className && (
                            <span className="text-[10px] text-muted-foreground">
                              {race.className}
                            </span>
                          )}
                        </div>
                      </Link>

                      {/* 外部リンク + JRAビュアーリンク */}
                      <div className="flex items-center gap-1">
                        <a
                          href={`https://p.keibabook.co.jp/cyuou/syutuba/${race.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="w-5 h-5 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                          title="競馬ブック"
                        >
                          <img src="/keibabook.ico" alt="競馬ブック" className="w-4 h-4 object-contain" />
                        </a>
                        {netkeibaRaceId(race) && (
                          <>
                            <a
                              href={`https://race.netkeiba.com/race/shutuba.html?race_id=${netkeibaRaceId(race)}&rf=race_submenu`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="w-5 h-5 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                              title="netkeiba"
                            >
                              <img src="/netkeiba.png" alt="netkeiba" className="w-4 h-4 object-contain" />
                            </a>
                            <a
                              href={`https://race.netkeiba.com/race/bbs.html?race_id=${netkeibaRaceId(race)}&rf=race_submenu`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="w-5 h-5 text-sm rounded hover:opacity-80 transition-opacity flex items-center justify-center"
                              title="netkeiba BBS"
                            >
                              💬
                            </a>
                          </>
                        )}
                        <JraViewerMiniLinks
                          date={date}
                          track={trackGroup.track}
                          raceNumber={race.raceNumber}
                          raceName={race.raceName}
                          kai={race.kai}
                          nichi={race.nichi}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
