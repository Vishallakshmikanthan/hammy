import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF6B5B]/60 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-[#FF6B5B] text-[#14213D] hover:bg-[#FF8274] shadow-coral-glow font-bold",
        coral:
          "bg-gradient-to-r from-[#FF6B5B] to-[#FF8577] text-[#14213D] hover:brightness-110 shadow-coral-glow font-bold",
        glass:
          "bg-[#F4EDE0]/[0.08] text-[#F4EDE0] border border-[#F4EDE0]/20 backdrop-blur-xl hover:bg-[#F4EDE0]/[0.14] hover:border-[#F4EDE0]/35 shadow-glass-sm",
        outline:
          "border border-[#F4EDE0]/25 bg-transparent text-[#F4EDE0] hover:bg-[#F4EDE0]/10 hover:border-[#F4EDE0]/40",
        secondary:
          "bg-[#14213D]/80 text-[#F4EDE0] border border-[#F4EDE0]/15 backdrop-blur-md hover:bg-[#1E3056]/90",
        ghost:
          "text-[#F4EDE0]/80 hover:bg-[#F4EDE0]/10 hover:text-[#F4EDE0]",
        destructive:
          "bg-[#FF6B5B]/20 text-[#FF6B5B] border border-[#FF6B5B]/40 hover:bg-[#FF6B5B]/30",
        amber:
          "bg-amber-500/20 text-amber-200 border border-amber-400/35 backdrop-blur-md hover:bg-amber-500/30",
        emerald:
          "bg-emerald-500/20 text-emerald-200 border border-emerald-400/35 backdrop-blur-md hover:bg-emerald-500/30",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-8 px-3.5 text-xs",
        lg: "h-11 px-7 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };

