import { NextResponse } from 'next/server';
import { getMlExperimentResult } from '@/lib/data/ml-result-reader';

export async function GET() {
  const result = await getMlExperimentResult();
  if (!result) {
    return NextResponse.json({ error: 'ML result not found' }, { status: 404 });
  }
  return NextResponse.json(result);
}
