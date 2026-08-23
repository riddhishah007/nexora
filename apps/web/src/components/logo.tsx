import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <circle cx="12" cy="12" r="2.4" fill="#7b68ee" />
      <circle cx="12" cy="12" r="2.4" stroke="#7b68ee" strokeWidth="1" opacity="0.4" />
      <circle cx="4.5" cy="4.5" r="1.8" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="19.5" cy="4.5" r="1.8" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="4.5" cy="19.5" r="1.8" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="19.5" cy="19.5" r="1.8" stroke="currentColor" strokeWidth="1.2" />
      <path
        d="M6 6l3.9 3.9M18 6l-3.9 3.9M6 18l3.9-3.9M18 18l-3.9-3.9"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        opacity="0.55"
      />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-foreground", className)}>
      <LogoMark />
      <span className="font-semibold tracking-tight">Nexora</span>
    </span>
  );
}
