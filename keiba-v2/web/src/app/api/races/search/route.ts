import { NextRequest, NextResponse } from 'next/server';
import { searchRaces } from '@/lib/data/race-search-reader';

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  const query = params.get('q') || '';
  const venues = params.get('venues')?.split(',').filter(Boolean) || [];
  const track = params.get('track') || '';
  const distanceMin = params.get('distanceMin') ? parseInt(params.get('distanceMin')!) : undefined;
  const distanceMax = params.get('distanceMax') ? parseInt(params.get('distanceMax')!) : undefined;
  const years = params.get('years')?.split(',').map(Number).filter(Boolean) || [];
  const grades = params.get('grades')?.split(',').filter(Boolean) || [];

  try {
    const result = searchRaces({
      query: query || undefined,
      venues: venues.length ? venues : undefined,
      track: track || undefined,
      distanceMin,
      distanceMax,
      years: years.length ? years : undefined,
      grades: grades.length ? grades : undefined,
    });

    return NextResponse.json(result);
  } catch (error) {
    console.error('Race search error:', error);
    return NextResponse.json(
      { races: [], totalCount: 0, filteredCount: 0, error: 'Search failed' },
      { status: 500 },
    );
  }
}
