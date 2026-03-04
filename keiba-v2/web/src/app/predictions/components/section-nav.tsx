'use client';

import { useState, useEffect } from 'react';

export type PageTab = 'bets' | 'races';

interface SectionNavProps {
  hasResults: boolean;
  hasBets: boolean;
  hasVB: boolean;
  hasDanger: boolean;
  hasMultiLeg?: boolean;
  activeTab: PageTab;
  onTabChange: (tab: PageTab) => void;
  raceCount?: number;
}

const BET_SECTIONS = [
  { id: 'section-summary', label: 'サマリー', always: true },
  { id: 'section-roi', label: '成績', always: false, needsResults: true },
  { id: 'section-bets', label: 'システム投資', always: false, needsBets: true },
  { id: 'section-multi-leg', label: 'スポット馬券', always: false, needsMultiLeg: true },
  { id: 'section-vb', label: 'Value Bet', always: false, needsVB: true },
  { id: 'section-danger', label: 'Danger Alert', always: false, needsDanger: true },
] as const;

export function SectionNav({ hasResults, hasBets, hasVB, hasDanger, hasMultiLeg = false, activeTab, onTabChange, raceCount = 0 }: SectionNavProps) {
  const [activeSection, setActiveSection] = useState('section-summary');

  const visibleSections = BET_SECTIONS.filter(s => {
    if (s.always) return true;
    if ('needsResults' in s && s.needsResults) return hasResults;
    if ('needsBets' in s && s.needsBets) return hasBets;
    if ('needsVB' in s && s.needsVB) return hasVB;
    if ('needsMultiLeg' in s && s.needsMultiLeg) return hasMultiLeg;
    if ('needsDanger' in s && s.needsDanger) return hasDanger;
    return true;
  });

  useEffect(() => {
    if (activeTab !== 'bets') return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: '-120px 0px -60% 0px', threshold: 0 }
    );

    for (const section of visibleSections) {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, [activeTab, hasResults, hasBets, hasVB, hasDanger, hasMultiLeg]);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="sticky top-14 z-30 bg-background/95 backdrop-blur border-b mb-6 -mx-4 px-4 py-2">
      <div className="flex items-center gap-3">
        {/* メインタブ */}
        <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden shrink-0">
          <button
            onClick={() => onTabChange('bets')}
            className={`px-3 py-1.5 text-xs font-semibold transition-colors ${
              activeTab === 'bets'
                ? 'bg-blue-600 text-white'
                : 'bg-background text-muted-foreground hover:bg-muted/50'
            }`}
          >
            馬券
          </button>
          <button
            onClick={() => onTabChange('races')}
            className={`px-3 py-1.5 text-xs font-semibold transition-colors border-l border-gray-200 dark:border-gray-700 ${
              activeTab === 'races'
                ? 'bg-blue-600 text-white'
                : 'bg-background text-muted-foreground hover:bg-muted/50'
            }`}
          >
            出走表{raceCount > 0 && ` (${raceCount})`}
          </button>
        </div>

        {/* セクション内ナビ（馬券タブのみ） */}
        {activeTab === 'bets' && (
          <div className="flex gap-1 overflow-x-auto">
            {visibleSections.map(s => (
              <button
                key={s.id}
                onClick={() => scrollTo(s.id)}
                className={`px-3 py-1.5 text-xs rounded-full whitespace-nowrap transition-colors ${
                  activeSection === s.id
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
