// Mock Button component for testing
// Replace with actual shadcn/ui Button component if available

export function Button({ children, onClick, disabled = false, className = "" }) {
  return (
    <button 
      onClick={onClick} 
      disabled={disabled}
      className={`button ${className}`}
    >
      {children}
    </button>
  );
}

