import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'WIN5',
};

export default function Win5Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
