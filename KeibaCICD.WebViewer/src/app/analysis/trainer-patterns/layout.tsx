import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '調教師パターン分析',
};

export default function TrainerPatternsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
