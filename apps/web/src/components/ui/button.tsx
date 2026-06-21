import * as React from "react"
import { cn } from "@/lib/utils"

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost"
  size?: "default" | "sm"
}

export function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md border text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        variant === "default" &&
          "border-primary bg-primary text-primary-foreground hover:bg-primary/90",
        variant === "outline" && "border-border bg-transparent hover:bg-muted",
        variant === "ghost" && "border-transparent bg-transparent hover:bg-muted",
        size === "default" && "h-10 px-4",
        size === "sm" && "h-8 px-3",
        className,
      )}
      {...props}
    />
  )
}
