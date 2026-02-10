"use client"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type AIButtonProps = React.ComponentProps<typeof Button>

export function AIButton({ className, ...props }: AIButtonProps) {
  return (
    <Button
      variant="secondary"
      className={cn(
        "text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200",
        className
      )}
      {...props}
    />
  )
}
