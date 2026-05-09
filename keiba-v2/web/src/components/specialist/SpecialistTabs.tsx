'use client';

/**
 * /specialist/[raceId] のタブUI (Client Component)
 *
 * 適用される specialist モデルが1個なら直接表示、複数ならタブ切替。
 * 将来的に sirius / pedigree / kazemachi-character-view 等を増やしていく。
 */

import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

export interface SpecialistTabConfig {
  id: string;
  label: string;
  panel: React.ReactNode;
}

interface Props {
  tabs: SpecialistTabConfig[];
}

export function SpecialistTabs({ tabs }: Props) {
  if (tabs.length === 0) {
    return (
      <div className="rounded-2xl border bg-white px-6 py-12 text-center text-gray-500">
        このレースに適用される specialist モデルはありません。
      </div>
    );
  }

  if (tabs.length === 1) {
    return <div>{tabs[0].panel}</div>;
  }

  return (
    <Tabs defaultValue={tabs[0].id} className="w-full">
      <TabsList
        className="grid w-full"
        style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}
      >
        {tabs.map((t) => (
          <TabsTrigger key={t.id} value={t.id}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((t) => (
        <TabsContent key={t.id} value={t.id} className="mt-4">
          {t.panel}
        </TabsContent>
      ))}
    </Tabs>
  );
}
