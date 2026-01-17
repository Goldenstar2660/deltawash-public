/**
 * DeviceStatusBadge - Badge showing device online/offline status.
 * TailAdmin-styled with dot indicator and status text.
 */
interface DeviceStatusBadgeProps {
  isOnline: boolean;
  size?: 'small' | 'medium' | 'large';
}

export function DeviceStatusBadge({ isOnline, size = 'medium' }: DeviceStatusBadgeProps) {
  const sizeStyles = {
    small: { padding: '0.125rem 0.5rem', fontSize: '0.625rem', dotSize: '5px' },
    medium: { padding: '0.25rem 0.625rem', fontSize: '0.75rem', dotSize: '6px' },
    large: { padding: '0.375rem 0.75rem', fontSize: '0.875rem', dotSize: '8px' },
  };

  const style = sizeStyles[size];

  return (
    <span 
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.375rem',
        padding: style.padding,
        fontSize: style.fontSize,
        fontWeight: 500,
        borderRadius: '9999px',
        backgroundColor: isOnline ? 'var(--color-success-50)' : 'var(--color-gray-100)',
        color: isOnline ? 'var(--color-success-600)' : 'var(--color-gray-500)',
      }}
      title={isOnline ? 'Device is online' : 'Device is offline'}
    >
      <span 
        style={{
          width: style.dotSize,
          height: style.dotSize,
          borderRadius: '50%',
          backgroundColor: isOnline ? 'var(--color-success-500)' : 'var(--color-gray-400)',
          flexShrink: 0,
        }}
      />
      <span>{isOnline ? 'Online' : 'Offline'}</span>
    </span>
  );
}
