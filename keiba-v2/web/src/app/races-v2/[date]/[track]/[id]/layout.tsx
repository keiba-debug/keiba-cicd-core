import React from 'react';

/**
 * レース詳細ページ（v2）用レイアウト
 */
export default function RaceV2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="race-detail-page">
      {children}
    </div>
  );
}
