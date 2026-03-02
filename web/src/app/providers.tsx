import { type ReactNode } from 'react';

interface ProvidersProps {
  children: ReactNode;
}

// Future: wrap with Toast and Auth context providers here
export function Providers({ children }: ProvidersProps) {
  return <>{children}</>;
}
