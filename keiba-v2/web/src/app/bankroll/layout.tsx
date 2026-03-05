import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '収支・実行 | KeibaCICD',
};

export default function BankrollLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
