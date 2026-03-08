import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '登録馬',
};

export default function RegistrationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
