import React from 'react';

interface OasisIconProps {
  className?: string;
  size?: number;
}

export function OasisIcon({ className = "", size = 40 }: OasisIconProps) {
  return (
    <img
      src="/logo.png"
      alt="OASIS Logo"
      width={size}
      height={size}
      className={className}
      style={{
        borderRadius: '8px',
      }}
    />
  );
}

export default OasisIcon;
