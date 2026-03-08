import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'オッズ表',
};

export default function OddsRaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
