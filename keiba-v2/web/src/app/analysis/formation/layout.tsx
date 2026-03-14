import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '三連単フォーメーション検証',
};

export default function FormationLayout({ children }: { children: React.ReactNode }) {
  return children;
}
