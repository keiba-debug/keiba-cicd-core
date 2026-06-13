import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'My買い目',
};

export default function MyBetsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
