type Size = "sm" | "md" | "lg";

interface LoadingSpinnerProps {
  size?: Size;
  className?: string;
}

const sizeClasses: Record<Size, string> = {
  sm: "w-4 h-4",
  md: "w-8 h-8",
  lg: "w-12 h-12",
};

export function LoadingSpinner({ size = "md", className = "" }: LoadingSpinnerProps) {
  return (
    <span
      role="status"
      className={[
        "inline-block rounded-full border-4 border-indigo-600 border-t-transparent animate-spin",
        sizeClasses[size],
        className,
      ].join(" ")}
    >
      <span className="sr-only">Cargando...</span>
    </span>
  );
}
