import * as React from "react"
import { cn } from "@/lib/utils"

const variants = {
  default: "bg-primary text-primary-foreground hover:bg-primary/90",
  outline: "border bg-card hover:bg-muted",
  ghost: "hover:bg-muted",
} as const

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants
  size?: "sm" | "lg"
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "sm", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium whitespace-nowrap transition active:scale-[.97] disabled:pointer-events-none disabled:opacity-40",
        size === "lg" ? "h-12 px-6 text-base" : "h-9 px-4 text-sm",
        variants[variant],
        className,
      )}
      {...props}
    />
  ),
)
Button.displayName = "Button"
