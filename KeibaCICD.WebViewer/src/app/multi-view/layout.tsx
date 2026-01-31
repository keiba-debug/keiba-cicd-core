import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'マルチビュー',
};

export default function MultiViewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
