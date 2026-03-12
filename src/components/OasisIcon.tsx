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
        filter: 'brightness(0) invert(1)', // 将 logo 变成白色
      }}
    />
  );
}

export default OasisIcon;
