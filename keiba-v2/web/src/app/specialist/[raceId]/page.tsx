/**
 * Specialist 予想画面 /specialist/[raceId] (Server Component)
 *
 * スペシャリストモデル（vega-niigata1000等）が適用されているレースのみ
 * 詳細予想を表示する専用画面。複数モデル該当時はタブ切替。
 */

import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { getRaceMetaForSpecialist } from '@/lib/data/specialist-reader';
import { SpecialistRaceHeader } from '@/components/specialist/SpecialistRaceHeader';
import { SpecialistTabs, type SpecialistTabConfig } from '@/components/specialist/SpecialistTabs';
import { NiigataChokuTab } from '@/components/odds-race/NiigataChokuTab';

export const dynamic = 'force-dynamic';

interface PageParams {
  params: Promise<{ raceId: string }>;
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { raceId } = await params;
  const meta = getRaceMetaForSpecialist(raceId);
  if (!meta) return { title: 'Specialist 予想' };
  return {
    title: `${meta.venueName}${meta.raceNumber}R Specialist 予想`,
  };
}

export default async function SpecialistPage({ params }: PageParams) {
  const { raceId } = await params;
  const meta = getRaceMetaForSpecialist(raceId);
  if (!meta) notFound();

  // 適用モデルから tabs を組み立てる
  const tabs: SpecialistTabConfig[] = [];
  for (const m of meta.appliedModels) {
    if (m.id === 'niigata1000') {
      tabs.push({
        id: 'niigata1000',
        label: m.label,
        panel: <NiigataChokuTab entries={meta.predictionRace.entries} raceId={meta.raceId} />,
      });
    }
    // 将来 sirius / pedigree 等のパネルをここに追加
  }

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-4">
      <SpecialistRaceHeader meta={meta} />
      <SpecialistTabs tabs={tabs} />
    </div>
  );
}
