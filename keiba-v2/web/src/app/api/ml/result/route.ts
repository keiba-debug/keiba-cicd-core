import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { getMlExperimentResult, getObstacleModelMeta } from '@/lib/data/ml-result-reader';
import { DATA3_ROOT } from '@/lib/config';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const modelType = request.nextUrl.searchParams.get('model');

  // モデルタイプ指定時: レジストリからメタファイルを特定して返す
  if (modelType && modelType !== 'polaris') {
    return getModelMeta(modelType, version);
  }

  // デフォルト: polaris (平地メインモデル) + 障害メタ
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

/**
 * レジストリベースのモデルメタ読み込み
 */
async function getModelMeta(modelType: string, version: string | null) {
  try {
    const registryPath = path.join(DATA3_ROOT, 'ml', 'model_registry.json');
    const registry = JSON.parse(fs.readFileSync(registryPath, 'utf-8'));
    const model = registry.models?.[modelType];
    if (!model) {
      return NextResponse.json({ error: `Unknown model: ${modelType}` }, { status: 404 });
    }

    const metaFile = model.meta_file;
    if (!metaFile) {
      return NextResponse.json({ error: `No meta file for ${modelType}` }, { status: 404 });
    }

    // バージョン指定時: versions/{dir}/{meta_file} から読む
    if (version) {
      const entry = model.versions?.find((v: { version: string }) => v.version === version);
      if (!entry?.dir) {
        return NextResponse.json({ error: `Version ${version} not found for ${modelType}` }, { status: 404 });
      }
      const versionedPath = path.join(DATA3_ROOT, 'ml', 'versions', entry.dir, metaFile);
      if (!fs.existsSync(versionedPath)) {
        return NextResponse.json({ error: `Meta not found: ${versionedPath}` }, { status: 404 });
      }
      const content = JSON.parse(fs.readFileSync(versionedPath, 'utf-8'));
      return NextResponse.json({ model_type: modelType, ...content });
    }

    // デフォルト: ライブ (data3/ml/{meta_file})
    const livePath = path.join(DATA3_ROOT, 'ml', metaFile);
    if (!fs.existsSync(livePath)) {
      return NextResponse.json({ error: `Meta not found: ${livePath}` }, { status: 404 });
    }
    const content = JSON.parse(fs.readFileSync(livePath, 'utf-8'));
    return NextResponse.json({ model_type: modelType, ...content });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
