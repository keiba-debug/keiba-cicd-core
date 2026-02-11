'use client';

/**
 * 馬分析結果表示コンポーネント
 */

import React from 'react';
import type { HorseAnalysis, AnalysisPoint } from '@/lib/horse-analyzer';
import { Badge } from '@/components/ui/badge';

interface HorseAnalysisSectionProps {
  analysis: HorseAnalysis;
}

// 信頼度バッジ
function ConfidenceBadge({ confidence }: { confidence: 'high' | 'medium' | 'low' }) {
  const styles = {
    high: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    low: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  };
  
  const labels = {
    high: '信頼度高',
    medium: '信頼度中',
    low: '参考',
  };
  
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded ${styles[confidence]}`}>
      {labels[confidence]}
    </span>
  );
}

// 分析ポイントカード
function AnalysisPointCard({ point, type }: { 
  point: AnalysisPoint; 
  type: 'strength' | 'weakness';
}) {
  const bgStyles = {
    strength: 'bg-emerald-50 border-emerald-200 dark:bg-emerald-900/20 dark:border-emerald-800',
    weakness: 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800',
  };
  
  const iconStyles = {
    strength: 'text-emerald-500',
    weakness: 'text-red-500',
  };
  
  const icons = {
    strength: '💪',
    weakness: '⚠️',
  };
  
  return (
    <div className={`p-3 rounded-lg border ${bgStyles[type]}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`text-lg ${iconStyles[type]}`}>{icons[type]}</span>
          <span className="font-medium text-sm">{point.label}</span>
        </div>
        <ConfidenceBadge confidence={point.confidence} />
      </div>
      <p className="text-xs text-muted-foreground mt-1 ml-7">
        {point.detail}
      </p>
    </div>
  );
}

export function HorseAnalysisSection({ analysis }: HorseAnalysisSectionProps) {
  const hasStrengths = analysis.strengths.length > 0;
  const hasWeaknesses = analysis.weaknesses.length > 0;
  const hasTargetConditions = analysis.targetConditions.length > 0;
  
  if (!hasStrengths && !hasWeaknesses && !hasTargetConditions) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
        <h2 className="text-lg font-semibold mb-4">🔍 分析</h2>
        <p className="text-muted-foreground text-sm">
          レース履歴が少ないため、分析データが不足しています。
        </p>
      </div>
    );
  }
  
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
      <h2 className="text-lg font-semibold mb-4">🔍 分析</h2>
      
      <div className="space-y-6">
        {/* 脚質 */}
        {analysis.passingStyle && analysis.passingStyle !== '不明' && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">脚質傾向:</span>
            <Badge variant="secondary" className="text-sm">
              🏃 {analysis.passingStyle}
            </Badge>
          </div>
        )}
        
        {/* 狙い目条件 */}
        {hasTargetConditions && (
          <div>
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <span className="text-amber-500">🎯</span>
              狙い目条件
            </h3>
            <div className="flex flex-wrap gap-2">
              {analysis.targetConditions.map((condition, idx) => (
                <Badge 
                  key={idx} 
                  className="bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-400"
                >
                  {condition}
                </Badge>
              ))}
            </div>
          </div>
        )}
        
        {/* 強み */}
        {hasStrengths && (
          <div>
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <span className="text-emerald-500">💪</span>
              強み
            </h3>
            <div className="grid gap-2">
              {analysis.strengths.map((point, idx) => (
                <AnalysisPointCard key={idx} point={point} type="strength" />
              ))}
            </div>
          </div>
        )}
        
        {/* 弱み */}
        {hasWeaknesses && (
          <div>
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <span className="text-red-500">⚠️</span>
              弱み・注意点
            </h3>
            <div className="grid gap-2">
              {analysis.weaknesses.map((point, idx) => (
                <AnalysisPointCard key={idx} point={point} type="weakness" />
              ))}
            </div>
          </div>
        )}
        
        {/* パターン分析サマリー */}
        {(analysis.patterns.bestDistance || analysis.patterns.bestSurface || 
          analysis.patterns.bestFrame || analysis.patterns.bestFieldSize) && (
          <div className="border-t pt-4 mt-4">
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <span>📊</span>
              ベストパターン
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {analysis.patterns.bestSurface && (
                <div>
                  <span className="text-muted-foreground">馬場:</span>
                  <span className="ml-1 font-medium">{analysis.patterns.bestSurface}</span>
                </div>
              )}
              {analysis.patterns.bestDistance && (
                <div>
                  <span className="text-muted-foreground">距離:</span>
                  <span className="ml-1 font-medium">{analysis.patterns.bestDistance}</span>
                </div>
              )}
              {analysis.patterns.bestFrame && (
                <div>
                  <span className="text-muted-foreground">枠順:</span>
                  <span className="ml-1 font-medium">{analysis.patterns.bestFrame}</span>
                </div>
              )}
              {analysis.patterns.bestCondition && (
                <div>
                  <span className="text-muted-foreground">馬場状態:</span>
                  <span className="ml-1 font-medium">{analysis.patterns.bestCondition}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
