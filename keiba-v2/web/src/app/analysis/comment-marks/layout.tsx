import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AIコメント印(ABC)成績',
};

export default function CommentMarksLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
