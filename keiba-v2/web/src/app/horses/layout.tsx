import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '馬検索',
};

export default function HorsesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
