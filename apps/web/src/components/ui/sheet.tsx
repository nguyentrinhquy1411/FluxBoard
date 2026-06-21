import * as React from "react"
import { Button } from "@/components/ui/button"

type SheetProps = {
  open: boolean
  title: string
  children: React.ReactNode
  onOpenChange: (open: boolean) => void
}

export function Sheet({ open, title, children, onOpenChange }: SheetProps) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" role="dialog" aria-label={title}>
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
        {children}
      </div>
    </div>
  )
}
