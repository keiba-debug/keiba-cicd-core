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
