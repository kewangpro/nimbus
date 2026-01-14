"use client"

import { useState } from "react"
import { api } from "@/lib/api"
import { IssueStatus, IssuePriority } from "@/types"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { BrainCircuit, Loader2, Check, X } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"

interface AIPlannerProps {
    onIssuesCreated: () => void
}

interface PlannedIssue {
    title: string
    description: string
    priority: IssuePriority
    status: IssueStatus
}

export function AIPlanner({ onIssuesCreated }: AIPlannerProps) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [plan, setPlan] = useState<PlannedIssue[]>([])
  const [step, setStep] = useState<'input' | 'review'>('input')

  const handleAnalyze = async () => {
      if (!input.trim()) return
      setLoading(true)
      try {
          const res = await api.post("/ai/plan", { text: input })
          setPlan(res.data)
          setStep('review')
      } catch (err) {
          console.error(err)
          toast.error("Failed to analyze plan")
      } finally {
          setLoading(false)
      }
  }

  const handleCreateAll = async () => {
      setLoading(true)
      try {
          // Create sequentially to maintain order (or Promise.all for speed)
          for (const issue of plan) {
              await api.post("/issues/", issue)
          }
          toast.success(`Created ${plan.length} issues`)
          setOpen(false)
          setInput("")
          setPlan([])
          setStep('input')
          onIssuesCreated()
      } catch (err) {
          console.error(err)
          toast.error("Failed to create issues")
      } finally {
          setLoading(false)
      }
  }

  const removeIssue = (index: number) => {
      setPlan(prev => prev.filter((_, i) => i !== index))
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" className="gap-2 text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200">
            <BrainCircuit className="h-4 w-4" />
            AI Plan
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[700px] max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>AI Project Planner</DialogTitle>
          <DialogDescription>
            {step === 'input' 
                ? "Describe your plan, features, or tasks in plain English. The AI will break it down." 
                : "Review the suggested tasks before creating them."}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4">
            {step === 'input' ? (
                <Textarea 
                    placeholder="E.g., I need to build a new landing page with a hero section, pricing table, and a contact form. Also, fix the navigation bug on mobile."
                    className="min-h-[200px] text-base p-4"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                />
            ) : (
                <div className="space-y-4">
                    {plan.length === 0 && <p className="text-center text-muted-foreground">No tasks found.</p>}
                    {plan.map((issue, idx) => (
                        <Card key={idx} className="relative group">
                            <Button 
                                variant="ghost" 
                                size="icon" 
                                className="absolute top-2 right-2 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                                onClick={() => removeIssue(idx)}
                            >
                                <X className="h-3 w-3" />
                            </Button>
                            <CardContent className="p-4 space-y-2">
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline">{issue.status}</Badge>
                                    <Badge variant="secondary" className={
                                        issue.priority === 'URGENT' ? 'text-red-600' : 
                                        issue.priority === 'HIGH' ? 'text-orange-500' : ''
                                    }>{issue.priority}</Badge>
                                    <Input 
                                        value={issue.title} 
                                        className="font-semibold h-8 border-none shadow-none px-0 focus-visible:ring-0"
                                        onChange={(e) => {
                                            const newPlan = [...plan]
                                            newPlan[idx].title = e.target.value
                                            setPlan(newPlan)
                                        }}
                                    />
                                </div>
                                <Textarea 
                                    value={issue.description} 
                                    className="text-sm text-muted-foreground min-h-[60px] border-none shadow-none p-0 resize-none focus-visible:ring-0"
                                    onChange={(e) => {
                                        const newPlan = [...plan]
                                        newPlan[idx].description = e.target.value
                                        setPlan(newPlan)
                                    }}
                                />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>

        <DialogFooter>
            {step === 'input' ? (
                <Button onClick={handleAnalyze} disabled={loading || !input.trim()}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <BrainCircuit className="mr-2 h-4 w-4" />}
                    {loading ? "Analyzing..." : "Generate Plan"}
                </Button>
            ) : (
                <div className="flex gap-2 w-full justify-end">
                    <Button variant="ghost" onClick={() => setStep('input')}>Back</Button>
                    <Button onClick={handleCreateAll} disabled={loading || plan.length === 0}>
                        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
                        Create {plan.length} Issues
                    </Button>
                </div>
            )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
