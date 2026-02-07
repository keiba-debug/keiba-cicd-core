/**
 * JRAレーシングビュアーのURL生成
 * パドック・レース映像へのリンクを生成
 */

// 競馬場コード（JRAビュアー形式 - 1桁）
const TRACK_CODES: Record<string, number> = {
  '札幌': 1,
  '函館': 2,
  '福島': 3,
  '新潟': 4,
  '東京': 5,
  '中山': 6,
  '中京': 7,
  '京都': 8,
  '阪神': 9,
  '小倉': 10, // 小倉は10 -> 16進で"a"
};

/**
 * レース番号を16進数に変換
 * 1-9 → "1"-"9", 10 → "a", 11 → "b", 12 → "c"
 */
function raceNumberToHex(raceNumber: number): string {
  return raceNumber.toString(16);
}

interface JraViewerParams {
  year: number;        // 年（例: 2026）
  month: number;       // 月（例: 1）
  day: number;         // 日（例: 18）
  track: string;       // 競馬場名（例: "中山"）
  kai: number;         // 回次（例: 1）
  nichi: number;       // 日次（例: 7）
  raceNumber: number;  // レース番号（例: 1）
}

/**
 * JRAレーシングビュアーのパドック映像URLを生成
 * 
 * @example
 * // 2026年1月18日 1回中山7日 1R
 * generatePaddockUrl({
 *   year: 2026, month: 1, day: 18,
 *   track: '中山', kai: 1, nichi: 7, raceNumber: 1
 * })
 * // => "https://regist.prc.jp/api/windowopen.aspx?target=race%2f2026%2f20260118%2f266171_p&quality=4"
 */
export function generatePaddockUrl(params: JraViewerParams): string | null {
  const trackCode = TRACK_CODES[params.track];
  if (trackCode === undefined) {
    console.warn(`Unknown track: ${params.track}`);
    return null;
  }
  const trackCodeHex = trackCode.toString(16);

  // 年下2桁
  const yearShort = params.year % 100;
  
  // 日付（YYYYMMDD形式）
  const dateStr = `${params.year}${String(params.month).padStart(2, '0')}${String(params.day).padStart(2, '0')}`;
  
  // レースコード生成
  // JRAビュアー形式: 年下2桁 + 場コード(1桁) + 回次(1桁) + 日次(16進数) + レース番号(16進数)
  // 例: 2026年1回中山7日目1R = 26 + 6 + 1 + 7 + 1 = 266171
  // 例: 2025年4回東京10日目3R = 25 + 5 + 4 + a + 3 = 2554a3
  const raceCode = `${yearShort}${trackCodeHex}${params.kai}${params.nichi.toString(16)}${raceNumberToHex(params.raceNumber)}`;
  
  // URL生成（パドック映像）- エンコードなし
  const target = `race/${params.year}/${dateStr}/${raceCode}_p`;
  
  return `https://regist.prc.jp/api/windowopen.aspx?target=${target}&quality=4`;
}

/**
 * JRAレーシングビュアーのレース映像URLを生成
 * レース映像はサフィックスなし
 */
export function generateRaceUrl(params: JraViewerParams): string | null {
  const trackCode = TRACK_CODES[params.track];
  if (trackCode === undefined) return null;
  const trackCodeHex = trackCode.toString(16);

  // 年下2桁
  const yearShort = params.year % 100;
  const dateStr = `${params.year}${String(params.month).padStart(2, '0')}${String(params.day).padStart(2, '0')}`;
  
  // JRAビュアー形式: 年下2桁 + 場コード(1桁) + 回次(1桁) + 日次(16進数) + レース番号(16進数)
  const raceCode = `${yearShort}${trackCodeHex}${params.kai}${params.nichi.toString(16)}${raceNumberToHex(params.raceNumber)}`;
  
  // レース映像はサフィックスなし - エンコードなし
  const target = `race/${params.year}/${dateStr}/${raceCode}`;
  
  return `https://regist.prc.jp/api/windowopen.aspx?target=${target}&quality=4`;
}

/**
 * JRAレーシングビュアーのパトロール映像URLを生成
 */
export function generatePatrolUrl(params: JraViewerParams): string | null {
  const raceUrl = generateRaceUrl(params);
  if (!raceUrl) return null;
  
  // レースURLに _a を追加（パトロール映像）
  return raceUrl.replace(/(&quality=)/, '_a$1');
}

/**
 * 開催キー名（例: "1回中山7日目"）から回次・日次・競馬場を抽出
 */
export function parseKaisaiKey(kaisaiKey: string): { kai: number; nichi: number; track: string } | null {
  // 形式: "X回YYY Z日目"
  const match = kaisaiKey.match(/^(\d+)回(.+?)(\d+)日目?$/);
  if (!match) return null;
  
  return {
    kai: parseInt(match[1], 10),
    track: match[2],
    nichi: parseInt(match[3], 10),
  };
}

/**
 * race_info.jsonのデータからレースの開催情報を取得
 */
export function getKaisaiInfoFromRaceInfo(
  kaisaiData: Record<string, Array<{ race_id?: string; raceId?: string; race_no?: string }>>,
  raceId: string
): { kai: number; nichi: number; track: string } | null {
  // 1) race_id / raceId 完全一致
  for (const [kaisaiKey, races] of Object.entries(kaisaiData)) {
    const found = races.find(
      (r) => r.race_id === raceId || (r as { raceId?: string }).raceId === raceId
    );
    if (found) {
      return parseKaisaiKey(kaisaiKey);
    }
  }
  return null;
}

/**
 * 開催情報を取得（フォールバック付き）
 * race_id で見つからない場合、競馬場名＋レース番号で検索する
 */
export function getKaisaiInfoFromRaceInfoWithFallback(
  kaisaiData: Record<string, Array<{ race_id?: string; raceId?: string; race_no?: string }>>,
  raceId: string,
  track: string,
  raceNumber: number
): { kai: number; nichi: number; track: string } | null {
  const exact = getKaisaiInfoFromRaceInfo(kaisaiData, raceId);
  if (exact) return exact;

  // 2) 競馬場＋レース番号で検索（race_id 表記ゆれ対策）
  for (const [kaisaiKey, races] of Object.entries(kaisaiData)) {
    const parsed = parseKaisaiKey(kaisaiKey);
    if (!parsed || parsed.track !== track) continue;
    const found = races.find(r => {
      const no = r.race_no ? parseInt(r.race_no.replace(/R$/i, ''), 10) : NaN;
      return !Number.isNaN(no) && no === raceNumber;
    });
    if (found) return parsed;
  }
  // 3) 競馬場名のみで一致する開催キーを採用（race_id が配列に無い場合の最終フォールバック）
  for (const [kaisaiKey] of Object.entries(kaisaiData)) {
    const parsed = parseKaisaiKey(kaisaiKey);
    if (parsed && parsed.track === track) return parsed;
  }
  return null;
}

/**
 * レースIDから情報を抽出
 */
export function parseRaceId(raceId: string): {
  year: number;
  raceNumber: number;
} | null {
  if (raceId.length < 12) return null;
  
  return {
    year: parseInt(raceId.substring(0, 4), 10),
    raceNumber: parseInt(raceId.substring(10, 12), 10),
  };
}

/**
 * 利用可能な競馬場コード一覧を取得
 */
export function getAvailableTracks(): string[] {
  return Object.keys(TRACK_CODES);
}
