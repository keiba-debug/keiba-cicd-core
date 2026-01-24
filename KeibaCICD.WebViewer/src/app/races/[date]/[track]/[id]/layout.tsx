import React from 'react';

export default function RaceDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="newspaper-mode">
      {children}
    </div>
  );
}
