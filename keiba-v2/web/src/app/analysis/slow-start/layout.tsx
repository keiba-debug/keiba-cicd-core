import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '出遅れ分析',
};

export default function SlowStartLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
