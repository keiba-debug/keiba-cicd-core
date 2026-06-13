import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'polaris セグメント分析',
};

export default function PolarisSegmentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
