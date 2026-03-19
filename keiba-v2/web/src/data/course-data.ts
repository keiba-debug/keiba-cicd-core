import type { CourseInfo } from '@/components/course-card';

/**
 * 全コース馬場分析データ
 * ソース: analyze_baba_report.py [17] コース別内有利度ランキング
 * データ: 2021-2026, 229,343エントリ
 */
export const ALL_COURSES: CourseInfo[] = [
  // =====================================================
  // 東京
  // =====================================================
  {
    trackName: '東京', surface: '芝', distanceMeters: 1400, turn: '左',
    courseGeometry: { straightLengthM: 525.9, elevationDiffM: 2.7, cornerCount: 2 },
    babaAnalysis: {
      firstCornerDistM: 540, firstCornerClass: '長(450m~)',
      sampleSize: 3690, innerTop3Pct: 18.2, outerTop3Pct: 22.0,
      innerAdvantage: -3.7, frontRunnerTop3Pct: 28.7, styleAdvantage: -14.1,
    },
  },
  {
    trackName: '東京', surface: '芝', distanceMeters: 1600, turn: '左',
    courseGeometry: { straightLengthM: 525.9, elevationDiffM: 2.7, cornerCount: 2 },
    babaAnalysis: {
      firstCornerDistM: 540, firstCornerClass: '長(450m~)',
      sampleSize: 4724, innerTop3Pct: 22.6, outerTop3Pct: 22.4,
      innerAdvantage: 0.2, frontRunnerTop3Pct: 30.9, styleAdvantage: -14.4,
    },
  },
  {
    trackName: '東京', surface: '芝', distanceMeters: 1800, turn: '左',
    courseGeometry: { straightLengthM: 525.9, elevationDiffM: 2.7, cornerCount: 4 },
    babaAnalysis: {
      firstCornerDistM: 340, firstCornerClass: '短(250-350m)',
      sampleSize: 3597, innerTop3Pct: 22.8, outerTop3Pct: 23.1,
      innerAdvantage: -0.3, frontRunnerTop3Pct: 32.4, styleAdvantage: -14.2,
    },
  },
  {
    trackName: '東京', surface: '芝', distanceMeters: 2000, turn: '左',
    courseGeometry: { straightLengthM: 525.9, elevationDiffM: 2.7, cornerCount: 4 },
    babaAnalysis: {
      firstCornerDistM: 540, firstCornerClass: '長(450m~)',
      sampleSize: 2363, innerTop3Pct: 25.5, outerTop3Pct: 24.9,
      innerAdvantage: 0.6, frontRunnerTop3Pct: 34.1, styleAdvantage: -9.8,
    },
  },
  {
    trackName: '東京', surface: '芝', distanceMeters: 2400, turn: '左',
    courseGeometry: { straightLengthM: 525.9, elevationDiffM: 2.7, cornerCount: 4, totalLengthM: 2083.1 },
    straightDirection: { runDirection: '東→西', headwindDirection: '西', tailwindDirection: '東' },
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 1533, innerTop3Pct: 23.1, outerTop3Pct: 25.7,
      innerAdvantage: -2.5, frontRunnerTop3Pct: 28.7, styleAdvantage: -8.0,
    },
  },
  {
    trackName: '東京', surface: 'ダート', distanceMeters: 1300, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 150, firstCornerClass: '超短(~250m)',
      sampleSize: 1762, innerTop3Pct: 20.8, outerTop3Pct: 19.4,
      innerAdvantage: 1.5, frontRunnerTop3Pct: 34.4, styleAdvantage: -19.8,
    },
  },
  {
    trackName: '東京', surface: 'ダート', distanceMeters: 1400, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 270, firstCornerClass: '短(250-350m)',
      sampleSize: 6882, innerTop3Pct: 17.9, outerTop3Pct: 20.5,
      innerAdvantage: -2.6, frontRunnerTop3Pct: 34.1, styleAdvantage: -18.2,
    },
  },
  {
    trackName: '東京', surface: 'ダート', distanceMeters: 1600, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 470, firstCornerClass: '長(450m~)',
      sampleSize: 7956, innerTop3Pct: 17.5, outerTop3Pct: 23.1,
      innerAdvantage: -5.5, frontRunnerTop3Pct: 32.5, styleAdvantage: -15.4,
    },
  },
  {
    trackName: '東京', surface: 'ダート', distanceMeters: 2100, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 2648, innerTop3Pct: 19.9, outerTop3Pct: 21.0,
      innerAdvantage: -1.2, frontRunnerTop3Pct: 29.4, styleAdvantage: -13.5,
    },
  },
  // =====================================================
  // 中山
  // =====================================================
  {
    trackName: '中山', surface: '芝', distanceMeters: 1200, turn: '右',
    courseGeometry: { straightLengthM: 310, elevationDiffM: 5.3, cornerCount: 4 },
    straightDirection: { runDirection: '南南西→北北東', headwindDirection: '北北東', tailwindDirection: '南南西' },
    babaAnalysis: {
      firstCornerDistM: 200, firstCornerClass: '超短(~250m)',
      sampleSize: 2458, innerTop3Pct: 25.2, outerTop3Pct: 17.4,
      innerAdvantage: 7.9, frontRunnerTop3Pct: 38.0, styleAdvantage: -21.6,
    },
  },
  {
    trackName: '中山', surface: '芝', distanceMeters: 1600, turn: '右',
    courseVariant: '外回り',
    courseGeometry: { straightLengthM: 310, elevationDiffM: 5.3, cornerCount: 4 },
    babaAnalysis: {
      firstCornerDistM: 250, firstCornerClass: '超短(~250m)',
      sampleSize: 4544, innerTop3Pct: 23.1, outerTop3Pct: 18.7,
      innerAdvantage: 4.3, frontRunnerTop3Pct: 34.2, styleAdvantage: -16.4,
    },
  },
  {
    trackName: '中山', surface: '芝', distanceMeters: 1800, turn: '右',
    courseGeometry: { straightLengthM: 310, elevationDiffM: 5.3, cornerCount: 4 },
    babaAnalysis: {
      firstCornerDistM: 460, firstCornerClass: '中(350-450m)',
      sampleSize: 2354, innerTop3Pct: 24.6, outerTop3Pct: 21.3,
      innerAdvantage: 3.3, frontRunnerTop3Pct: 34.0, styleAdvantage: -16.5,
    },
  },
  {
    trackName: '中山', surface: '芝', distanceMeters: 2000, turn: '右',
    courseVariant: '内回り',
    courseGeometry: { straightLengthM: 310, elevationDiffM: 5.3, cornerCount: 4, courseWidthM: '20-32m', totalLengthM: 1667.1 },
    straightDirection: { runDirection: '南南西→北北東', headwindDirection: '北北東', tailwindDirection: '南南西' },
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
        { distanceFromGoalM: 1667, elevationM: 2.0, landmark: 'スタート' },
      ],
      keyFeatures: [
        { position: 'ゴール前180m-70m', description: '中山名物の急坂（高低差2.2m、最大勾配2.24%・JRA最大）' },
        { position: '2コーナー手前', description: '最高到達点（+2.8m）' },
      ],
    },
    babaAnalysis: {
      firstCornerDistM: 260, firstCornerClass: '短(250-350m)',
      sampleSize: 3573, innerTop3Pct: 20.8, outerTop3Pct: 21.6,
      innerAdvantage: -0.7, frontRunnerTop3Pct: 30.7, styleAdvantage: -14.4,
    },
  },
  {
    trackName: '中山', surface: '芝', distanceMeters: 2200, turn: '右',
    courseGeometry: { straightLengthM: 310, elevationDiffM: 5.3, cornerCount: 4 },
    babaAnalysis: {
      firstCornerDistM: 460, firstCornerClass: '中(350-450m)',
      sampleSize: 1222, innerTop3Pct: 21.5, outerTop3Pct: 21.3,
      innerAdvantage: 0.3, frontRunnerTop3Pct: 27.6, styleAdvantage: -9.2,
    },
  },
  {
    trackName: '中山', surface: '芝', distanceMeters: 2500, turn: '右',
    courseGeometry: { straightLengthM: 310, elevationDiffM: 5.3, cornerCount: 4 },
    babaAnalysis: {
      firstCornerDistM: 260, firstCornerClass: '短(250-350m)',
      sampleSize: 663, innerTop3Pct: 21.8, outerTop3Pct: 21.8,
      innerAdvantage: 0.0, frontRunnerTop3Pct: 30.8, styleAdvantage: -11.4,
    },
  },
  {
    trackName: '中山', surface: 'ダート', distanceMeters: 1200, turn: '右',
    courseGeometry: { straightLengthM: 308, elevationDiffM: 4.5, cornerCount: 4, totalLengthM: 1493 },
    straightDirection: { runDirection: '南南西→北北東', headwindDirection: '北北東', tailwindDirection: '南南西' },
    babaAnalysis: {
      firstCornerDistM: 250, firstCornerClass: '超短(~250m)',
      sampleSize: 9737, innerTop3Pct: 17.4, outerTop3Pct: 21.4,
      innerAdvantage: -3.9, frontRunnerTop3Pct: 38.7, styleAdvantage: -21.3,
      conditionBias: [
        { label: '乾燥(<8%)', sampleSize: 2018, innerAdvantage: -3.5, styleAdvantage: -16.8 },
        { label: '標準(8-12%)', sampleSize: 2540, innerAdvantage: -3.0, styleAdvantage: -22.3 },
        { label: '湿潤(>=12%)', sampleSize: 3872, innerAdvantage: -4.5, styleAdvantage: -20.8 },
      ],
    },
  },
  {
    trackName: '中山', surface: 'ダート', distanceMeters: 1800, turn: '右',
    courseGeometry: { straightLengthM: 308, elevationDiffM: 4.5, cornerCount: 4 },
    babaAnalysis: {
      firstCornerDistM: 450, firstCornerClass: '中(350-450m)',
      sampleSize: 10152, innerTop3Pct: 18.0, outerTop3Pct: 22.7,
      innerAdvantage: -4.7, frontRunnerTop3Pct: 35.9, styleAdvantage: -15.9,
      conditionBias: [
        { label: '湿潤', sampleSize: 3872, innerAdvantage: -8.0 },
        { label: '標準', sampleSize: 2540, innerAdvantage: -4.4 },
        { label: '乾燥', sampleSize: 2018, innerAdvantage: -3.3 },
      ],
    },
  },
  // =====================================================
  // 阪神
  // =====================================================
  {
    trackName: '阪神', surface: '芝', distanceMeters: 1200, turn: '右',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 1215, innerTop3Pct: 28.4, outerTop3Pct: 19.6,
      innerAdvantage: 8.8, frontRunnerTop3Pct: 40.2, styleAdvantage: -18.0,
    },
  },
  {
    trackName: '阪神', surface: '芝', distanceMeters: 1400, turn: '右',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 2141, innerTop3Pct: 25.5, outerTop3Pct: 19.0,
      innerAdvantage: 6.5, frontRunnerTop3Pct: 32.9, styleAdvantage: -16.3,
    },
  },
  {
    trackName: '阪神', surface: '芝', distanceMeters: 1600, turn: '右',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 450, firstCornerClass: '中(350-450m)',
      sampleSize: 3330, innerTop3Pct: 24.4, outerTop3Pct: 21.0,
      innerAdvantage: 3.4, frontRunnerTop3Pct: 30.4, styleAdvantage: -12.6,
    },
  },
  {
    trackName: '阪神', surface: '芝', distanceMeters: 1800, turn: '右',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 2088, innerTop3Pct: 27.7, outerTop3Pct: 24.2,
      innerAdvantage: 3.5, frontRunnerTop3Pct: 28.8, styleAdvantage: -9.9,
    },
  },
  {
    trackName: '阪神', surface: '芝', distanceMeters: 2000, turn: '右',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 450, firstCornerClass: '中(350-450m)',
      sampleSize: 2192, innerTop3Pct: 26.9, outerTop3Pct: 24.3,
      innerAdvantage: 2.7, frontRunnerTop3Pct: 33.4, styleAdvantage: -10.4,
    },
  },
  {
    trackName: '阪神', surface: '芝', distanceMeters: 2200, turn: '右',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 591, innerTop3Pct: 25.7, outerTop3Pct: 23.3,
      innerAdvantage: 2.4, frontRunnerTop3Pct: 24.5, styleAdvantage: 0.2,
    },
  },
  {
    trackName: '阪神', surface: '芝', distanceMeters: 2400, turn: '右',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 440, firstCornerClass: '中(350-450m)',
      sampleSize: 749, innerTop3Pct: 29.1, outerTop3Pct: 29.1,
      innerAdvantage: 0.0, frontRunnerTop3Pct: 37.4, styleAdvantage: -14.8,
    },
  },
  {
    trackName: '阪神', surface: 'ダート', distanceMeters: 1200, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 270, firstCornerClass: '短(250-350m)',
      sampleSize: 4150, innerTop3Pct: 18.3, outerTop3Pct: 21.5,
      innerAdvantage: -3.1, frontRunnerTop3Pct: 40.0, styleAdvantage: -23.6,
    },
  },
  {
    trackName: '阪神', surface: 'ダート', distanceMeters: 1400, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 460, firstCornerClass: '長(450m~)',
      sampleSize: 5011, innerTop3Pct: 17.2, outerTop3Pct: 22.8,
      innerAdvantage: -5.6, frontRunnerTop3Pct: 34.8, styleAdvantage: -18.8,
    },
  },
  {
    trackName: '阪神', surface: 'ダート', distanceMeters: 1800, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 260, firstCornerClass: '短(250-350m)',
      sampleSize: 6796, innerTop3Pct: 21.9, outerTop3Pct: 25.6,
      innerAdvantage: -3.7, frontRunnerTop3Pct: 38.6, styleAdvantage: -17.1,
    },
  },
  {
    trackName: '阪神', surface: 'ダート', distanceMeters: 2000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 460, firstCornerClass: '長(450m~)',
      sampleSize: 1125, innerTop3Pct: 21.3, outerTop3Pct: 26.8,
      innerAdvantage: -5.5, frontRunnerTop3Pct: 33.6, styleAdvantage: -14.2,
    },
  },
  // =====================================================
  // 京都
  // =====================================================
  {
    trackName: '京都', surface: '芝', distanceMeters: 1200, turn: '右',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 970, innerTop3Pct: 22.3, outerTop3Pct: 19.6,
      innerAdvantage: 2.6, frontRunnerTop3Pct: 34.0, styleAdvantage: -22.4,
    },
  },
  {
    trackName: '京都', surface: '芝', distanceMeters: 1400, turn: '右',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 400, firstCornerClass: '中(350-450m)',
      sampleSize: 1350, innerTop3Pct: 24.4, outerTop3Pct: 20.8,
      innerAdvantage: 3.6, frontRunnerTop3Pct: 31.8, styleAdvantage: -18.3,
    },
  },
  {
    trackName: '京都', surface: '芝', distanceMeters: 1600, turn: '右',
    courseVariant: '外回り',
    courseGeometry: { straightLengthM: 403.7, elevationDiffM: 4.3, cornerCount: 4, courseWidthM: '28-38m', totalLengthM: 1894.3 },
    straightDirection: { runDirection: '南西→北東', headwindDirection: '北東', tailwindDirection: '南西' },
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
        { distanceFromGoalM: 1894, elevationM: 0.0, landmark: 'スタート' },
      ],
      keyFeatures: [
        { position: '3コーナー', description: '京都名物「淀の坂」（頂上・高低差4.3m・JRA2位）' },
        { position: '3C→4C', description: '一気に下るレイアウト、惰性をつけて直線へ' },
      ],
    },
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 2202, innerTop3Pct: 19.6, outerTop3Pct: 24.6,
      innerAdvantage: -5.0, frontRunnerTop3Pct: 33.7, styleAdvantage: -15.6,
    },
  },
  {
    trackName: '京都', surface: '芝', distanceMeters: 1800, turn: '右',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 400, firstCornerClass: '中(350-450m)',
      sampleSize: 1390, innerTop3Pct: 27.5, outerTop3Pct: 23.5,
      innerAdvantage: 4.0, frontRunnerTop3Pct: 32.4, styleAdvantage: -14.1,
    },
  },
  {
    trackName: '京都', surface: '芝', distanceMeters: 2000, turn: '右',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 1488, innerTop3Pct: 26.8, outerTop3Pct: 26.2,
      innerAdvantage: 0.6, frontRunnerTop3Pct: 31.9, styleAdvantage: -7.2,
    },
  },
  {
    trackName: '京都', surface: '芝', distanceMeters: 2200, turn: '右',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 400, firstCornerClass: '中(350-450m)',
      sampleSize: 522, innerTop3Pct: 30.7, outerTop3Pct: 23.5,
      innerAdvantage: 7.2, frontRunnerTop3Pct: 36.3, styleAdvantage: -16.8,
    },
  },
  {
    trackName: '京都', surface: '芝', distanceMeters: 2400, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 479, innerTop3Pct: 27.3, outerTop3Pct: 23.3,
      innerAdvantage: 4.0, frontRunnerTop3Pct: 28.7, styleAdvantage: -14.3,
    },
  },
  {
    trackName: '京都', surface: 'ダート', distanceMeters: 1200, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 2539, innerTop3Pct: 17.3, outerTop3Pct: 24.6,
      innerAdvantage: -7.3, frontRunnerTop3Pct: 37.4, styleAdvantage: -20.1,
    },
  },
  {
    trackName: '京都', surface: 'ダート', distanceMeters: 1400, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 420, firstCornerClass: '中(350-450m)',
      sampleSize: 3017, innerTop3Pct: 18.9, outerTop3Pct: 21.2,
      innerAdvantage: -2.3, frontRunnerTop3Pct: 38.0, styleAdvantage: -19.5,
    },
  },
  {
    trackName: '京都', surface: 'ダート', distanceMeters: 1800, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 250, firstCornerClass: '超短(~250m)',
      sampleSize: 4232, innerTop3Pct: 22.1, outerTop3Pct: 24.9,
      innerAdvantage: -2.8, frontRunnerTop3Pct: 37.4, styleAdvantage: -15.7,
    },
  },
  {
    trackName: '京都', surface: 'ダート', distanceMeters: 1900, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 1018, innerTop3Pct: 23.7, outerTop3Pct: 22.8,
      innerAdvantage: 0.9, frontRunnerTop3Pct: 28.9, styleAdvantage: -11.0,
    },
  },
  // =====================================================
  // 中京
  // =====================================================
  {
    trackName: '中京', surface: '芝', distanceMeters: 1200, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 1682, innerTop3Pct: 24.2, outerTop3Pct: 14.9,
      innerAdvantage: 9.3, frontRunnerTop3Pct: 32.3, styleAdvantage: -17.8,
    },
  },
  {
    trackName: '中京', surface: '芝', distanceMeters: 1400, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 510, firstCornerClass: '長(450m~)',
      sampleSize: 2412, innerTop3Pct: 22.7, outerTop3Pct: 17.0,
      innerAdvantage: 5.8, frontRunnerTop3Pct: 31.1, styleAdvantage: -15.7,
    },
  },
  {
    trackName: '中京', surface: '芝', distanceMeters: 1600, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 2914, innerTop3Pct: 24.8, outerTop3Pct: 21.3,
      innerAdvantage: 3.5, frontRunnerTop3Pct: 34.3, styleAdvantage: -17.6,
    },
  },
  {
    trackName: '中京', surface: '芝', distanceMeters: 2000, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 3534, innerTop3Pct: 27.0, outerTop3Pct: 23.0,
      innerAdvantage: 4.0, frontRunnerTop3Pct: 34.7, styleAdvantage: -13.1,
    },
  },
  {
    trackName: '中京', surface: '芝', distanceMeters: 2200, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 1415, innerTop3Pct: 26.3, outerTop3Pct: 22.3,
      innerAdvantage: 4.0, frontRunnerTop3Pct: 26.7, styleAdvantage: -8.4,
    },
  },
  {
    trackName: '中京', surface: 'ダート', distanceMeters: 1200, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 3441, innerTop3Pct: 20.8, outerTop3Pct: 20.3,
      innerAdvantage: 0.5, frontRunnerTop3Pct: 39.1, styleAdvantage: -19.6,
    },
  },
  {
    trackName: '中京', surface: 'ダート', distanceMeters: 1400, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 510, firstCornerClass: '長(450m~)',
      sampleSize: 4771, innerTop3Pct: 18.3, outerTop3Pct: 22.3,
      innerAdvantage: -4.0, frontRunnerTop3Pct: 34.6, styleAdvantage: -17.2,
    },
  },
  {
    trackName: '中京', surface: 'ダート', distanceMeters: 1800, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 5869, innerTop3Pct: 22.7, outerTop3Pct: 23.9,
      innerAdvantage: -1.2, frontRunnerTop3Pct: 37.6, styleAdvantage: -15.2,
    },
  },
  {
    trackName: '中京', surface: 'ダート', distanceMeters: 1900, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 410, firstCornerClass: '中(350-450m)',
      sampleSize: 1883, innerTop3Pct: 22.8, outerTop3Pct: 24.0,
      innerAdvantage: -1.1, frontRunnerTop3Pct: 34.5, styleAdvantage: -13.4,
    },
  },
  // =====================================================
  // 新潟
  // =====================================================
  {
    trackName: '新潟', surface: '芝', distanceMeters: 1200, turn: '左',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 440, firstCornerClass: '中(350-450m)',
      sampleSize: 1437, innerTop3Pct: 14.6, outerTop3Pct: 22.7,
      innerAdvantage: -8.0, frontRunnerTop3Pct: 31.3, styleAdvantage: -17.3,
    },
  },
  {
    trackName: '新潟', surface: '芝', distanceMeters: 1400, turn: '左',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 450, firstCornerClass: '中(350-450m)',
      sampleSize: 1851, innerTop3Pct: 19.0, outerTop3Pct: 19.9,
      innerAdvantage: -0.9, frontRunnerTop3Pct: 31.1, styleAdvantage: -13.6,
    },
  },
  {
    trackName: '新潟', surface: '芝', distanceMeters: 1600, turn: '左',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 2026, innerTop3Pct: 19.3, outerTop3Pct: 21.9,
      innerAdvantage: -2.6, frontRunnerTop3Pct: 29.0, styleAdvantage: -17.2,
    },
  },
  {
    trackName: '新潟', surface: '芝', distanceMeters: 1800, turn: '左',
    courseVariant: '内回り',
    babaAnalysis: {
      firstCornerDistM: 250, firstCornerClass: '超短(~250m)',
      sampleSize: 2266, innerTop3Pct: 21.0, outerTop3Pct: 22.6,
      innerAdvantage: -1.6, frontRunnerTop3Pct: 29.9, styleAdvantage: -10.1,
    },
  },
  {
    trackName: '新潟', surface: '芝', distanceMeters: 2000, turn: '左',
    courseVariant: '外回り',
    babaAnalysis: {
      firstCornerDistM: 450, firstCornerClass: '中(350-450m)',
      sampleSize: 1789, innerTop3Pct: 21.5, outerTop3Pct: 23.0,
      innerAdvantage: -1.4, frontRunnerTop3Pct: 24.6, styleAdvantage: -9.2,
    },
  },
  {
    trackName: '新潟', surface: 'ダート', distanceMeters: 1200, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 380, firstCornerClass: '中(350-450m)',
      sampleSize: 4541, innerTop3Pct: 19.3, outerTop3Pct: 22.6,
      innerAdvantage: -3.4, frontRunnerTop3Pct: 45.9, styleAdvantage: -25.7,
    },
  },
  {
    trackName: '新潟', surface: 'ダート', distanceMeters: 1800, turn: '左',
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 5342, innerTop3Pct: 19.6, outerTop3Pct: 22.5,
      innerAdvantage: -2.9, frontRunnerTop3Pct: 38.0, styleAdvantage: -17.1,
    },
  },
  // =====================================================
  // 福島
  // =====================================================
  {
    trackName: '福島', surface: '芝', distanceMeters: 1200, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 320, firstCornerClass: '短(250-350m)',
      sampleSize: 3644, innerTop3Pct: 24.3, outerTop3Pct: 20.4,
      innerAdvantage: 3.9, frontRunnerTop3Pct: 36.8, styleAdvantage: -21.4,
    },
  },
  {
    trackName: '福島', surface: '芝', distanceMeters: 1800, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 380, firstCornerClass: '中(350-450m)',
      sampleSize: 2132, innerTop3Pct: 22.3, outerTop3Pct: 18.9,
      innerAdvantage: 3.4, frontRunnerTop3Pct: 31.5, styleAdvantage: -16.5,
    },
  },
  {
    trackName: '福島', surface: '芝', distanceMeters: 2000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 1687, innerTop3Pct: 21.0, outerTop3Pct: 19.4,
      innerAdvantage: 1.6, frontRunnerTop3Pct: 24.9, styleAdvantage: -8.2,
    },
  },
  {
    trackName: '福島', surface: '芝', distanceMeters: 2600, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 756, innerTop3Pct: 23.7, outerTop3Pct: 21.6,
      innerAdvantage: 2.1, frontRunnerTop3Pct: 23.4, styleAdvantage: -6.7,
    },
  },
  {
    trackName: '福島', surface: 'ダート', distanceMeters: 1150, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 300, firstCornerClass: '短(250-350m)',
      sampleSize: 2535, innerTop3Pct: 20.7, outerTop3Pct: 19.9,
      innerAdvantage: 0.9, frontRunnerTop3Pct: 46.1, styleAdvantage: -25.9,
    },
  },
  {
    trackName: '福島', surface: 'ダート', distanceMeters: 1700, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 360, firstCornerClass: '中(350-450m)',
      sampleSize: 3797, innerTop3Pct: 20.9, outerTop3Pct: 21.9,
      innerAdvantage: -1.0, frontRunnerTop3Pct: 36.8, styleAdvantage: -17.2,
    },
  },
  // =====================================================
  // 小倉
  // =====================================================
  {
    trackName: '小倉', surface: '芝', distanceMeters: 1200, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 6017, innerTop3Pct: 18.4, outerTop3Pct: 20.8,
      innerAdvantage: -2.4, frontRunnerTop3Pct: 31.5, styleAdvantage: -15.5,
    },
  },
  {
    trackName: '小倉', surface: '芝', distanceMeters: 1800, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 320, firstCornerClass: '短(250-350m)',
      sampleSize: 3007, innerTop3Pct: 21.8, outerTop3Pct: 23.9,
      innerAdvantage: -2.2, frontRunnerTop3Pct: 30.6, styleAdvantage: -12.9,
    },
  },
  {
    trackName: '小倉', surface: '芝', distanceMeters: 2000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 2709, innerTop3Pct: 23.4, outerTop3Pct: 22.1,
      innerAdvantage: 1.3, frontRunnerTop3Pct: 25.0, styleAdvantage: -7.1,
    },
  },
  {
    trackName: '小倉', surface: 'ダート', distanceMeters: 1000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 200, firstCornerClass: '超短(~250m)',
      sampleSize: 2182, innerTop3Pct: 25.2, outerTop3Pct: 22.3,
      innerAdvantage: 2.9, frontRunnerTop3Pct: 51.5, styleAdvantage: -28.9,
      conditionBias: [
        { label: '乾燥', sampleSize: 819, innerAdvantage: 3.2, styleAdvantage: -15.2 },
        { label: '標準', sampleSize: 690, innerAdvantage: 2.0, styleAdvantage: -15.3 },
        { label: '湿潤', sampleSize: 119, innerAdvantage: -2.5, styleAdvantage: -21.0 },
      ],
    },
  },
  {
    trackName: '小倉', surface: 'ダート', distanceMeters: 1700, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 5235, innerTop3Pct: 20.6, outerTop3Pct: 20.7,
      innerAdvantage: -0.1, frontRunnerTop3Pct: 34.0, styleAdvantage: -14.1,
    },
  },
  // =====================================================
  // 札幌
  // =====================================================
  {
    trackName: '札幌', surface: '芝', distanceMeters: 1200, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 1806, innerTop3Pct: 21.3, outerTop3Pct: 23.5,
      innerAdvantage: -2.2, frontRunnerTop3Pct: 34.3, styleAdvantage: -18.2,
    },
  },
  {
    trackName: '札幌', surface: '芝', distanceMeters: 1500, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 1257, innerTop3Pct: 24.3, outerTop3Pct: 24.5,
      innerAdvantage: -0.2, frontRunnerTop3Pct: 35.7, styleAdvantage: -14.8,
    },
  },
  {
    trackName: '札幌', surface: '芝', distanceMeters: 1800, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 1126, innerTop3Pct: 30.0, outerTop3Pct: 29.1,
      innerAdvantage: 1.0, frontRunnerTop3Pct: 37.8, styleAdvantage: -17.7,
    },
  },
  {
    trackName: '札幌', surface: '芝', distanceMeters: 2000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 310, firstCornerClass: '短(250-350m)',
      sampleSize: 1474, innerTop3Pct: 22.9, outerTop3Pct: 22.1,
      innerAdvantage: 0.8, frontRunnerTop3Pct: 27.8, styleAdvantage: -9.2,
    },
  },
  {
    trackName: '札幌', surface: 'ダート', distanceMeters: 1000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 200, firstCornerClass: '超短(~250m)',
      sampleSize: 996, innerTop3Pct: 21.2, outerTop3Pct: 30.0,
      innerAdvantage: -8.8, frontRunnerTop3Pct: 47.7, styleAdvantage: -25.7,
    },
  },
  {
    trackName: '札幌', surface: 'ダート', distanceMeters: 1700, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 360, firstCornerClass: '中(350-450m)',
      sampleSize: 3251, innerTop3Pct: 20.3, outerTop3Pct: 24.6,
      innerAdvantage: -4.3, frontRunnerTop3Pct: 31.0, styleAdvantage: -10.1,
    },
  },
  // =====================================================
  // 函館
  // =====================================================
  {
    trackName: '函館', surface: '芝', distanceMeters: 1200, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 280, firstCornerClass: '短(250-350m)',
      sampleSize: 2219, innerTop3Pct: 25.4, outerTop3Pct: 24.0,
      innerAdvantage: 1.4, frontRunnerTop3Pct: 34.3, styleAdvantage: -20.2,
    },
  },
  {
    trackName: '函館', surface: '芝', distanceMeters: 1800, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 330, firstCornerClass: '短(250-350m)',
      sampleSize: 1001, innerTop3Pct: 26.9, outerTop3Pct: 22.7,
      innerAdvantage: 4.3, frontRunnerTop3Pct: 31.8, styleAdvantage: -9.3,
    },
  },
  {
    trackName: '函館', surface: '芝', distanceMeters: 2000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 250, firstCornerClass: '超短(~250m)',
      sampleSize: 720, innerTop3Pct: 21.0, outerTop3Pct: 21.2,
      innerAdvantage: -0.2, frontRunnerTop3Pct: 27.8, styleAdvantage: -4.2,
    },
  },
  {
    trackName: '函館', surface: 'ダート', distanceMeters: 1000, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 200, firstCornerClass: '超短(~250m)',
      sampleSize: 909, innerTop3Pct: 28.2, outerTop3Pct: 27.5,
      innerAdvantage: 0.7, frontRunnerTop3Pct: 56.7, styleAdvantage: -36.4,
    },
  },
  {
    trackName: '函館', surface: 'ダート', distanceMeters: 1700, turn: '右',
    babaAnalysis: {
      firstCornerDistM: 350, firstCornerClass: '短(250-350m)',
      sampleSize: 1813, innerTop3Pct: 27.5, outerTop3Pct: 25.0,
      innerAdvantage: 2.5, frontRunnerTop3Pct: 38.9, styleAdvantage: -16.1,
    },
  },
];

