import { CourseCard, CourseCardGrid, type CourseInfo } from '@/components/course-card';

// サンプルデータ（中山芝内回り）- 実データ基づく
const nakayamaTurf2000: CourseInfo = {
  trackName: '中山',
  surface: '芝',
  distanceMeters: 2000,
  turn: '右',
  courseVariant: '内回り',
  
  courseGeometry: {
    straightLengthM: 310,
    elevationDiffM: 5.3,
    cornerCount: 4,
    courseWidthM: '20-32m',
    totalLengthM: 1667.1
  },
  
  straightDirection: {
    runDirection: '南南西→北北東',
    headwindDirection: '北北東',
    tailwindDirection: '南南西'
  },
  
  elevationProfile: {
    description: '芝コース高低断面図（右・内回り）',
    points: [
      { distanceFromGoalM: 0, elevationM: 2.0, landmark: 'ゴール' },
      { distanceFromGoalM: 70, elevationM: 0.0, landmark: '急坂終点' },
      { distanceFromGoalM: 180, elevationM: -2.2, landmark: '急坂開始' },
      { distanceFromGoalM: 310, elevationM: -2.5, landmark: '4コーナー' },
      { distanceFromGoalM: 600, elevationM: -3.5, landmark: '最深部' },
      { distanceFromGoalM: 750, elevationM: -3.0, landmark: '3コーナー' },
      { distanceFromGoalM: 950, elevationM: -1.5, landmark: '向正面' },
      { distanceFromGoalM: 1350, elevationM: 2.0, landmark: '2コーナー' },
      { distanceFromGoalM: 1500, elevationM: 2.8, landmark: '最高地点' },
      { distanceFromGoalM: 1600, elevationM: 2.5, landmark: '1コーナー' },
      { distanceFromGoalM: 1667, elevationM: 2.0, landmark: 'スタート' }
    ],
    keyFeatures: [
      { position: 'ゴール前180m-70m', description: '中山名物の急坂（高低差2.2m、最大勾配2.24%・JRA最大）' },
      { position: '2コーナー手前', description: '最高到達点（+2.8m）' },
      { position: '3-4コーナー間', description: '最深部（-3.5m）' }
    ]
  },
  
  bias: {
    drawBias: '内枠有利',
    runningStyleBias: '先行有利',
    paceBias: 'スローペース有利',
    groundConditionNotes: '瞬発力勝負にはなりにくい。持久力勝負を得意とする馬が台頭'
  },
  
  runningStyleStats: {
    escape: 18,
    frontRunner: 35,
    stalker: 42,
    closer: 5,
    sampleCount: 200,
    period: '2023-2025'
  },
  
  pciStandard: {
    overall: {
      standard: 49.7,
      hThreshold: 47.0,
      sThreshold: 52.5,
      sampleCount: 104
    }
  },
  
  raceQuality: {
    standard: '内枠・先行・スローペース',
    highSpeedTrack: '内枠・先行・スローペース',
    wetTrack: '内枠・先行・スローペース'
  }
};

