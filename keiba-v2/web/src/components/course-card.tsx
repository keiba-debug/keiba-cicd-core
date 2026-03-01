'use client';

import { useState } from 'react';

// コース情報の型定義
export interface CourseInfo {
  trackName: string;
  surface: '芝' | 'ダート' | '障害';
  distanceMeters: number;
  turn: '右' | '左' | '直線';
  courseVariant?: '内' | '外' | '内回り' | '外回り' | 'なし';
  courseGeometry?: {
    straightLengthM: number;
    elevationDiffM: number;
    cornerCount: number;
    courseWidthM?: string;
    totalLengthM?: number;
  };
  straightDirection?: {
    runDirection: string;
    headwindDirection: string;
    tailwindDirection: string;
  };
  elevationProfile?: {
    description: string;
    points: { distanceFromGoalM: number; elevationM: number; landmark?: string }[];
    keyFeatures?: { position: string; description: string }[];
  };
  bias?: {
    drawBias: string;
    runningStyleBias: string;
    paceBias?: string;
    groundConditionNotes?: string;
  };
  runningStyleStats?: {
    escape: number;
    frontRunner: number;
    stalker: number;
    closer: number;
    sampleCount?: number;
    period?: string;
  };
  pciStandard?: {
    overall?: {
      standard: number;
      hThreshold: number;
      sThreshold: number;
      sampleCount?: number;
    };
  };
  raceQuality?: {
    standard: string;
    highSpeedTrack?: string;
    wetTrack?: string;
  };
  // 馬場分析データ（analyze_baba_report.py由来）
  babaAnalysis?: {
    firstCornerDistM?: number;       // 1角までの距離（メートル）
    firstCornerClass?: '超短(~250m)' | '短(250-350m)' | '中(350-450m)' | '長(450m~)';
    sampleSize: number;              // 分析対象サンプル数
    innerTop3Pct: number;            // 内枠(1-3)のtop3率
    outerTop3Pct: number;            // 外枠(6-8)のtop3率
    innerAdvantage: number;          // 内有利度（pt）
    frontRunnerTop3Pct: number;      // 逃先のtop3率
    sashiTop3Pct?: number;           // 差しのtop3率
    styleAdvantage: number;          // 差し有利度（pt、負=前有利）
    // 馬場状態別バイアス
    conditionBias?: {
      label: string;                 // 例: "乾燥", "標準", "湿潤" or "硬", "標準", "柔"
      sampleSize: number;
      innerAdvantage: number;
      styleAdvantage?: number;
    }[];
    // 開催進行バイアス（会場レベル）
    kaisaiProgression?: {
      phase: string;                 // 序盤/前半/中盤/後半
      sampleSize: number;
      styleAdvantage: number;        // 差し有利度
    }[];
  };
}

