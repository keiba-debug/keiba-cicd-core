'use client';

import { useState, useEffect } from 'react';

interface SectionNavProps {
  hasResults: boolean;
  hasBets: boolean;
  hasVB: boolean;
  hasDanger: boolean;
}

const SECTIONS = [
  { id: 'section-summary', label: 'サマリー', always: true },
  { id: 'section-roi', label: '成績', always: false, needsResults: true },
  { id: 'section-bets', label: '購入プラン', always: false, needsBets: true },
  { id: 'section-vb', label: 'VB候補', always: false, needsVB: true },
  { id: 'section-danger', label: '危険馬結果', always: false, needsDanger: true },
  { id: 'section-races', label: 'レースカード', always: true },
] as const;

export function SectionNav({ hasResults, hasBets, hasVB, hasDanger }: SectionNavProps) {
  const [activeSection, setActiveSection] = useState('section-summary');

  const visibleSections = SECTIONS.filter(s => {
    if (s.always) return true;
    if ('needsResults' in s && s.needsResults) return hasResults;
    if ('needsBets' in s && s.needsBets) return hasBets;
    if ('needsVB' in s && s.needsVB) return hasVB;
    if ('needsDanger' in s && s.needsDanger) return hasDanger;
    return true;
  });

  useEffect(() => {
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
  }, [hasResults, hasBets, hasVB, hasDanger]);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="sticky top-14 z-30 bg-background/95 backdrop-blur border-b mb-6 -mx-4 px-4 py-2">
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
    </div>
  );
}