// 中山ダート - 実データ基づく
const nakayamaDirt1200: CourseInfo = {
  trackName: '中山',
  surface: 'ダート',
  distanceMeters: 1200,
  turn: '右',
  courseVariant: 'なし',
  
  courseGeometry: {
    straightLengthM: 308,
    elevationDiffM: 4.5,
    cornerCount: 4,
    totalLengthM: 1493
  },
  
  straightDirection: {
    runDirection: '南南西→北北東',
    headwindDirection: '北北東',
    tailwindDirection: '南南西'
  },
  
  elevationProfile: {
    description: 'ダートコース高低断面図（右回り）',
    points: [
      { distanceFromGoalM: 0, elevationM: 2.0, landmark: 'ゴール' },
      { distanceFromGoalM: 70, elevationM: 0.0, landmark: '急坂終点' },
      { distanceFromGoalM: 180, elevationM: -2.0, landmark: '急坂開始' },
      { distanceFromGoalM: 308, elevationM: -2.5, landmark: '4コーナー' },
      { distanceFromGoalM: 600, elevationM: -2.0, landmark: '向正面' },
      { distanceFromGoalM: 800, elevationM: -1.0, landmark: '3コーナー' },
      { distanceFromGoalM: 1150, elevationM: 1.5, landmark: '2コーナー' },
      { distanceFromGoalM: 1300, elevationM: 2.0, landmark: '1コーナー' },
      { distanceFromGoalM: 1493, elevationM: 2.0, landmark: 'スタート' }
    ],
    keyFeatures: [
      { position: 'ゴール前', description: '芝コース同様の急坂（高低差4.5m）' },
      { position: '1200mスタート', description: '芝スタート、発走してすぐ下り坂' }
    ]
  },
  
  bias: {
    drawBias: '外枠有利',
    runningStyleBias: '先行有利',
    paceBias: 'ハイペース',
    groundConditionNotes: '高含水率時は内枠有利。1200mのみ芝スタート'
  },
  
  runningStyleStats: {
    escape: 22,
    frontRunner: 38,
    stalker: 32,
    closer: 8,
    sampleCount: 383,
    period: '2023-2025'
  },
  
  pciStandard: {
    overall: {
      standard: 42.4,
      hThreshold: 39.6,
      sThreshold: 45.3,
      sampleCount: 383
    }
  },
  
  raceQuality: {
    standard: '外枠・先行・短縮・ハイペース',
    highSpeedTrack: '内枠・差し・短縮・ハイペース',
    wetTrack: '内枠・先行・ハイペース'
  }
};

// 東京芝2400m
const tokyoTurf2400: CourseInfo = {
  trackName: '東京',
  surface: '芝',
  distanceMeters: 2400,
  turn: '左',
  courseVariant: 'なし',
  
  courseGeometry: {
    straightLengthM: 525.9,
    elevationDiffM: 2.7,
    cornerCount: 4,
    totalLengthM: 2083.1
  },
  
  straightDirection: {
    runDirection: '東→西',
    headwindDirection: '西',
    tailwindDirection: '東'
  },
  
  bias: {
    drawBias: '枠順フラット',
    runningStyleBias: '差し有利',
    paceBias: 'ペースフラット',
    groundConditionNotes: '日本ダービーの舞台、長い直線で末脚勝負'
  },
  
  runningStyleStats: {
    escape: 12,
    frontRunner: 28,
    stalker: 45,
    closer: 15,
    sampleCount: 150,
    period: '2023-2025'
  },
  
  raceQuality: {
    standard: '差し・長い直線',
    highSpeedTrack: '差し・追込有利',
    wetTrack: '先行有利'
  }
};

// 京都芝1600m（外回り）- 実データ基づく
const kyotoTurf1600: CourseInfo = {
  trackName: '京都',
  surface: '芝',
  distanceMeters: 1600,
  turn: '右',
  courseVariant: '外回り',
  
  courseGeometry: {
    straightLengthM: 403.7,
    elevationDiffM: 4.3,
    cornerCount: 4,
    courseWidthM: '28-38m',
    totalLengthM: 1894.3
  },
  
  straightDirection: {
    runDirection: '南西→北東',
    headwindDirection: '北東',
    tailwindDirection: '南西'
  },
  
  elevationProfile: {
    description: '芝コース高低断面図（右・外回り）',
    points: [
      { distanceFromGoalM: 0, elevationM: 0.0, landmark: 'ゴール' },
      { distanceFromGoalM: 404, elevationM: 0.0, landmark: '直線入口' },
      { distanceFromGoalM: 550, elevationM: 0.5, landmark: '4コーナー' },
      { distanceFromGoalM: 700, elevationM: 2.5, landmark: '坂の下り' },
      { distanceFromGoalM: 850, elevationM: 4.3, landmark: '3コーナー（頂上）' },
      { distanceFromGoalM: 1000, elevationM: 3.0, landmark: '坂の上り' },
      { distanceFromGoalM: 1150, elevationM: 1.0, landmark: '向正面' },
      { distanceFromGoalM: 1300, elevationM: 0.0, landmark: '2コーナー' },
      { distanceFromGoalM: 1600, elevationM: 0.0, landmark: '1コーナー' },
      { distanceFromGoalM: 1894, elevationM: 0.0, landmark: 'スタート' }
    ],
    keyFeatures: [
      { position: '3コーナー', description: '京都名物「淀の坂」（頂上・高低差4.3m・JRA2位）' },
      { position: '3C→4C', description: '一気に下るレイアウト、惰性をつけて直線へ' },
      { position: '残り800m', description: '坂の頂上付近、ペースが上がるポイント' }
    ]
  },
  
  bias: {
    drawBias: '枠順フラット（幅員が広いため）',
    runningStyleBias: '差し有利',
    paceBias: 'スローペース',
    groundConditionNotes: 'マイルCS(G1)の舞台。坂の下りで惰性をつけて直線に向く戦法が浸透'
  },
  
  runningStyleStats: {
    escape: 15,
    frontRunner: 30,
    stalker: 40,
    closer: 15,
    sampleCount: 173,
    period: '2023-2025'
  },
  
  pciStandard: {
    overall: {
      standard: 53.6,
      hThreshold: 50.1,
      sThreshold: 57.0,
      sampleCount: 173
    }
  },
  
  raceQuality: {
    standard: '差し・スローペース',
    highSpeedTrack: '差し・追込有利',
    wetTrack: '先行有利'
  }
};