// 高低断面図コンポーネント
function ElevationProfile({ profile, width = 300, height = 80 }: { 
  profile: CourseInfo['elevationProfile']; 
  width?: number;
  height?: number;
}) {
  if (!profile?.points || profile.points.length < 2) {
    return (
      <div className="bg-gray-100 rounded p-4 text-center text-gray-500 text-sm">
        断面図データなし
      </div>
    );
  }

  const points = profile.points;
  const maxDist = Math.max(...points.map(p => p.distanceFromGoalM));
  const minElev = Math.min(...points.map(p => p.elevationM));
  const maxElev = Math.max(...points.map(p => p.elevationM));
  const elevRange = maxElev - minElev || 1;

  const padding = { top: 10, bottom: 25, left: 5, right: 5 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // ポイントをSVG座標に変換（ゴールが左側）
  const svgPoints = points.map(p => ({
    x: padding.left + (1 - p.distanceFromGoalM / maxDist) * chartWidth,
    y: padding.top + (1 - (p.elevationM - minElev) / elevRange) * chartHeight,
    landmark: p.landmark,
    elevation: p.elevationM
  }));

  // パスを生成
  const pathD = svgPoints.map((p, i) => 
    `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
  ).join(' ');

  // 塗りつぶし用のパス
  const fillD = `${pathD} L ${svgPoints[svgPoints.length - 1].x} ${height - padding.bottom} L ${svgPoints[0].x} ${height - padding.bottom} Z`;

  return (
    <svg width={width} height={height} className="w-full">
      <defs>
        <linearGradient id="elevGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0.2" />
        </linearGradient>
      </defs>
      
      {/* グリッド線 */}
      <line 
        x1={padding.left} 
        y1={height - padding.bottom} 
        x2={width - padding.right} 
        y2={height - padding.bottom} 
        stroke="#ddd" 
        strokeWidth="1"
      />
      <line 
        x1={padding.left} 
        y1={padding.top + chartHeight / 2} 
        x2={width - padding.right} 
        y2={padding.top + chartHeight / 2} 
        stroke="#eee" 
        strokeWidth="1"
        strokeDasharray="4,4"
      />

      {/* 塗りつぶし */}
      <path d={fillD} fill="url(#elevGradient)" />
      
      {/* ライン */}
      <path d={pathD} fill="none" stroke="#16a34a" strokeWidth="2" />

      {/* ランドマーク */}
      {svgPoints.filter(p => p.landmark).map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="3" fill="#16a34a" />
          <text 
            x={p.x} 
            y={height - 5} 
            textAnchor="middle" 
            fontSize="8" 
            fill="#666"
          >
            {p.landmark === 'ゴール' ? '🏁' : p.landmark?.replace('コーナー', 'C')}
          </text>
        </g>
      ))}

      {/* スタート・ゴールラベル */}
      <text x={padding.left + 5} y={height - 8} fontSize="9" fill="#333">ゴール</text>
      <text x={width - padding.right - 25} y={height - 8} fontSize="9" fill="#333">スタート</text>
    </svg>
  );
}

// 脚質傾向バーチャート
function RunningStyleChart({ stats }: { stats: CourseInfo['runningStyleStats'] }) {
  if (!stats) {
    return (
      <div className="text-gray-500 text-sm">データなし</div>
    );
  }

  const styles = [
    { label: '逃げ', value: stats.escape, color: 'bg-red-500' },
    { label: '先行', value: stats.frontRunner, color: 'bg-orange-500' },
    { label: '差し', value: stats.stalker, color: 'bg-blue-500' },
    { label: '追込', value: stats.closer, color: 'bg-purple-500' },
  ];

  const maxValue = Math.max(...styles.map(s => s.value));

  return (
    <div className="space-y-1.5">
      {styles.map((style, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="w-8 text-gray-600">{style.label}</span>
          <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className={`h-full ${style.color} transition-all duration-500`}
              style={{ width: `${(style.value / maxValue) * 100}%` }}
            />
          </div>
          <span className="w-10 text-right font-mono text-gray-700">
            {style.value}%
            {style.value === maxValue && <span className="ml-1 text-green-600">★</span>}
          </span>
        </div>
      ))}
      {stats.sampleCount && (
        <div className="text-xs text-gray-400 text-right">
          n={stats.sampleCount} ({stats.period})
        </div>
      )}
    </div>
  );
}

// コースバイアスバッジ
function BiasBadges({ bias }: { bias: CourseInfo['bias'] }) {
  if (!bias) return null;

  const badges = [];
  
  if (bias.drawBias) {
    const isInner = bias.drawBias.includes('内');
    badges.push({
      label: bias.drawBias,
      color: isInner ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700',
      icon: isInner ? '🔵' : '🟠'
    });
  }
  
  if (bias.runningStyleBias) {
    const isFront = bias.runningStyleBias.includes('先行') || bias.runningStyleBias.includes('逃げ');
    badges.push({
      label: bias.runningStyleBias,
      color: isFront ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700',
      icon: isFront ? '🏃' : '💨'
    });
  }
  
  if (bias.paceBias) {
    const isSlow = bias.paceBias.includes('スロー');
    badges.push({
      label: bias.paceBias,
      color: isSlow ? 'bg-yellow-100 text-yellow-700' : 'bg-purple-100 text-purple-700',
      icon: isSlow ? '🐢' : '🐇'
    });
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {badges.map((badge, i) => (
        <span 
          key={i}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${badge.color}`}
        >
          <span>{badge.icon}</span>
          {badge.label}
        </span>
      ))}
    </div>
  );
}

