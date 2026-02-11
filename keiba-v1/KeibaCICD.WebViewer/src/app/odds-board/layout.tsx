import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'オッズボード',
};

export default function OddsBoardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
