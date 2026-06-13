import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '騎手接戦分析',
};

export default function JockeyCloseFinishLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
