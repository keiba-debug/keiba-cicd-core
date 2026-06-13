import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Changelog',
};

export default function ChangelogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