// データなしサンプル（最小構成）
const minimalCourse: CourseInfo = {
  trackName: '札幌',
  surface: '芝',
  distanceMeters: 1800,
  turn: '右',
};

const sampleCourses: CourseInfo[] = [
  nakayamaTurf2000,
  nakayamaDirt1200,
  tokyoTurf2400,
  kyotoTurf1600,
];

export default function CourseDemoPage() {
  return (
    <div className="container py-6">
      <h1 className="text-3xl font-bold mb-2">🏟️ コース情報ビジュアライズ デモ</h1>
      <p className="text-muted-foreground mb-6">
        競馬場コースデータを視覚化したコンポーネントのデモページです。
        高低断面図、脚質傾向、風向き情報などを表示します。
      </p>

      {/* 説明 */}
      <div className="bg-blue-50 rounded-lg p-4 mb-8 border border-blue-200">
        <h2 className="font-bold text-blue-800 mb-2">📊 表示項目</h2>
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <ul className="list-disc list-inside text-gray-700 space-y-1">
            <li>コース基本情報（距離、回り、直線長、高低差）</li>
            <li>コースバイアス（枠順、脚質、ペース）</li>
            <li>高低断面図（SVG描画）</li>
            <li>脚質別勝率（バーチャート）</li>
          </ul>
          <ul className="list-disc list-inside text-gray-700 space-y-1">
            <li>直線の方角（風向き分析用）</li>
            <li>PCI基準値</li>
            <li>レース質（馬場状態別）</li>
          </ul>
        </div>
      </div>

      {/* メインのサンプル */}
      <h2 className="text-xl font-bold mb-4">🎯 フル情報サンプル</h2>
      <div className="mb-8">
        <CourseCard course={nakayamaTurf2000} />
      </div>

      {/* グリッド表示 */}
      <h2 className="text-xl font-bold mb-4">📋 コース一覧（グリッド表示）</h2>
      <div className="mb-8">
        <CourseCardGrid courses={sampleCourses} />
      </div>

      {/* コンパクト表示 */}
      <h2 className="text-xl font-bold mb-4">📦 コンパクト表示（クリックで展開）</h2>
      <div className="space-y-2 mb-8">
        {sampleCourses.map((course, i) => (
          <CourseCard key={i} course={course} compact />
        ))}
      </div>

      {/* 最小データ */}
      <h2 className="text-xl font-bold mb-4">⚠️ データ不足時の表示</h2>
      <div className="max-w-md mb-8">
        <CourseCard course={minimalCourse} />
      </div>

      {/* 今後の拡張 */}
      <div className="mt-12 p-6 bg-green-50 rounded-lg border border-green-200">
        <h2 className="text-xl font-bold mb-4 text-green-800">🔮 今後の拡張予定</h2>
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <div>
            <h3 className="font-bold text-green-700 mb-2">データ整備</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-1">
              <li>全10競馬場の主要距離データ作成</li>
              <li>高低断面図の座標データ入力</li>
              <li>脚質別勝率の算出</li>
            </ul>
          </div>
          <div>
            <h3 className="font-bold text-green-700 mb-2">機能拡張</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-1">
              <li>天気API連携（気象庁API）</li>
              <li>風向きと直線方角の照合</li>
              <li>リアルタイム馬場状態表示</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
