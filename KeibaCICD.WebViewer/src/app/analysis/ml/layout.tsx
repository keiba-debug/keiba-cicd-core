import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'ML分析 | KeibaCICD',
};

export default function MlAnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
