import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none backdrop-blur-md",
  {
    variants: {
      variant: {
        default:
          "border-[#FF6B5B]/40 bg-[#FF6B5B]/20 text-[#FF6B5B] shadow-[0_0_15px_rgba(255,107,91,0.2)]",
        coralSolid:
          "border-transparent bg-[#FF6B5B] text-[#14213D] font-bold shadow-coral-glow",
        cream:
          "border-[#F4EDE0]/30 bg-[#F4EDE0]/12 text-[#F4EDE0]",
        navy:
          "border-[#F4EDE0]/15 bg-[#14213D]/80 text-[#F4EDE0]/90",
        success:
          "border-emerald-400/35 bg-emerald-500/15 text-emerald-300",
        warning:
          "border-amber-400/35 bg-amber-500/15 text-amber-300",
        danger:
          "border-rose-400/40 bg-rose-500/20 text-rose-300",
        outline:
          "border-[#F4EDE0]/25 text-[#F4EDE0] bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };

