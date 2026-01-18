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

// メインのコースカードコンポーネント
export function CourseCard({ course, compact = false }: { course: CourseInfo; compact?: boolean }) {
  const [isExpanded, setIsExpanded] = useState(!compact);

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden hover:shadow-md transition-shadow">
      {/* ヘッダー */}
      <div 
        className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 cursor-pointer"
        onClick={() => compact && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <SurfaceIcon surface={course.surface} />
          <div className="flex-1">
            <h3 className="font-bold text-lg">
              {course.trackName}競馬場 {course.surface}{course.distanceMeters}m
              {course.courseVariant && course.courseVariant !== 'なし' && (
                <span className="text-gray-500 text-sm ml-1">（{course.courseVariant}）</span>
              )}
            </h3>
            <div className="flex items-center gap-3 text-sm text-gray-600 mt-0.5">
              <span>🔄 {course.turn}回り</span>
              {course.courseGeometry && (
                <>
                  <span>📏 直線{course.courseGeometry.straightLengthM}m</span>
                  <span>⛰️ 高低差{course.courseGeometry.elevationDiffM}m</span>
                </>
              )}
            </div>
          </div>
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
          {/* バイアスバッジ */}
          {course.bias && (
            <div>
              <div className="text-xs text-gray-500 mb-1.5">📊 コース傾向</div>
              <BiasBadges bias={course.bias} />
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
