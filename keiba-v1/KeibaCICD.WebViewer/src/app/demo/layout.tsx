import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'デモ',
};

export default function DemoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
