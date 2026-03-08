import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'IDM分析',
};

export default function IdmAnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
