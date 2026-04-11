interface SocitwinIconProps {
  className?: string;
  size?: number;
}

export function SocitwinIcon({ className = "", size = 40 }: SocitwinIconProps) {
  return (
    <img
      src="/logo.png"
      alt="Socitwin Logo"
      width={size}
      height={size}
      className={className}
      style={{
        borderRadius: '8px',
      }}
    />
  );
}

export default SocitwinIcon;
