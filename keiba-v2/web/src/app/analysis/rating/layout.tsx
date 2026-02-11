import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'レイティング分析',
};

export default function RatingAnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