// 表面タイプのアイコン
function SurfaceIcon({ surface }: { surface: '芝' | 'ダート' | '障害' }) {
  const styles = {
    '芝': { bg: 'bg-green-500', icon: '🌿' },
    'ダート': { bg: 'bg-amber-600', icon: '🏜️' },
    '障害': { bg: 'bg-gray-500', icon: '🚧' },
  };
  const style = styles[surface];
  
  return (
    <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full ${style.bg} text-white text-lg`}>
      {style.icon}
    </span>
  );
}

// 内有利度ゲージ
function InnerAdvantageGauge({ value, label }: { value: number; label: string }) {
  // -10 ~ +10 のスケールでゲージ表示
  const clampedValue = Math.max(-10, Math.min(10, value));
  const pct = ((clampedValue + 10) / 20) * 100;
  const isInner = value > 0;
  const color = isInner
    ? value >= 5 ? 'text-blue-700' : 'text-blue-500'
    : value <= -5 ? 'text-orange-700' : 'text-orange-500';
  const bgColor = isInner
    ? value >= 5 ? 'bg-blue-500' : 'bg-blue-400'
    : value <= -5 ? 'bg-orange-500' : 'bg-orange-400';

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-14 shrink-0">{label}</span>
      <div className="flex-1 relative">
        <div className="h-3 bg-gray-200 rounded-full relative overflow-hidden">
          {/* center line */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-400 z-10" />
          {/* filled bar */}
          {isInner ? (
            <div className={`absolute top-0 bottom-0 ${bgColor} rounded-r-full`}
                 style={{ left: '50%', width: `${(pct - 50)}%` }} />
          ) : (
            <div className={`absolute top-0 bottom-0 ${bgColor} rounded-l-full`}
                 style={{ right: '50%', width: `${(50 - pct)}%` }} />
          )}
        </div>
        <div className="flex justify-between text-[9px] text-gray-400 mt-0.5">
          <span>外有利</span>
          <span>内有利</span>
        </div>
      </div>
      <span className={`font-bold text-sm w-16 text-right ${color}`}>
        {value > 0 ? '+' : ''}{value.toFixed(1)}pt
      </span>
    </div>
  );
}

// 馬場分析セクション
function BabaAnalysisSection({ baba }: { baba: NonNullable<CourseInfo['babaAnalysis']> }) {
  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-500 mb-1">📊 馬場バイアス分析 (n={baba.sampleSize.toLocaleString()})</div>

      {/* 内外・脚質ゲージ */}
      <div className="space-y-2">
        <InnerAdvantageGauge value={baba.innerAdvantage} label="内外" />
        <InnerAdvantageGauge value={baba.styleAdvantage} label="脚質" />
      </div>

      {/* 数値サマリ */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-gray-500">内枠(1-3) top3</div>
          <div className="font-bold text-sm">{baba.innerTop3Pct.toFixed(1)}%</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-gray-500">外枠(6-8) top3</div>
          <div className="font-bold text-sm">{baba.outerTop3Pct.toFixed(1)}%</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-gray-500">逃先 top3</div>
          <div className="font-bold text-sm">{baba.frontRunnerTop3Pct.toFixed(1)}%</div>
        </div>
        {baba.firstCornerDistM && (
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-gray-500">1角距離</div>
            <div className="font-bold text-sm">{baba.firstCornerDistM}m
              <span className="text-[10px] text-gray-400 ml-1">{baba.firstCornerClass}</span>
            </div>
          </div>
        )}
      </div>

      {/* 馬場状態別バイアス */}
      {baba.conditionBias && baba.conditionBias.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 mb-1">馬場状態別</div>
          <div className="space-y-1">
            {baba.conditionBias.map((cb, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="w-20 text-gray-600 shrink-0">{cb.label}</span>
                <span className="text-gray-400">n={cb.sampleSize}</span>
                <span className={`font-mono font-medium ${cb.innerAdvantage > 0 ? 'text-blue-600' : 'text-orange-600'}`}>
                  内{cb.innerAdvantage > 0 ? '+' : ''}{cb.innerAdvantage.toFixed(1)}pt
                </span>
                {cb.styleAdvantage !== undefined && (
                  <span className="text-gray-500 font-mono">
                    脚{cb.styleAdvantage > 0 ? '+' : ''}{cb.styleAdvantage.toFixed(1)}pt
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// メインのコースカードコンポーネント
export function CourseCard({ course, compact = false }: { course: CourseInfo; compact?: boolean }) {
  const [isExpanded, setIsExpanded] = useState(!compact);

  const baba = course.babaAnalysis;
  const headerBg = course.surface === 'ダート'
    ? 'from-amber-50 to-orange-50'
    : 'from-green-50 to-emerald-50';

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden hover:shadow-md transition-shadow">
      {/* ヘッダー */}
      <div
        className={`p-4 bg-gradient-to-r ${headerBg} cursor-pointer`}
        onClick={() => compact && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <SurfaceIcon surface={course.surface} />
          <div className="flex-1 min-w-0">
            <h3 className="font-bold text-lg">
              {course.trackName} {course.surface}{course.distanceMeters}m
              {course.courseVariant && course.courseVariant !== 'なし' && (
                <span className="text-gray-500 text-sm ml-1">({course.courseVariant})</span>
              )}
            </h3>
            <div className="flex items-center gap-3 text-sm text-gray-600 mt-0.5 flex-wrap">
              <span>{course.turn}回り</span>
              {course.courseGeometry && (
                <>
                  <span>直線{course.courseGeometry.straightLengthM}m</span>
                  <span>高低差{course.courseGeometry.elevationDiffM}m</span>
                </>
              )}
              {baba?.firstCornerDistM && (
                <span>1角{baba.firstCornerDistM}m</span>
              )}
            </div>
          </div>
          {/* ヘッダーのミニバイアス表示 */}
          {baba && (
            <div className="flex flex-col items-end gap-0.5 shrink-0">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                baba.innerAdvantage >= 3 ? 'bg-blue-100 text-blue-700'
                : baba.innerAdvantage <= -3 ? 'bg-orange-100 text-orange-700'
                : 'bg-gray-100 text-gray-600'
              }`}>
                {baba.innerAdvantage >= 3 ? '内有利' : baba.innerAdvantage <= -3 ? '外有利' : 'フラット'}
                {baba.innerAdvantage !== 0 && ` ${baba.innerAdvantage > 0 ? '+' : ''}${baba.innerAdvantage.toFixed(1)}`}
              </span>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                baba.styleAdvantage >= -10 ? 'bg-green-100 text-green-700'
                : baba.styleAdvantage <= -20 ? 'bg-red-100 text-red-700'
                : 'bg-yellow-100 text-yellow-700'
              }`}>
                {baba.styleAdvantage >= -10 ? '差し有効' : baba.styleAdvantage <= -20 ? '先行圧倒' : '先行有利'}
              </span>
            </div>
          )}
          {compact && (
            <span className="text-gray-400 text-lg">
              {isExpanded ? '▲' : '▼'}
            </span>
          )}
        </div>
      </div>

      {/* 展開コンテンツ */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          {/* 馬場分析（新） */}
          {baba && <BabaAnalysisSection baba={baba} />}

          {/* バイアスバッジ（既存・手動定義データ用） */}
          {course.bias && (
            <div>
              <div className="text-xs text-gray-500 mb-1.5">📋 コース傾向メモ</div>
              <BiasBadges bias={course.bias} />
              {course.bias.groundConditionNotes && (
                <div className="text-xs text-gray-500 mt-1">{course.bias.groundConditionNotes}</div>
              )}
            </div>
          )}

          {/* 高低断面図 */}
          {course.elevationProfile && (
            <div>
              <div className="text-xs text-gray-500 mb-1.5">⛰️ 高低断面図</div>
              <ElevationProfile profile={course.elevationProfile} width={320} height={90} />
              {course.elevationProfile.keyFeatures && (
                <div className="mt-2 space-y-0.5">
                  {course.elevationProfile.keyFeatures.map((f, i) => (
                    <div key={i} className="text-xs text-gray-600">
                      <span className="font-medium">{f.position}:</span> {f.description}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 脚質傾向 */}
          {course.runningStyleStats && (
            <div>
              <div className="text-xs text-gray-500 mb-1.5">🎯 脚質別勝率</div>
              <RunningStyleChart stats={course.runningStyleStats} />
            </div>
          )}

          {/* 直線方角 */}
          {course.straightDirection && (
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">🧭 直線の方角（風向き分析用）</div>
              <div className="text-sm">
                <span className="font-medium">{course.straightDirection.runDirection}</span>
              </div>
              <div className="text-xs text-gray-600 mt-1">
                向かい風: {course.straightDirection.headwindDirection} /
                追い風: {course.straightDirection.tailwindDirection}
              </div>
            </div>
          )}

          {/* PCI基準値 */}
          {course.pciStandard?.overall && (
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">⚡ PCI基準値</div>
              <div className="flex items-center gap-4 text-sm">
                <div>
                  <span className="text-lg font-bold text-blue-600">
                    {course.pciStandard.overall.standard.toFixed(1)}
                  </span>
                  <span className="text-gray-500 text-xs ml-1">基準</span>
                </div>
                <div className="text-xs text-gray-600">
                  H &lt; {course.pciStandard.overall.hThreshold.toFixed(1)} &lt; M &lt; {course.pciStandard.overall.sThreshold.toFixed(1)} &lt; S
                </div>
              </div>
            </div>
          )}

          {/* レース質 */}
          {course.raceQuality && (
            <div className="text-xs text-gray-600 border-t pt-3">
              <div className="font-medium mb-1">📋 レース質</div>
              <div>標準: {course.raceQuality.standard}</div>
              {course.raceQuality.highSpeedTrack && (
                <div>超高速馬場: {course.raceQuality.highSpeedTrack}</div>
              )}
              {course.raceQuality.wetTrack && (
                <div>重馬場: {course.raceQuality.wetTrack}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// コースカードグリッド
export function CourseCardGrid({ courses }: { courses: CourseInfo[] }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {courses.map((course, i) => (
        <CourseCard key={i} course={course} />
      ))}
    </div>
  );
}
