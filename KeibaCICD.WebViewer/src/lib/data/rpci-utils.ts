/**
 * RPCI計算ユーティリティ（クライアント/サーバー両用）
 * fsを使用しないため、クライアントコンポーネントからも利用可能
 */

// RPCI傾向タイプ（3段階 - 後方互換）
export type RpciTrend = 'instantaneous' | 'sustained' | 'neutral';

// レース傾向タイプ（5段階 - v3新規）
export type RaceTrendType =
  | 'sprint_finish'        // 瞬発戦
  | 'long_sprint'          // ロンスパ戦
  | 'even_pace'            // 平均ペース
  | 'front_loaded'         // Hペース前傾
  | 'front_loaded_strong'; // Hペース後傾

export const RACE_TREND_LABELS: Record<RaceTrendType, string> = {
  sprint_finish: '瞬発',
  long_sprint: 'ロンスパ',
  even_pace: '平均',
  front_loaded: 'H前傾',
  front_loaded_strong: 'H後傾',
};

export const RACE_TREND_COLORS: Record<RaceTrendType, string> = {
  sprint_finish: 'bg-blue-100 text-blue-700',
  long_sprint: 'bg-indigo-100 text-indigo-700',
  even_pace: 'bg-gray-100 text-gray-700',
  front_loaded: 'bg-red-100 text-red-700',
  front_loaded_strong: 'bg-orange-100 text-orange-700',
};

export interface RpciThresholds {
  instantaneous: number;  // 瞬発戦閾値
  sustained: number;      // 持続戦閾値
}

export interface CourseRpciInfo {
  courseKey: string;           // 例: "Tokyo_Turf_2000m"
  courseName: string;          // 例: "東京芝2000m"
  rpciMean: number;
  trend: RpciTrend;
  trendLabel: string;          // 例: "瞬発戦傾向"
  thresholds: RpciThresholds;
  similarCourses: string[];
  sampleCount: number;
  runnerAdjustment?: {         // 頭数別RPCI補正
    rpciOffset: number;
    sampleCount: number;
    runnerBand: string;        // "少頭数(~8)" / "中頭数(9-13)" / "多頭数(14~)"
  };
  babaCondition?: string;      // "良" / "稍重以上"（馬場別データ使用時）
}

export interface RaceRpciAnalysis {
  actualRpci: number;                   // 実際のRPCI値
  actualTrend: RpciTrend;               // 実際の傾向
  actualTrendLabel: string;             // 実際の傾向ラベル
  comparedToStandard: 'faster' | 'slower' | 'typical';  // 基準値との比較
  comparedToStandardLabel: string;      // 比較ラベル
  deviation: number;                    // 基準からの偏差
  sourceHorses: number;                 // 計算に使用した馬数
}

/**
 * RPCI傾向を判定
 */
export function getRpciTrend(rpciMean: number): { trend: RpciTrend; label: string } {
  if (rpciMean >= 51) {
    return { trend: 'instantaneous', label: '瞬発戦傾向' };
  } else if (rpciMean <= 48) {
    return { trend: 'sustained', label: '持続戦傾向' };
  }
  return { trend: 'neutral', label: '平均的' };
}

/**
 * 前3Fタイムを秒に変換
 * @param timeStr "35.2" や "1:12.3" 形式
 */
function parseTimeToSeconds(timeStr: string): number | null {
  if (!timeStr || timeStr === '-') return null;
  
  // "1:12.3" 形式
  if (timeStr.includes(':')) {
    const parts = timeStr.split(':');
    const minutes = parseInt(parts[0], 10);
    const seconds = parseFloat(parts[1]);
    if (isNaN(minutes) || isNaN(seconds)) return null;
    return minutes * 60 + seconds;
  }
  
  // "35.2" 形式
  const seconds = parseFloat(timeStr);
  if (isNaN(seconds)) return null;
  return seconds;
}

/**
 * レース結果から実際のRPCIを計算
 * @param entries レース出走馬配列（結果付き）
 * @param courseRpciInfo コースのRPCI基準値情報（オプション）
 */
