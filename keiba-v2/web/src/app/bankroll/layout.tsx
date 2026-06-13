import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '推奨馬券',
};

export default function BankrollLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
