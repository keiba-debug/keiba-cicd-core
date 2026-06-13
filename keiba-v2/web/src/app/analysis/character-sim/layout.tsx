import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'キャラ別シミュレーション',
};

export default function CharacterSimLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
