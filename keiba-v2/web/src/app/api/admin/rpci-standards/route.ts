import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// RPCI基準値データの型定義
interface RpciStats {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
  weighted_mean?: number;
}

interface RpciThresholds {
  instantaneous: number;  // 瞬発戦閾値
  sustained: number;      // 持続戦閾値
}

interface CourseData {
  sample_count: number;
  rpci: RpciStats;
  thresholds: RpciThresholds;
}

interface RunnerAdjustment {
  rpci_offset: number;
  rpci_mean: number;
  sample_count: number;
}

interface TrendDistEntry {
  count: number;
  pct: number;
}

interface RpciStandardsData {
  metadata: {
    created_at: string;
    source: string;
    description: string;
    calculation: string;
  };
  by_distance_group: Record<string, CourseData>;
  courses: Record<string, CourseData>;
  similar_courses: Record<string, string[]>;
  by_baba?: Record<string, CourseData>;
  by_distance_group_baba?: Record<string, CourseData>;
  runner_adjustments?: Record<string, Record<string, RunnerAdjustment>>;
  race_trend_distribution?: Record<string, Record<string, TrendDistEntry>>;
}

/**
 * RPCI基準値データを取得
 * GET /api/admin/rpci-standards
 * 
 * Query params:
 * - course: コース名（例: Tokyo_Turf_2000m）で特定コースのみ取得
 * - group: 距離グループ（例: Turf_1800-2200m）で特定グループのみ取得
 */
export async function GET(request: NextRequest) {
  console.log('[RPCI] ========== API CALLED ==========');
  try {
    const searchParams = request.nextUrl.searchParams;
    const course = searchParams.get('course');
    const group = searchParams.get('group');
    console.log('[RPCI] Query params - course:', course, 'group:', group);

    // race_type_standards.jsonのパス（v2: data3/analysis/）
    const dataPath = path.join(
      DATA3_ROOT,
      'analysis',
      'race_type_standards.json'
    );

    // デバッグログ
    console.log('[RPCI] DATA3_ROOT:', DATA3_ROOT);
    console.log('[RPCI] Full path:', dataPath);

    // ファイル存在チェック
    try {
      await fs.access(dataPath);
    } catch {
      return NextResponse.json(
        { 
          error: 'RPCI基準値ファイルが見つかりません',
          message: '管理画面で「レース特性基準値算出」を実行してください',
          path: dataPath
        },
        { status: 404 }
      );
    }

    // JSONファイルを読み込み
    const fileContent = await fs.readFile(dataPath, 'utf-8');
    const data: RpciStandardsData = JSON.parse(fileContent);

    // 特定コースのみ取得
    if (course) {
      const courseData = data.courses[course];
      if (!courseData) {
        return NextResponse.json(
          { error: `コース「${course}」が見つかりません` },
          { status: 404 }
        );
      }
      const similarCourses = data.similar_courses[course] || [];
      return NextResponse.json({
        course,
        data: courseData,
        similar_courses: similarCourses,
        metadata: data.metadata
      });
    }

    // 特定距離グループのみ取得
    if (group) {
      const groupData = data.by_distance_group[group];
      if (!groupData) {
        return NextResponse.json(
          { error: `距離グループ「${group}」が見つかりません` },
          { status: 404 }
        );
      }
      return NextResponse.json({
        group,
        data: groupData,
        metadata: data.metadata
      });
    }

    // 全データを返す（サマリー付き）
    const summary = {
      totalCourses: Object.keys(data.courses).length,
      totalSamples: Object.values(data.courses).reduce((sum, c) => sum + c.sample_count, 0),
      distanceGroups: Object.keys(data.by_distance_group).length,
      similarPairs: Object.values(data.similar_courses).reduce((sum, arr) => sum + arr.length, 0) / 2,
    };

    return NextResponse.json({
      summary,
      by_distance_group: data.by_distance_group,
      courses: data.courses,
      similar_courses: data.similar_courses,
      by_distance_group_baba: data.by_distance_group_baba || {},
      runner_adjustments: data.runner_adjustments || {},
      race_trend_distribution: data.race_trend_distribution || {},
      metadata: data.metadata
    });

  } catch (error) {
    console.error('RPCI基準値取得エラー:', error);
    return NextResponse.json(
      { error: 'RPCI基準値の取得に失敗しました', details: String(error) },
      { status: 500 }
    );
  }
}
