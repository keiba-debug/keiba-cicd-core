import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Selective 候補',
};

export default function SelectiveBetsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
