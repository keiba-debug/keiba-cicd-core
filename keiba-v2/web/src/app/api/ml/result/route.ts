import { NextRequest, NextResponse } from 'next/server';
import { getMlExperimentResult, getObstacleModelMeta } from '@/lib/data/ml-result-reader';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const [result, obstacleMeta] = await Promise.all([
    getMlExperimentResult(version),
    getObstacleModelMeta(),
  ]);
  if (!result) {
    return NextResponse.json({ error: 'ML result not found' }, { status: 404 });
  }
  const response = { ...result, ...(obstacleMeta ? { obstacle_model: obstacleMeta } : {}) };
  return NextResponse.json(response);
}
