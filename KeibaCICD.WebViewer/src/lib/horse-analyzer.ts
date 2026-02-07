/**
 * 馬分析エンジン
 * 
 * 過去レース履歴から馬の強み・弱み・狙い目条件を分析
 */

import type { HorseRaceResult, HorseStats, StatGroup } from '@/lib/data/integrated-horse-reader';

/**
 * 分析結果
 */
export interface HorseAnalysis {
  strengths: AnalysisPoint[];      // 強み
  weaknesses: AnalysisPoint[];     // 弱み
  targetConditions: string[];      // 狙い目条件
  patterns: PatternAnalysis;       // パターン分析
  passingStyle: string;            // 脚質傾向
}

export interface AnalysisPoint {
  label: string;
  detail: string;
  confidence: 'high' | 'medium' | 'low';  // 信頼度（サンプル数に基づく）
}

export interface PatternAnalysis {
  bestDistance: string;
  bestSurface: string;
  bestFrame: string;
  bestFieldSize: string;
  bestCondition: string;
}

/**
 * 脚質を分析
 */
function analyzePassingStyle(pastRaces: HorseRaceResult[]): string {
  if (pastRaces.length < 3) return '不明';
  
  const validRaces = pastRaces.slice(0, 10).filter(r => {
    const pos = parseInt(r.finishPosition, 10);
    return !isNaN(pos) && r.cornerPositions;
  });
  
  if (validRaces.length < 3) return '不明';
  
  let escapeCount = 0;
  let frontCount = 0;
  let midCount = 0;
  let rearCount = 0;
  
  for (const race of validRaces) {
    // 通過順位の最初の値を取得
    const positions = race.cornerPositions.replace(/[^0-9-]/g, '').split('-');
    const firstCorner = parseInt(positions[0], 10);
    
    if (isNaN(firstCorner)) continue;
    
    // 頭数に対する相対位置で判定
    const headCount = race.headCount || 18;
    const relativePos = firstCorner / headCount;
    
    if (relativePos <= 0.15) escapeCount++;
    else if (relativePos <= 0.35) frontCount++;
    else if (relativePos <= 0.65) midCount++;
    else rearCount++;
  }
  
  const total = escapeCount + frontCount + midCount + rearCount;
  if (total === 0) return '不明';
  
  const max = Math.max(escapeCount, frontCount, midCount, rearCount);
  
  if (escapeCount === max) return '逃げ';
  if (frontCount === max) return '先行';
  if (midCount === max) return '差し';
  return '追込';
}

/**
 * 信頼度を判定
 */
function getConfidence(races: number): 'high' | 'medium' | 'low' {
  if (races >= 10) return 'high';
  if (races >= 5) return 'medium';
  return 'low';
}

/**
 * 最高成績の条件を取得
 */
function getBestCondition(
  groups: Record<string, StatGroup>,
  minRaces: number = 3
): { key: string; group: StatGroup } | null {
  let best: { key: string; group: StatGroup } | null = null;
  
  for (const [key, group] of Object.entries(groups)) {
    if (group.races < minRaces) continue;
    if (!best || group.showRate > best.group.showRate) {
      best = { key, group };
    }
  }
  
  return best;
}

/**
 * 最低成績の条件を取得
 */
function getWorstCondition(
  groups: Record<string, StatGroup>,
  minRaces: number = 3
): { key: string; group: StatGroup } | null {
  let worst: { key: string; group: StatGroup } | null = null;
  
  for (const [key, group] of Object.entries(groups)) {
    if (group.races < minRaces) continue;
    if (!worst || group.showRate < worst.group.showRate) {
      worst = { key, group };
    }
  }
  
  return worst;
}

/**
 * 馬を分析
 */
