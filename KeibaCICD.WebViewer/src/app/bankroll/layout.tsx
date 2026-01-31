import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '収支管理',
};

export default function BankrollLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
