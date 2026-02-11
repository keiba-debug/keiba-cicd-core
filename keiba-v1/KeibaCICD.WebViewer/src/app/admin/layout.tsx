import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'データ登録',
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