// ユーティリティ
export const VENUES = ['東京', '中山', '阪神', '京都', '中京', '新潟', '福島', '小倉', '札幌', '函館'] as const;
export type Venue = typeof VENUES[number];

// =====================================================
// 競馬場概要情報（競馬場コース事典2 + course_master.json ベース）
// =====================================================
export interface VenueInfo {
  name: string;
  nameEn: string;
  region: '関東' | '関西' | '中部' | '北海道' | '東北' | '九州';
  direction: '右' | '左';
  grassType: '野芝' | '洋芝' | '野芝+洋芝';
  turfStraight: number;    // 芝直線距離(m)
  dirtStraight: number;    // ダート直線距離(m)
  turfCircumference: number; // 芝1周(m)
  heightDiff: number;      // 高低差(m)
  hasSlope: boolean;       // 急坂有無
  courseType: 'large' | 'medium' | 'small';
  avgTimeRank: number;     // 走破タイムランク(辞典の7.5等)
  characteristics: string; // 短い特徴文
  turfNote: string;        // 芝コースの特徴説明
  dirtNote: string;        // ダートコースの特徴説明
  trackConditionNote: string; // 馬場状態の特記事項
  tags: string[];          // 特徴タグ
  color: string;           // テーマカラー(hex)
}

export const VENUE_INFO: Record<string, VenueInfo> = {
  '札幌': {
    name: '札幌', nameEn: 'SAPPORO', region: '北海道', direction: '右',
    grassType: '洋芝', turfStraight: 266.1, dirtStraight: 264.0,
    turfCircumference: 1640.9, heightDiff: 0.7, hasSlope: false,
    courseType: 'small', avgTimeRank: 7.5,
    characteristics: '洋芝、終始平坦、楕円形が特徴',
    turfNote: '平坦で直線短い。コーナーが緩くスピード持続型。洋芝でパワー要求もあり、ディープ産駒よりキングマンボ系が走りやすい。Aコース使用時は内外フラット、Bコースは外有利傾向。',
    dirtNote: 'コーナーの角度が急で位置取り重要。中距離は外枠からスムーズに脚を使える馬が有利。',
    trackConditionNote: '北海道開催の2場は基本「洋芝」を採用。寒さに強い洋芝は本州の野芝と異なり、クッション性が高くスタミナを要求する。',
    tags: ['洋芝', '平坦', '小回り', 'スピード持続'],
    color: '#1e88e5',
  },
  '函館': {
    name: '函館', nameEn: 'HAKODATE', region: '北海道', direction: '右',
    grassType: '洋芝', turfStraight: 262.1, dirtStraight: 260.3,
    turfCircumference: 1626.4, heightDiff: 3.5, hasSlope: true,
    courseType: 'small', avgTimeRank: 7.5,
    characteristics: '洋芝、大きな起伏、小回りが特徴',
    turfNote: 'JRA最短直線（262.1m）。逃げ先行が圧倒的有利。起伏のある洋芝小回りコースで、機動力やパワー、持続力が求められる。ディープ系よりもタフなコースを好むタイプ向き。',
    dirtNote: 'ダートも最短直線で先行絶対有利。中距離は外枠から脚を使える馬の回収率に注目。',
    trackConditionNote: '洋芝で「渋る」とパワー要求が増す。2025年施設リニューアル。',
    tags: ['洋芝', '起伏', 'JRA最短直線', '逃げ先行天国'],
    color: '#00897b',
  },
  '福島': {
    name: '福島', nameEn: 'FUKUSHIMA', region: '東北', direction: '右',
    grassType: '野芝+洋芝', turfStraight: 292.0, dirtStraight: 295.7,
    turfCircumference: 1600.0, heightDiff: 1.9, hasSlope: true,
    courseType: 'small', avgTimeRank: 6.0,
    characteristics: '小回り急坂、スパイラルカーブ',
    turfNote: '小回りでスパイラルカーブ採用。内枠先行有利だが、開催後半は芝の痛みで外差し傾向に変化。1200mは内有利が顕著。',
    dirtNote: '先行有利だが開催後半は差し有利に変化。1150mは逃げ先行が圧倒的。',
    trackConditionNote: '開催進行による馬場バイアス変化が大きい。序盤は内前有利→後半は外差し有利に。',
    tags: ['小回り', 'スパイラルカーブ', '内有利', '開催進行で変化'],
    color: '#f4511e',
  },
  '新潟': {
    name: '新潟', nameEn: 'NIIGATA', region: '中部', direction: '左',
    grassType: '野芝+洋芝', turfStraight: 358.7, dirtStraight: 353.9,
    turfCircumference: 2223.1, heightDiff: 0.7, hasSlope: false,
    courseType: 'large', avgTimeRank: 6.0,
    characteristics: '平坦、直線長い、直線1000mコースが特殊',
    turfNote: '外回りは直線が長く差し有利。内回りは小回りで先行有利。直線1000mはコーナーなしの特殊コースで馬場の内外によるバイアスが極端。',
    dirtNote: '平坦ダートで先行有利。直線そこそこで持続力要求。',
    trackConditionNote: '平坦のため馬場状態による変化は比較的少ない。',
    tags: ['平坦', '直線長い', '直線1000m', '外回り差し有利'],
    color: '#7cb342',
  },
  '東京': {
    name: '東京', nameEn: 'TOKYO', region: '関東', direction: '左',
    grassType: '野芝', turfStraight: 525.9, dirtStraight: 501.6,
    turfCircumference: 2083.1, heightDiff: 2.7, hasSlope: true,
    courseType: 'large', avgTimeRank: 8.0,
    characteristics: 'JRA最長直線、差し追込有効、実力差が出やすい',
    turfNote: 'JRA最長直線525.9m。直線に急坂があり実力差が出やすい。差し・追込が届く展開が多いが、超スローになると前残りも。コーナーが緩やかで隊列が整いやすい。',
    dirtNote: 'ダートでも直線が長くJRA唯一差し有利になれるコース。1600mは1角までの距離が長くポジション取りが重要。',
    trackConditionNote: '仮柵（A〜D）運用で内外の痛み差が開催進行で変化。秋の東京は馬場良好で高速。',
    tags: ['JRA最長直線', '急坂', '差し追込有効', '実力勝負'],
    color: '#5e35b1',
  },
  '中山': {
    name: '中山', nameEn: 'NAKAYAMA', region: '関東', direction: '右',
    grassType: '野芝', turfStraight: 310.0, dirtStraight: 308.0,
    turfCircumference: 1667.0, heightDiff: 5.3, hasSlope: true,
    courseType: 'small', avgTimeRank: 8.0,
    characteristics: 'JRA最大急坂＋小回り、先行有利、スタミナ要求',
    turfNote: '中山名物のゴール前急坂（高低差2.2m、最大勾配2.24%はJRA最大）。小回りで先行有利だがスタミナも要求。1200mは枠順の影響が特に大きく内枠圧倒的有利。',
    dirtNote: '先行有利。急坂で底力必要。1200mは外枠不利が顕著、1800mも外枠不利傾向。湿潤時さらに外枠不利に。',
    trackConditionNote: '急坂があるため、馬場が渋ると消耗が激しい。冬場は芝が枯れてパワー要求が増す。',
    tags: ['JRA最大急坂', '小回り', '先行有利', '高低差5.3m'],
    color: '#d81b60',
  },
  '中京': {
    name: '中京', nameEn: 'CHUKYO', region: '中部', direction: '左',
    grassType: '野芝+洋芝', turfStraight: 412.5, dirtStraight: 410.7,
    turfCircumference: 1705.9, heightDiff: 3.5, hasSlope: true,
    courseType: 'medium', avgTimeRank: 7.0,
    characteristics: '直線長め＋急坂、実力勝負になりやすい',
    turfNote: '直線412.5mは中規模場では長い部類。急坂もあり実力勝負になりやすい。1200mは内枠有利が顕著（+9.3pt）。長距離は差し有利傾向。',
    dirtNote: '急坂で先行勢がバテやすいがダートでは先行有利維持。1400mは1角距離が長く外枠不利。',
    trackConditionNote: '2025年に高速馬場化の傾向。コース改修後はバイアスが変わりつつある。',
    tags: ['直線長め', '急坂', '実力勝負', '1200m内有利'],
    color: '#ff8f00',
  },
  '京都': {
    name: '京都', nameEn: 'KYOTO', region: '関西', direction: '右',
    grassType: '野芝', turfStraight: 403.7, dirtStraight: 329.1,
    turfCircumference: 1894.3, heightDiff: 4.3, hasSlope: true,
    courseType: 'large', avgTimeRank: 7.5,
    characteristics: '淀の坂＋下り、外回り直線長い、2025年改修で高速化',
    turfNote: '3コーナーに京都名物「淀の坂」（高低差4.3m、JRA2位）。3C→4Cの下りで惰性をつけて直線に入る特徴的なレイアウト。外回り1600mは内枠不利（-5.0pt）。2200mは逆に内枠有利。',
    dirtNote: '先行有利。1-2月は馬場が湿り内枠有利傾向。1900mは1角が遠くポジション取りが重要。',
    trackConditionNote: '2025年改修後は高速馬場化。エアレーション・シャタリング実施で走破タイムが変化。',
    tags: ['淀の坂', '3C下り', '外回り直線長い', '2025改修'],
    color: '#c62828',
  },
  '阪神': {
    name: '阪神', nameEn: 'HANSHIN', region: '関西', direction: '右',
    grassType: '野芝', turfStraight: 473.6, dirtStraight: 352.7,
    turfCircumference: 2089.0, heightDiff: 1.8, hasSlope: true,
    courseType: 'large', avgTimeRank: 8.0,
    characteristics: '外回り直線長い、急坂で差し有利、内回りは先行有利',
    turfNote: '外回り直線473.6mは東京に次ぐ長さ。急坂があり差し有利に。内回りは1200m/1400mで内枠有利が顕著（+8.8pt/+6.5pt）。外回り2200m以上は差し追込有効。',
    dirtNote: '先行有利。砂かぶりで外枠やや有利。1400mは1角距離が長く外枠不利(-5.6pt)が目立つ。',
    trackConditionNote: '冬場の阪神は野芝が枯れてパワー要求。宝塚記念の時期は梅雨で馬場変化大。',
    tags: ['外回り直線長い', '急坂', '内回り先行有利', '外回り差し有利'],
    color: '#1565c0',
  },
  '小倉': {
    name: '小倉', nameEn: 'KOKURA', region: '九州', direction: '右',
    grassType: '野芝+洋芝', turfStraight: 293.0, dirtStraight: 291.3,
    turfCircumference: 1615.1, heightDiff: 3.0, hasSlope: true,
    courseType: 'small', avgTimeRank: 6.5,
    characteristics: '小回り平坦に近い、先行有利、開催進むとバイアス変化大',
    turfNote: '小回りで先行有利だが、直線は293mと福島より長い。1200mは外枠不利傾向あり。2000mは差しも届くようになる。開催が進むと内の芝が荒れて外差し有利に変化。',
    dirtNote: '先行有利。直線短く差し届きにくい。1000mは逃げ先行が圧倒的（top3率51.5%）。',
    trackConditionNote: '夏の小倉は芝の痛みが早い。連続開催で馬場バイアスが大きく変わる。',
    tags: ['小回り', '先行有利', '開催進行で変化', '夏の小倉'],
    color: '#e65100',
  },
};