export function analyzeHorse(
  pastRaces: HorseRaceResult[],
  stats: HorseStats
): HorseAnalysis {
  const analysis: HorseAnalysis = {
    strengths: [],
    weaknesses: [],
    targetConditions: [],
    patterns: {
      bestDistance: '',
      bestSurface: '',
      bestFrame: '',
      bestFieldSize: '',
      bestCondition: '',
    },
    passingStyle: '',
  };
  
  // 脚質分析
  analysis.passingStyle = analyzePassingStyle(pastRaces);
  
  // 芝/ダート比較
  if (stats.turf.races >= 3 && stats.dirt.races >= 3) {
    if (stats.turf.showRate > stats.dirt.showRate + 15) {
      analysis.strengths.push({
        label: '芝が得意',
        detail: `芝の複勝率${stats.turf.showRate}%（ダート${stats.dirt.showRate}%）`,
        confidence: getConfidence(stats.turf.races),
      });
      analysis.targetConditions.push('芝');
      analysis.patterns.bestSurface = '芝';
    } else if (stats.dirt.showRate > stats.turf.showRate + 15) {
      analysis.strengths.push({
        label: 'ダートが得意',
        detail: `ダートの複勝率${stats.dirt.showRate}%（芝${stats.turf.showRate}%）`,
        confidence: getConfidence(stats.dirt.races),
      });
      analysis.targetConditions.push('ダート');
      analysis.patterns.bestSurface = 'ダート';
    }
  } else if (stats.turf.races >= 3 && stats.turf.showRate >= 40) {
    analysis.strengths.push({
      label: '芝が得意',
      detail: `芝の複勝率${stats.turf.showRate}%`,
      confidence: getConfidence(stats.turf.races),
    });
    analysis.patterns.bestSurface = '芝';
  } else if (stats.dirt.races >= 3 && stats.dirt.showRate >= 40) {
    analysis.strengths.push({
      label: 'ダートが得意',
      detail: `ダートの複勝率${stats.dirt.showRate}%`,
      confidence: getConfidence(stats.dirt.races),
    });
    analysis.patterns.bestSurface = 'ダート';
  }
  
  // 距離別分析
  const bestDistance = getBestCondition(stats.byDistance);
  const worstDistance = getWorstCondition(stats.byDistance);
  
  if (bestDistance && bestDistance.group.showRate >= 40) {
    analysis.strengths.push({
      label: `${bestDistance.key}が得意`,
      detail: `複勝率${bestDistance.group.showRate}%（${bestDistance.group.races}戦）`,
      confidence: getConfidence(bestDistance.group.races),
    });
    analysis.targetConditions.push(bestDistance.key);
    analysis.patterns.bestDistance = bestDistance.key;
  }
  
  if (worstDistance && worstDistance.group.showRate < 20 && worstDistance.group.races >= 5) {
    analysis.weaknesses.push({
      label: `${worstDistance.key}は苦手`,
      detail: `複勝率${worstDistance.group.showRate}%（${worstDistance.group.races}戦）`,
      confidence: getConfidence(worstDistance.group.races),
    });
  }
  
  // 馬場状態別分析
  const bestCondition = getBestCondition(stats.byCondition);
  const worstCondition = getWorstCondition(stats.byCondition);
  
  if (bestCondition && bestCondition.group.showRate >= 45) {
    analysis.strengths.push({
      label: `${bestCondition.key}馬場が得意`,
      detail: `複勝率${bestCondition.group.showRate}%（${bestCondition.group.races}戦）`,
      confidence: getConfidence(bestCondition.group.races),
    });
    analysis.patterns.bestCondition = bestCondition.key;
  }
  
  // 枠順別分析
  if (stats.byFrame) {
    const bestFrame = getBestCondition(stats.byFrame);
    const worstFrame = getWorstCondition(stats.byFrame);
    
    if (bestFrame && bestFrame.group.showRate >= 45) {
      analysis.strengths.push({
        label: `${bestFrame.key}が得意`,
        detail: `複勝率${bestFrame.group.showRate}%（${bestFrame.group.races}戦）`,
        confidence: getConfidence(bestFrame.group.races),
      });
      analysis.targetConditions.push(bestFrame.key);
      analysis.patterns.bestFrame = bestFrame.key;
    }
    
    if (worstFrame && worstFrame.group.showRate < 15 && worstFrame.group.races >= 5) {
      analysis.weaknesses.push({
        label: `${worstFrame.key}は苦手`,
        detail: `複勝率${worstFrame.group.showRate}%（${worstFrame.group.races}戦）`,
        confidence: getConfidence(worstFrame.group.races),
      });
    }
  }
  
  // 頭数別分析
  if (stats.byFieldSize) {
    const bestFieldSize = getBestCondition(stats.byFieldSize);
    const worstFieldSize = getWorstCondition(stats.byFieldSize);
    
    if (bestFieldSize && bestFieldSize.group.showRate >= 45) {
      analysis.strengths.push({
        label: `${bestFieldSize.key}が得意`,
        detail: `複勝率${bestFieldSize.group.showRate}%（${bestFieldSize.group.races}戦）`,
        confidence: getConfidence(bestFieldSize.group.races),
      });
      analysis.patterns.bestFieldSize = bestFieldSize.key;
    }
    
    if (worstFieldSize && worstFieldSize.group.showRate < 15 && worstFieldSize.group.races >= 5) {
      analysis.weaknesses.push({
        label: `${worstFieldSize.key}は苦手`,
        detail: `複勝率${worstFieldSize.group.showRate}%（${worstFieldSize.group.races}戦）`,
        confidence: getConfidence(worstFieldSize.group.races),
      });
    }
  }
  
  // 脚質に基づく分析
  if (analysis.passingStyle === '逃げ' || analysis.passingStyle === '先行') {
    analysis.strengths.push({
      label: `${analysis.passingStyle}脚質`,
      detail: '前につけられる脚質。展開に左右されにくい',
      confidence: 'medium',
    });
  } else if (analysis.passingStyle === '追込') {
    analysis.weaknesses.push({
      label: '追込脚質',
      detail: '展開次第で届かないリスクあり',
      confidence: 'medium',
    });
  }
  
  // 全体の勝率が高い場合
  if (stats.total.winRate >= 20) {
    analysis.strengths.push({
      label: '高勝率',
      detail: `通算勝率${stats.total.winRate}%`,
      confidence: getConfidence(stats.total.races),
    });
  }
  
  // 安定した複勝率
  if (stats.total.showRate >= 50) {
    analysis.strengths.push({
      label: '安定した成績',
      detail: `通算複勝率${stats.total.showRate}%`,
      confidence: getConfidence(stats.total.races),
    });
  }
  
  // 成績が低迷している場合
  if (stats.total.races >= 10 && stats.total.showRate < 15) {
    analysis.weaknesses.push({
      label: '成績低迷中',
      detail: `通算複勝率${stats.total.showRate}%（${stats.total.races}戦）`,
      confidence: 'high',
    });
  }
  
  return analysis;
}
