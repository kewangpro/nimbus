"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { AIButton } from "@/components/ai-button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"

interface AIClientUpdateProps {
  projectId?: string
}

export function AIClientUpdate({ projectId }: AIClientUpdateProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [updateText, setUpdateText] = useState("")

  useEffect(() => {
    setUpdateText("")
  }, [projectId])

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const res = await api.post("/ai/client-update", { project_id: projectId })
      setUpdateText(res.data.update_text || "")
      if (!res.data.update_text) {
        toast.error("No update generated")
      }
    } catch (err) {
      console.error(err)
      toast.error("Failed to generate update")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <AIButton>
          🧾 Client Update
        </AIButton>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] h-[75vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Client Update Draft</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 overflow-y-auto pr-2 flex-1">
          <AIButton
            onClick={handleGenerate}
            disabled={loading}
          >
            {loading ? "Generating..." : "🧾 Generate Update"}
          </AIButton>
          <Textarea value={updateText} readOnly className="min-h-[240px]" />
        </div>
      </DialogContent>
    </Dialog>
  )
}