export function calculateActualRpci(
  entries: Array<{
    result?: {
      finish_position?: string;
      first_3f?: string;
      last_3f?: string;
      time?: string;
    } | null;
  }>,
  courseRpciInfo?: CourseRpciInfo | null
): RaceRpciAnalysis | null {
  // 結果がある馬をフィルタリング
  const withResults = entries.filter(e => 
    e.result && 
    e.result.finish_position && 
    !isNaN(parseInt(e.result.finish_position, 10))
  );

  if (withResults.length === 0) return null;

  // 1着〜3着の馬からRPCIを計算（データの信頼性が高い）
  const topHorses = withResults
    .filter(e => {
      const pos = parseInt(e.result!.finish_position!, 10);
      return pos >= 1 && pos <= 3;
    })
    .sort((a, b) => 
      parseInt(a.result!.finish_position!, 10) - parseInt(b.result!.finish_position!, 10)
    );

  // RPCIを計算できる馬を抽出
  const validForRpci = topHorses.filter(e => {
    const first3f = parseTimeToSeconds(e.result?.first_3f || '');
    const last3f = parseTimeToSeconds(e.result?.last_3f || '');
    return first3f !== null && last3f !== null && last3f > 0;
  });

  if (validForRpci.length === 0) {
    // first_3fがない場合、走破タイムとlast_3fから計算を試みる
    const withTimeAndLast3f = topHorses.filter(e => {
      const time = parseTimeToSeconds(e.result?.time || '');
      const last3f = parseTimeToSeconds(e.result?.last_3f || '');
      return time !== null && last3f !== null && time > last3f;
    });

    if (withTimeAndLast3f.length === 0) return null;

    // 走破タイム - 上がり3F = 前半タイムとして計算
    const rpciValues = withTimeAndLast3f.map(e => {
      const time = parseTimeToSeconds(e.result!.time!)!;
      const last3f = parseTimeToSeconds(e.result!.last_3f!)!;
      const first3f = time - last3f;  // 概算（前半600mではなく全体-上がり）
      return (first3f / last3f) * 50;
    });

    const avgRpci = rpciValues.reduce((a, b) => a + b, 0) / rpciValues.length;
    return buildRpciAnalysis(avgRpci, withTimeAndLast3f.length, courseRpciInfo);
  }

  // 正確なRPCIを計算（前3F / 後3F × 50）
  const rpciValues = validForRpci.map(e => {
    const first3f = parseTimeToSeconds(e.result!.first_3f!)!;
    const last3f = parseTimeToSeconds(e.result!.last_3f!)!;
    return (first3f / last3f) * 50;
  });

  const avgRpci = rpciValues.reduce((a, b) => a + b, 0) / rpciValues.length;
  return buildRpciAnalysis(avgRpci, validForRpci.length, courseRpciInfo);
}

/**
 * RPCI分析結果を構築
 */
function buildRpciAnalysis(
  actualRpci: number,
  sourceHorses: number,
  courseRpciInfo?: CourseRpciInfo | null
): RaceRpciAnalysis {
  const { trend: actualTrend, label: actualTrendLabel } = getRpciTrend(actualRpci);

  let comparedToStandard: 'faster' | 'slower' | 'typical' = 'typical';
  let comparedToStandardLabel = 'コース平均的なペース';
  let deviation = 0;

  if (courseRpciInfo) {
    deviation = actualRpci - courseRpciInfo.rpciMean;
    
    if (actualRpci >= courseRpciInfo.thresholds.instantaneous) {
      comparedToStandard = 'slower';
      comparedToStandardLabel = 'スローペース（瞬発戦）';
    } else if (actualRpci <= courseRpciInfo.thresholds.sustained) {
      comparedToStandard = 'faster';
      comparedToStandardLabel = 'ハイペース（持続戦）';
    } else {
      comparedToStandardLabel = 'コース平均的なペース';
    }
  }

  return {
    actualRpci,
    actualTrend,
    actualTrendLabel,
    comparedToStandard,
    comparedToStandardLabel,
    deviation,
    sourceHorses,
  };
}
