import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'ML Report | KeibaCICD',
};

export default function MlAnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
