import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'レース検索',
};

export default function RacesSearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
