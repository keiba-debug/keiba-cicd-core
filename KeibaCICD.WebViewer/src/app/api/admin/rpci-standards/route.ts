import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

// RPCI基準値データの型定義
interface RpciStats {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
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
  try {
    const searchParams = request.nextUrl.searchParams;
    const course = searchParams.get('course');
    const group = searchParams.get('group');

    // race_type_standards.jsonのパス
    const dataPath = path.join(
      process.cwd(),
      '..',
      'KeibaCICD.TARGET',
      'data',
      'race_type_standards.json'
    );

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
