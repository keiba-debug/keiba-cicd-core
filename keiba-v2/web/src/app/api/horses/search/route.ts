import { NextRequest, NextResponse } from 'next/server';
import { searchHorsesByNameIndex } from '@/lib/data/horse-data-reader';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = searchParams.get('q') || '';

  if (!query.trim()) {
    return NextResponse.json({ horses: [] });
  }

  try {
    const horses = await searchHorsesByNameIndex(query);
    return NextResponse.json({ horses });
  } catch (error) {
    console.error('Search error:', error);
    return NextResponse.json({ horses: [], error: 'Search failed' }, { status: 500 });
  }
}
