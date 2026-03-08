import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'シミュレーション',
};

export default function SimulationLayout({ children }: { children: React.ReactNode }) {
  return children;
}
