// Mock Card component for testing
// Replace with actual shadcn/ui Card component if available

export function Card({ children, className = "" }) {
  return (
    <div className={`card ${className}`}>
      {children}
    </div>
  );
}

export function CardContent({ children, className = "" }) {
  return (
    <div className={`card-content ${className}`}>
      {children}
    </div>
  );
}

