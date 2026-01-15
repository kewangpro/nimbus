"use client"

import { useState } from "react"
import { format } from "date-fns"
import { api } from "@/lib/api"
import { Issue, IssueStatus, IssuePriority } from "@/types"
import { isOverdue } from "@/lib/utils"
import { useProject } from "@/components/project-provider"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { CalendarIcon, Trash2, Loader2, Save, AlertCircle, CheckCircle2, CalendarDays, FolderKanban } from "lucide-react"
import { toast } from "sonner"

interface IssueDetailModalProps {
  issue: Issue | null
  isOpen: boolean
  onClose: () => void
  onUpdate: () => void
}

export function IssueDetailModal({ issue, isOpen, onClose, onUpdate }: IssueDetailModalProps) {
  const [loading, setLoading] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const { projects } = useProject()
  
  // Local state for edits
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [status, setStatus] = useState<IssueStatus>(IssueStatus.TODO)
  const [priority, setPriority] = useState<IssuePriority>(IssuePriority.MEDIUM)
  const [projectId, setProjectId] = useState<string>("")

  // Sync state when issue opens
  useState(() => {
      if (issue) {
          setTitle(issue.title)
          setDescription(issue.description || "")
          setStatus(issue.status)
          setPriority(issue.priority)
          setProjectId(issue.project_id || "")
      }
  })

  // Re-sync if issue prop changes while open (e.g. fast switching)
  if (issue && issue.title !== title && !isEditing && !loading && issue.id !== (projectId ? "dirty" : issue.id)) {
      // Logic to prevent overwrite during edit is tricky, simplify:
      // Only resync if issue ID changes
  }
  // Better sync logic
  const [currentIssueId, setCurrentIssueId] = useState<string | null>(null)
  if (issue && issue.id !== currentIssueId) {
      setTitle(issue.title)
      setDescription(issue.description || "")
      setStatus(issue.status)
      setPriority(issue.priority)
      setProjectId(issue.project_id || "")
      setCurrentIssueId(issue.id)
  }

  const handleSave = async () => {
      if (!issue) return
      setLoading(true)
      try {
          await api.patch(`/issues/${issue.id}`, {
              title,
              description,
              status,
              priority,
              project_id: projectId
          })
          toast.success("Issue updated")
          onUpdate()
          setIsEditing(false)
      } catch (err) {
          console.error(err)
          toast.error("Failed to update issue")
      } finally {
          setLoading(false)
      }
  }

  const handleDelete = async () => {
      if (!issue) return
      if (!confirm("Are you sure you want to delete this issue?")) return
      
      setLoading(true)
      try {
          await api.delete(`/issues/${issue.id}`)
          toast.success("Issue deleted")
          onUpdate()
          onClose()
      } catch (err) {
          console.error(err)
          toast.error("Failed to delete issue")
      } finally {
          setLoading(false)
      }
  }

  const handleComplete = async () => {
      if (!issue) return
      setLoading(true)
      try {
          await api.patch(`/issues/${issue.id}`, { status: IssueStatus.DONE })
          toast.success("Issue completed!")
          onUpdate()
          onClose()
      } catch (err) {
          toast.error("Failed to complete issue")
      } finally {
          setLoading(false)
      }
  }

  const handleRescheduleToday = async () => {
      if (!issue) return
      setLoading(true)
      try {
          // Set to today
          const today = new Date().toISOString().split('T')[0]
          await api.patch(`/issues/${issue.id}`, { due_date: today })
          toast.success("Rescheduled to today")
          onUpdate()
      } catch (err) {
          toast.error("Failed to reschedule")
      } finally {
          setLoading(false)
      }
  }

  if (!issue) return null

  const overdue = isOverdue(issue)

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <div className="flex items-center justify-between pr-8">
            <DialogTitle className="text-xl flex items-center gap-2">
                {isEditing ? (
                    <Input value={title} onChange={(e) => setTitle(e.target.value)} className="font-bold" />
                ) : (
                    <span onClick={() => setIsEditing(true)} className="cursor-pointer hover:underline underline-offset-4 decoration-dashed">
                        {issue.title}
                    </span>
                )}
                {overdue && <span className="bg-red-100 text-red-600 text-xs px-2 py-0.5 rounded-full flex items-center gap-1"><AlertCircle className="w-3 h-3" /> Overdue</span>}
            </DialogTitle>
          </div>
          <DialogDescription className="flex items-center gap-2 mt-2">
            <span className="font-mono text-xs text-muted-foreground">{issue.id.slice(0, 8)}</span>
            <span>•</span>
            <span className="text-xs text-muted-foreground">Created {format(new Date(issue.created_at), "MMM d, yyyy")}</span>
          </DialogDescription>
        </DialogHeader>

        {overdue && !isEditing && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-center justify-between">
                <div className="text-sm text-red-800">
                    This task was due on <strong>{issue.due_date && format(new Date(issue.due_date), "MMM d")}</strong>.
                </div>
                <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="border-red-200 hover:bg-red-100 text-red-700" onClick={handleRescheduleToday} disabled={loading}>
                        <CalendarDays className="w-4 h-4 mr-2" />
                        Do Today
                    </Button>
                    <Button size="sm" className="bg-red-600 hover:bg-red-700 text-white" onClick={handleComplete} disabled={loading}>
                        <CheckCircle2 className="w-4 h-4 mr-2" />
                        Complete
                    </Button>
                </div>
            </div>
        )}

        <div className="grid gap-4 py-4">
            {/* Project Selector */}
            <div className="space-y-2">
                <Label>Project</Label>
                <Select value={projectId} onValueChange={(v) => { setProjectId(v); if (!isEditing) setIsEditing(true); }}>
                    <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select Project" />
                    </SelectTrigger>
                    <SelectContent>
                        {projects.map(p => (
                            <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label>Status</Label>
                    <Select value={status} onValueChange={(v) => { setStatus(v as IssueStatus); if (!isEditing) setIsEditing(true); }}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={IssueStatus.TODO}>Todo</SelectItem>
                            <SelectItem value={IssueStatus.IN_PROGRESS}>In Progress</SelectItem>
                            <SelectItem value={IssueStatus.DONE}>Done</SelectItem>
                            <SelectItem value={IssueStatus.CANCELED}>Canceled</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                <div className="space-y-2">
                    <Label>Priority</Label>
                    <Select value={priority} onValueChange={(v) => { setPriority(v as IssuePriority); if (!isEditing) setIsEditing(true); }}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={IssuePriority.LOW}>Low</SelectItem>
                            <SelectItem value={IssuePriority.MEDIUM}>Medium</SelectItem>
                            <SelectItem value={IssuePriority.HIGH}>High</SelectItem>
                            <SelectItem value={IssuePriority.URGENT}>Urgent</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            <div className="space-y-2">
                <Label>Description</Label>
                {isEditing ? (
                    <Textarea 
                        value={description} 
                        onChange={(e) => setDescription(e.target.value)} 
                        className="min-h-[150px]"
                    />
                ) : (
                    <div 
                        onClick={() => setIsEditing(true)}
                        className="min-h-[100px] p-3 rounded-md border bg-muted/20 text-sm whitespace-pre-wrap cursor-pointer hover:bg-muted/40"
                    >
                        {description || <span className="text-muted-foreground italic">No description provided. Click to add one.</span>}
                    </div>
                )}
            </div>
            
            {issue.due_date && (
                <div className={`flex items-center gap-2 text-sm ${overdue ? 'text-red-600 font-medium' : 'text-muted-foreground'}`}>
                    <CalendarIcon className="h-4 w-4" />
                    Due: {format(new Date(issue.due_date), "PPP")}
                </div>
            )}
        </div>

        <DialogFooter className="flex items-center justify-between sm:justify-between w-full">
            <Button variant="destructive" size="sm" onClick={handleDelete} disabled={loading}>
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
            </Button>
            
            <div className="flex gap-2">
                {isEditing ? (
                    <>
                        <Button variant="ghost" onClick={() => setIsEditing(false)}>Cancel</Button>
                        <Button onClick={handleSave} disabled={loading}>
                            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                            Save Changes
                        </Button>
                    </>
                ) : (
                    <Button onClick={() => onClose()}>Close</Button>
                )}
            </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
