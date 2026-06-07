'use client';

import React from 'react';
import { NextBetCalculator } from '@/components/bankroll/NextBetCalculator';
import { FundManagement } from '@/components/bankroll/FundManagement';
import { WinningCollection } from '@/components/bankroll/WinningCollection';

export function FundTab() {
  return (
    <div className="space-y-6">
      <NextBetCalculator />
      <FundManagement />
      <WinningCollection />
    </div>
  );
}