// =====================================================
// コース別の狙い方・実践Tips（競馬場コース事典2 ベース）
// key: "場名-芝orダート-距離m" 例: "札幌-芝-1200"
// =====================================================
export interface CourseTip {
  headline: string;         // コース特徴の一行見出し
  description: string;      // コース解説（2-3文）
  tips: string[];           // 狙い方のポイント（箇条書き）
}

export const COURSE_TIPS: Record<string, CourseTip> = {
  // === 札幌 ===
  '札幌-芝-1200': {
    headline: 'Aコース時は逃げ先行馬が止まりづらい',
    description: '直線距離266.1mと短い軽量平坦コース。コーナーが緩く直線入口で馬群がバラけにくいので、内の差し馬が詰まりやすい。',
    tips: ['Aコースは外枠管理（内外フラット）', 'Bコースは外枠有利（1枠差は約18%）', '全体は逃げ先行有利'],
  },
  '札幌-芝-1500': {
    headline: 'コーナースタートで内枠有利が基本',
    description: '1,2コーナーポケットからスタートする典型的コーナースタートコース。内枠有利だが、Bコース使用時は外からでも差しが効く。',
    tips: ['Aコースは内枠先行有利', 'Bコースは外枠有利', '東京芝1400m級のスピード感'],
  },
  '札幌-芝-1800': {
    headline: '初角までが短く、前半は落ち着きやすい',
    description: '初角まで185.1mと短くスローペースになりやすい。逃げ先行馬が基本有利。コーナーが緩くペースが上がりにくいため、中団待機では差し切れない。',
    tips: ['逃げ先行有利', 'Bコースは外枠有利', '全体2着には7,8枠の差し馬'],
  },
  '札幌-芝-2000': {
    headline: '初角までの距離が長い為、枠の差はフラット',
    description: '初角まで385.1mと長くなり、枠順がポジション争いに影響しにくい。1800mと同様にスロー傾向だが、持続力のある差し馬も届く。',
    tips: ['逃げ先行&捲り（1,2着率53%）', '純差し追込のエピファネイア、サトノダイヤモンド系は上がり3F勝負'],
  },
  '札幌-ダート-1000': {
    headline: 'スピードで押し切りやすく、逃げ先行馬の回収率が高い',
    description: '向正面からスタートして直線を駆くワンターンコース。スピードで押し切りやすく逃げ先行馬が圧倒的有利。',
    tips: ['逃げ先行馬有利', '外枠有利（砂かぶり回避）', 'データ量の注目血統チェック'],
  },
  '札幌-ダート-1700': {
    headline: '緩いコーナーから長く脚を使える馬が有利',
    description: '直線264.3mと短いが、比較的緩いコーナーが続く構造。外枠からスムーズに長い脚を使える馬の回収率が高い。',
    tips: ['長馬場は外枠有利', '長馬場は内枠の外への持ち出し注意', '前走上がり3位以内'],
  },
  // === 函館 ===
  '函館-芝-1200': {
    headline: 'JRA最短直線で前有利の典型、1〜3着の7割が4角5番手以内',
    description: '直線262.1mはJRA最短。逃げ先行馬が止まらない典型コース。内枠先行有利が基本だが、Bコース時は外からでも間に合う。',
    tips: ['逃げ先行馬有利', '内枠有利', '洋芝パワー型を狙う'],
  },
  '函館-芝-1800': {
    headline: '前に行ける機動力のある馬が有利',
    description: '初角までの距離が短くスロー傾向。小回りのため好位を取れる器用な馬が有利。洋芝でスタミナも要求。',
    tips: ['先行馬有利', '内枠有利', '洋芝適性は必須'],
  },
  '函館-芝-2000': {
    headline: '向正面スタートでスローになりやすい',
    description: '向正面中間からスタートして1周半を走る。スローペースからの瞬発力勝負になりやすい。',
    tips: ['中枠〜先行馬有利（1,2着率53%）', '類似は阪神芝2000m', '上がり3F勝負'],
  },
  '函館-ダート-1000': {
    headline: 'スピードで押し切り、逃げ先行の回収率が非常に高い',
    description: 'JRA最短直線のダート1000m。逃げ先行の圧倒的優位は芝以上。',
    tips: ['逃げ先行馬有利', '外枠有利（砂かぶり回避）'],
  },
  '函館-ダート-1700': {
    headline: '外枠から長い脚を使える馬に注目',
    description: '小回りだが直線が短いため、コーナーでの位置取りが全て。外枠から好位を取れる馬の回収率に注目。',
    tips: ['長馬場は外枠有利', '前走上がり3位以内'],
  },
  // === 東京 ===
  '東京-芝-1400': {
    headline: '直線525.9mで差し追込も届くが、1角まで540mで先行争い激化',
    description: '1角までの距離が540mと長く先行争いが激化しやすい。直線が長いため差し追込も届くが、外枠不利傾向（-3.7pt）がある。',
    tips: ['外枠不利に注意（-3.7pt）', '差し追込も有効', 'ペースが上がりやすく持続力重要'],
  },
  '東京-芝-1600': {
    headline: '枠順フラット、マイル王道コース',
    description: '内外フラット（+0.2pt）でバイアスが少ない。直線長くスローからの瞬発力勝負にも、ハイペースの持続力勝負にもなる万能コース。',
    tips: ['枠順ほぼフラット', '瞬発力＋持続力のバランス型', 'NHKマイルC・安田記念の舞台'],
  },
  '東京-芝-1800': {
    headline: '1角まで340mで枠順の影響は小さい',
    description: '4コーナーのコースで1角まで340m。直線の長さで実力差が出やすいが、枠順の影響はほぼフラット。',
    tips: ['枠順フラット', '実力差が出やすい', '毎日王冠の舞台'],
  },
  '東京-芝-2000': {
    headline: '1角遠く枠順フラット、実力馬向き',
    description: '1角まで540mで枠の有利不利なし。直線の長さと坂で真の実力が問われる。天皇賞(秋)の舞台。',
    tips: ['枠順フラット', '差し追込有効', '急坂で底力必要'],
  },
  '東京-芝-2400': {
    headline: 'ダービーの舞台、直線の坂で実力差が出る',
    description: '日本ダービー・ジャパンカップの舞台。1角まで350mで外枠やや不利。3〜4角で仕掛けどころを問う名コース。',
    tips: ['外枠やや不利（-2.5pt）', '差し追込有効（-8.0pt差し有利度）', 'スタミナと瞬発力の両方必要'],
  },
  '東京-ダート-1300': {
    headline: '1角まで短く内枠先行有利',
    description: '1角まで150mと超短。内枠先行有利の典型的な短距離ダートコース。',
    tips: ['内枠先行有利（+1.5pt）', '逃げ先行top3率34.4%'],
  },
  '東京-ダート-1400': {
    headline: '1角まで270mで枠順差あり、外枠やや有利',
    description: 'フェブラリーSの裏舞台。1角まで270mで外枠有利傾向（-2.6pt内枠不利）。砂かぶりの影響大。',
    tips: ['外枠有利（-2.6pt内枠不利）', '先行有利だが差しも届く'],
  },
  '東京-ダート-1600': {
    headline: '1角まで470mで外枠不利が顕著、JRAダート最注目距離',
    description: 'フェブラリーSの舞台。1角まで470mと長いが外枠不利が最も顕著（-5.5pt）。ダートでも差しが有効な唯一のコース。',
    tips: ['外枠不利が顕著（-5.5pt）', 'ダートでも差し有効', 'フェブラリーS・ユニコーンSの舞台'],
  },
  '東京-ダート-2100': {
    headline: '中距離で枠順差は縮小、底力勝負',
    description: '長距離ダートで底力が問われる。枠順の影響は比較的小さい。',
    tips: ['枠順差は小さい（-1.2pt）', '先行有利だが差しも届く'],
  },
  // === 中山 ===
  '中山-芝-1200': {
    headline: '内枠圧倒有利＋先行天国、JRA屈指のバイアスコース',
    description: '1角まで200mの超短距離。内枠先行有利が最も顕著なコース（+7.9pt）。逃先top3率38.0%と先行天国。',
    tips: ['内枠圧倒有利（+7.9pt）', '逃げ先行天国', '外枠差し馬は割引き必須'],
  },
  '中山-芝-1600': {
    headline: '外回り使用も1角短く内有利、急坂で先行やや有利',
    description: '外回りだが1角まで250mと短い。急坂があるため先行馬でもスタミナ要求。内枠有利（+4.3pt）。',
    tips: ['内枠有利（+4.3pt）', '先行有利', '急坂でスタミナ要'],
  },
  '中山-芝-1800': {
    headline: '1角まで460mで枠の影響やや緩和',
    description: '1角まで460mあるため枠の差は緩和されるが、まだ内有利傾向（+3.3pt）。先行有利も健在。',
    tips: ['やや内有利（+3.3pt）', '先行有利', '中山記念の舞台'],
  },
  '中山-芝-2000': {
    headline: '内回り、枠順フラットで差しも有効',
    description: '内回り2000m。1角まで260mだが枠順はほぼフラット。差し馬も有効で、有馬記念とは異なるバイアス。',
    tips: ['枠順ほぼフラット', '差し有効', '弥生賞の舞台'],
  },
  '中山-芝-2200': {
    headline: '外回り長距離、差し有効で枠順フラット',
    description: '外回り2200m。枠順フラット、差し有利度-9.2ptで差し馬の活躍目立つ。',
    tips: ['枠順フラット', '差し有効'],
  },
  '中山-芝-2500': {
    headline: '有馬記念の舞台、内回り、スタミナ決戦',
    description: '有馬記念の舞台。1角まで260m、急坂を2回通過するタフなコース。スタミナと機動力が求められる。',
    tips: ['枠順フラット', '急坂2回通過でスタミナ勝負', '有馬記念の舞台'],
  },
  '中山-ダート-1200': {
    headline: '外枠不利が顕著、先行天国',
    description: '1角まで250mの超短距離ダート。外枠不利(-3.9pt)が目立ち、先行有利が圧倒的。湿潤時さらに外枠不利。',
    tips: ['外枠不利（-3.9pt）', '先行天国（top3率38.7%）', '湿潤時は外枠さらに不利'],
  },
  '中山-ダート-1800': {
    headline: '外枠不利が顕著、先行有利のタフなコース',
    description: '1角まで450m。外枠不利(-4.7pt)が顕著。湿潤時は外枠不利が-8.0ptまで拡大。急坂で底力必要。',
    tips: ['外枠不利（-4.7pt、湿潤時-8.0pt）', '先行有利', '急坂で底力必要'],
  },
  // === 阪神 ===
  '阪神-芝-1200': {
    headline: '内回り、内枠有利が極めて顕著',
    description: '内回り1200m。内枠有利が+8.8ptと全コースでも屈指の偏り。逃げ先行がtop3率40.2%と圧倒的。',
    tips: ['内枠有利（+8.8pt）', '逃げ先行圧倒', '外枠差し馬は大幅割引き'],
  },
  '阪神-芝-1400': {
    headline: '内回り、内枠有利が顕著',
    description: '内回り1400m。1角まで310mで内枠有利（+6.5pt）。先行有利のコース。',
    tips: ['内枠有利（+6.5pt）', '先行有利'],
  },
  '阪神-芝-1600': {
    headline: '外回り、直線長く差しも有効',
    description: '外回り1600mで直線473.6m。内有利傾向はあるが（+3.4pt）差しも有効。桜花賞・阪神JFの舞台。',
    tips: ['やや内有利（+3.4pt）', '差しも有効', '桜花賞の舞台'],
  },
  '阪神-芝-1800': {
    headline: '内回り、内枠有利で差しも届く',
    description: '内回り1800m。内枠有利（+3.5pt）だが差し有利度-9.9ptで差しも届く中距離。',
    tips: ['内枠有利（+3.5pt）', '差しも有効'],
  },
  '阪神-芝-2000': {
    headline: '外回り、実力勝負の名コース',
    description: '外回り2000m。大阪杯の舞台。内有利（+2.7pt）だが差しも有効。',
    tips: ['やや内有利（+2.7pt）', '差し有効', '大阪杯の舞台'],
  },
  '阪神-芝-2200': {
    headline: '内回り長距離、差し追込が最も有効',
    description: '内回り2200m。差し有利度+0.2ptとほぼフラット～差し有利の珍しいコース。宝塚記念の裏舞台。',
    tips: ['差し追込有効', '脚質バイアスなし'],
  },
  '阪神-芝-2400': {
    headline: '外回り長距離、枠順フラット',
    description: '外回り2400m。内外フラット。先行有利度は-14.8ptで先行やや有利だが差しも効く。',
    tips: ['枠順フラット', '先行やや有利'],
  },
  '阪神-ダート-1200': {
    headline: '外枠不利、逃げ先行天国',
    description: '1角まで270mで外枠不利(-3.1pt)。逃げ先行top3率40.0%と先行天国。',
    tips: ['外枠不利（-3.1pt）', '逃げ先行天国'],
  },
  '阪神-ダート-1400': {
    headline: '1角遠く外枠不利が最も顕著なダートコースの一つ',
    description: '1角まで460mだが外枠不利(-5.6pt)が非常に顕著。先行有利のコース。',
    tips: ['外枠不利が非常に顕著（-5.6pt）', '先行有利'],
  },
  '阪神-ダート-1800': {
    headline: '先行有利、外枠不利の典型的中距離ダート',
    description: '1角まで260mの短距離。外枠不利(-3.7pt)で先行有利。',
    tips: ['外枠不利（-3.7pt）', '先行有利（top3率38.6%）'],
  },
  '阪神-ダート-2000': {
    headline: '1角遠く外枠不利、差しも届く長距離ダート',
    description: '1角まで460m。外枠不利(-5.5pt)だが差しも有効な長距離ダート。',
    tips: ['外枠不利（-5.5pt）', '差しも有効'],
  },
  // === 京都 ===
  '京都-芝-1200': {
    headline: '内回り短距離、やや内有利で先行天国',
    description: '内回り1200m。内有利（+2.6pt）で逃先top3率34.0%。先行有利度-22.4ptと先行天国。',
    tips: ['やや内有利', '先行天国（-22.4pt）'],
  },
  '京都-芝-1400': {
    headline: '外回り、内有利傾向あり',
    description: '外回り1400m。内有利（+3.6pt）で先行有利。京都外回りだが距離が短いため差しは届きにくい。',
    tips: ['内有利（+3.6pt）', '先行有利'],
  },
  '京都-芝-1600': {
    headline: '外回り、内枠不利が顕著な異色コース',
    description: '外回り1600m。内枠不利(-5.0pt)が顕著で京都芝では珍しいパターン。淀の坂を越えてからの直線で差し馬も有効。',
    tips: ['内枠不利が顕著（-5.0pt）', '差しも有効', 'マイルCSの舞台'],
  },
  '京都-芝-1800': {
    headline: '外回り、内有利で先行やや有利',
    description: '外回り1800m。内有利（+4.0pt）で先行有利。秋華賞の舞台。',
    tips: ['内有利（+4.0pt）', '先行有利'],
  },
  '京都-芝-2000': {
    headline: '内回り、枠順フラットで差しも有効',
    description: '内回り2000m。枠順ほぼフラットで差しも有効。菊花賞の前哨戦の舞台。',
    tips: ['枠順フラット', '差しも有効'],
  },
  '京都-芝-2200': {
    headline: '外回り、内枠有利が顕著',
    description: '外回り2200m。内枠有利（+7.2pt）が顕著。エリザベス女王杯の舞台。先行有利度も高い。',
    tips: ['内枠有利（+7.2pt）', '先行有利', 'エリザベス女王杯の舞台'],
  },
  '京都-芝-2400': {
    headline: '内有利傾向、菊花賞の舞台',
    description: '内有利（+4.0pt）で先行有利。菊花賞・天皇賞(春)の舞台。スタミナ勝負。',
    tips: ['内有利（+4.0pt）', '先行有利', '菊花賞・天皇賞(春)の舞台'],
  },
  '京都-ダート-1200': {
    headline: '外枠不利が最も顕著なダートコース',
    description: '外枠不利(-7.3pt)がJRAダートコースで最大級。先行有利のコース。',
    tips: ['外枠不利が極端（-7.3pt）', '先行有利'],
  },
  '京都-ダート-1400': {
    headline: '外枠やや不利、先行天国',
    description: '外枠やや不利(-2.3pt)。先行top3率38.0%と先行天国。',
    tips: ['外枠やや不利', '先行天国'],
  },
  '京都-ダート-1800': {
    headline: '1角まで超短、外枠不利',
    description: '1角まで250mの超短距離。外枠不利(-2.8pt)で先行有利。',
    tips: ['外枠不利（-2.8pt）', '先行有利'],
  },
  '京都-ダート-1900': {
    headline: '枠順フラット、やや差しも有効',
    description: '枠順ほぼフラット。先行有利度-11.0ptでやや差しも届く長距離ダート。',
    tips: ['枠順フラット', 'やや差しも有効'],
  },
  // === 中京 ===
  '中京-芝-1200': {
    headline: '内枠有利が全コース最大級',
    description: '1角まで310mだが内枠有利が+9.3ptと全コースで最大級。先行有利コース。',
    tips: ['内枠有利が極端（+9.3pt）', '先行有利'],
  },
  '中京-芝-1400': {
    headline: '1角まで510mで内枠有利が続く',
    description: '1角まで510mと長いが内有利（+5.8pt）は健在。先行有利のコース。',
    tips: ['内有利（+5.8pt）', '先行有利'],
  },
  '中京-芝-1600': {
    headline: '内有利で先行有利、急坂でスタミナ要',
    description: '1角まで310mで内有利（+3.5pt）。急坂があるため先行勢でもスタミナ要求。',
    tips: ['内有利（+3.5pt）', '先行有利', '急坂でスタミナ要'],
  },
  '中京-芝-2000': {
    headline: '内有利で先行有利、実力勝負',
    description: '内有利（+4.0pt）で先行有利。急坂と直線の長さで実力差が出やすい。',
    tips: ['内有利（+4.0pt）', '先行有利', '実力差出やすい'],
  },
  '中京-芝-2200': {
    headline: '長距離で差しも有効に',
    description: '内有利（+4.0pt）だが差し有利度-8.4ptと差しも有効に。長距離でスタミナ勝負。',
    tips: ['内有利（+4.0pt）', '差しも有効'],
  },
  '中京-ダート-1200': {
    headline: '枠順フラット、先行天国',
    description: '枠順ほぼフラット（+0.5pt）で珍しいダートコース。逃先top3率39.1%と先行天国。',
    tips: ['枠順フラット', '先行天国'],
  },
  '中京-ダート-1400': {
    headline: '1角遠く外枠不利',
    description: '1角まで510mだが外枠不利(-4.0pt)。先行有利のコース。',
    tips: ['外枠不利（-4.0pt）', '先行有利'],
  },
  '中京-ダート-1800': {
    headline: '枠順差小さく、先行有利',
    description: '枠順差は小さい(-1.2pt)。先行top3率37.6%と先行有利。チャンピオンズCの舞台。',
    tips: ['枠順差小さい', '先行有利', 'チャンピオンズCの舞台'],
  },
  '中京-ダート-1900': {
    headline: '枠順差小さく差しも届く',
    description: '枠順差は小さい(-1.1pt)。差し有利度-13.4ptで差しも届く長距離ダート。',
    tips: ['枠順差小さい', '差しも有効'],
  },
  // === 新潟 ===
  '新潟-芝-1200': {
    headline: '外回り、外枠不利が顕著',
    description: '外回り1200m。外枠不利(-8.0pt)が全芝コースで最大級。先行有利。',
    tips: ['外枠不利が極端（-8.0pt）', '先行有利'],
  },
  '新潟-芝-1400': {
    headline: '内回り、枠順フラット',
    description: '内回り1400m。枠順ほぼフラット。先行やや有利。',
    tips: ['枠順フラット', '先行やや有利'],
  },
  '新潟-芝-1600': {
    headline: '外回り直線長く差し有利',
    description: '外回り1600m。外枠やや不利(-2.6pt)。直線長く先行有利度-17.2ptだが差しも届く。',
    tips: ['外枠やや不利', '差しも届く'],
  },
  '新潟-芝-1800': {
    headline: '内回り、差しも有効に',
    description: '内回り1800m。枠順ほぼフラット。差し有利度-10.1ptで差しも有効。',
    tips: ['枠順フラット', '差しも有効'],
  },
  '新潟-芝-2000': {
    headline: '外回り、差し有利が顕著',
    description: '外回り2000m。差し有利度-9.2ptと差し馬向き。枠順はフラット。新潟記念の舞台。',
    tips: ['枠順フラット', '差し有利', '新潟記念の舞台'],
  },
  '新潟-ダート-1200': {
    headline: '外枠不利、逃げ先行天国',
    description: '外枠不利(-3.4pt)。逃先top3率45.9%と先行天国。先行有利度-25.7ptは全コースでも屈指。',
    tips: ['外枠不利', '逃げ先行天国（45.9%）'],
  },
  '新潟-ダート-1800': {
    headline: '外枠不利、先行有利',
    description: '外枠不利(-2.9pt)。先行top3率38.0%と先行有利。',
    tips: ['外枠不利', '先行有利'],
  },
  // === 福島 ===
  '福島-芝-1200': {
    headline: '小回りで内有利、先行天国',
    description: '内有利（+3.9pt）。逃先top3率36.8%と先行天国。開催後半は外差し注意。',
    tips: ['内有利（+3.9pt）', '先行天国', '開催後半は外差し注意'],
  },
  '福島-芝-1800': {
    headline: '内有利、先行有利だが差しも',
    description: '内有利（+3.4pt）。先行有利だが差し有利度-16.5ptとまだ先行圧倒。',
    tips: ['内有利（+3.4pt）', '先行有利'],
  },
  '福島-芝-2000': {
    headline: '枠順差縮小、差しも有効',
    description: '内やや有利（+1.6pt）。差し有利度-8.2ptで差しも有効な中距離。',
    tips: ['やや内有利', '差しも有効'],
  },
  '福島-芝-2600': {
    headline: '長距離で差し有効、スタミナ決戦',
    description: '内やや有利（+2.1pt）。差し有利度-6.7ptで差し追込が最も有効なコース。',
    tips: ['やや内有利', '差し有効'],
  },
  '福島-ダート-1150': {
    headline: '逃げ先行が圧倒的に有利',
    description: '枠順フラット（+0.9pt）。逃先top3率46.1%と逃げ先行天国。先行有利度-25.9ptは屈指。',
    tips: ['枠順フラット', '逃げ先行天国（46.1%）'],
  },
  '福島-ダート-1700': {
    headline: '枠順フラット、先行有利',
    description: '枠順ほぼフラット(-1.0pt)。先行有利のコース。',
    tips: ['枠順フラット', '先行有利'],
  },
  // === 小倉 ===
  '小倉-芝-1200': {
    headline: '小回りだが外枠やや不利',
    description: '外枠やや不利(-2.4pt)。先行有利度-15.5ptと先行有利。開催進むと外差し。',
    tips: ['外枠やや不利', '先行有利', '開催後半は外差し注意'],
  },
  '小倉-芝-1800': {
    headline: '外枠やや不利、差しも届く',
    description: '外枠やや不利(-2.2pt)。差し有利度-12.9ptで差しも届く。',
    tips: ['外枠やや不利', '差しも届く'],
  },
  '小倉-芝-2000': {
    headline: '枠順フラット、差しが最も有効',
    description: '枠順ほぼフラット（+1.3pt）。差し有利度-7.1ptで差し馬向き。',
    tips: ['枠順フラット', '差しが有効'],
  },
  '小倉-ダート-1000': {
    headline: '逃げ先行が圧倒的、内枠有利',
    description: '内枠有利（+2.9pt）。逃先top3率51.5%はJRA最高級。先行有利度-28.9ptは全コースで最大。',
    tips: ['内枠有利（+2.9pt）', '逃げ先行天国（51.5%）', 'JRA最大の先行有利コース'],
  },
  '小倉-ダート-1700': {
    headline: '枠順フラット、先行有利',
    description: '枠順ほぼフラット(-0.1pt)。先行有利のコース。',
    tips: ['枠順フラット', '先行有利'],
  },
};
