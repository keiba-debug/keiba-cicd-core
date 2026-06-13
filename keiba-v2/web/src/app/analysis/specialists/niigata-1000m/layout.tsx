import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '千直',
};

export default function NiigataChokuLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
