import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'オッズ分析',
};

export default function OddsRaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
