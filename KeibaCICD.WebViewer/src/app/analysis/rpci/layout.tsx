import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'RPCI分析',
};

export default function RpciAnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
