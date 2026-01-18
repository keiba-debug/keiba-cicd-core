'use client';

import { ViewModeProvider } from '@/lib/view-mode-context';
import { ReactNode } from 'react';

export function Providers({ children }: { children: ReactNode }) {
  return <ViewModeProvider>{children}</ViewModeProvider>;
}
