import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '買い方ラボ',
};

export default function BetLabLayout({ children }: { children: React.ReactNode }) {
  return children;
}
