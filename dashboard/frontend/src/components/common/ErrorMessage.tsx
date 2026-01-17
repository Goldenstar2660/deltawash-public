/**
 * ErrorMessage component for displaying errors with retry option.
 * TailAdmin-styled alert component with icon and action.
 */

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div 
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-8)',
        background: 'var(--color-surface)',
        borderRadius: '1rem',
        border: '1px solid var(--color-gray-200)',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          backgroundColor: 'var(--color-error-50)',
          marginBottom: 'var(--space-4)',
        }}
      >
        <svg 
          width="24" 
          height="24" 
          viewBox="0 0 24 24" 
          fill="none"
          style={{ color: 'var(--color-error-500)' }}
        >
          <path 
            d="M12 9V11M12 15H12.01M5.07183 19H18.9282C20.4678 19 21.4301 17.3333 20.6603 16L13.7321 4C12.9623 2.66667 11.0378 2.66667 10.268 4L3.33978 16C2.56998 17.3333 3.53223 19 5.07183 19Z" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          />
        </svg>
      </div>
      
      <h3 
        style={{
          fontSize: 'var(--text-lg)',
          fontWeight: 600,
          color: 'var(--color-gray-800)',
          marginBottom: 'var(--space-2)',
        }}
      >
        Something went wrong
      </h3>
      
      <p 
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--color-gray-500)',
          maxWidth: '320px',
          marginBottom: onRetry ? 'var(--space-5)' : 0,
        }}
      >
        {message}
      </p>
      
      {onRetry && (
        <button 
          onClick={onRetry} 
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
            padding: 'var(--space-2-5) var(--space-4)',
            backgroundColor: 'var(--color-brand-500)',
            color: 'white',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            borderRadius: 'var(--radius-lg)',
            border: 'none',
            cursor: 'pointer',
            transition: 'background-color 150ms ease',
            boxShadow: 'var(--shadow-theme-xs)',
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-brand-600)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--color-brand-500)'}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path 
              d="M14 8C14 11.3137 11.3137 14 8 14C4.68629 14 2 11.3137 2 8C2 4.68629 4.68629 2 8 2C10.0348 2 11.8351 3.00137 12.9313 4.5M14 4.5V1.5M14 4.5H11" 
              stroke="currentColor" 
              strokeWidth="1.5" 
              strokeLinecap="round" 
              strokeLinejoin="round"
            />
          </svg>
          Try again
        </button>
      )}
    </div>
  );
}
