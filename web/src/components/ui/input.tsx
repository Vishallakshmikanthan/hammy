import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-full border border-[#F4EDE0]/20 bg-[#14213D]/60 px-3.5 py-1.5 text-xs text-[#F4EDE0] shadow-inner backdrop-blur-xl transition-all placeholder:text-[#F4EDE0]/40 focus-visible:outline-none focus-visible:border-[#FF6B5B] focus-visible:ring-2 focus-visible:ring-[#FF6B5B]/30 disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };

