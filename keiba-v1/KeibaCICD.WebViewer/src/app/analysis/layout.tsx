import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '分析',
};

export default function AnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
