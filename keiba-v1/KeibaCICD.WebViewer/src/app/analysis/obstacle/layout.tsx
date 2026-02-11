import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '障害分析',
};

export default function ObstacleAnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
