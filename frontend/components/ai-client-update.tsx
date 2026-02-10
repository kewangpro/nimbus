"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
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
        <Button variant="secondary" className="text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200">
          🧾 Client Update
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] h-[75vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Client Update Draft</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 overflow-y-auto pr-2 flex-1">
          <Button
            onClick={handleGenerate}
            disabled={loading}
            className="text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200"
          >
            {loading ? "Generating..." : "🧾 Generate Update"}
          </Button>
          <Textarea value={updateText} readOnly className="min-h-[240px]" />
        </div>
      </DialogContent>
    </Dialog>
  )
}
