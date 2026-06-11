import { NextRequest, NextResponse } from 'next/server';
import { getBetTemplateLab } from '@/lib/data/bet-template-lab-reader';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const result = await getBetTemplateLab(version);
  if (!result) {
    return NextResponse.json(
      { error: 'Bet template lab not found. Run: python -m ml.export_bet_template_lab' },
      { status: 404 },
    );
  }
  return NextResponse.json(result);
}
