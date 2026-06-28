import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '発信者コメント分析',
};

export default function CommentProfilesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
