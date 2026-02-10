"use client"

import { useState, useEffect } from "react"
import { format, parseISO } from "date-fns"
import { api } from "@/lib/api"
import { Issue, IssueStatus, IssuePriority, User, IssueSummary } from "@/types"
import { isOverdue } from "@/lib/utils"
import { useProject } from "@/components/project-provider"
import { useTimezone } from "@/components/timezone-provider"
import { fromZonedTime } from "date-fns-tz"
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
import { CalendarIcon, Trash2, Loader2, Save, AlertCircle, CheckCircle2, CalendarDays, UserMinus, HelpCircle } from "lucide-react"
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
    const { timezone, formatInTimezone, toZoned } = useTimezone()

    // Local state for edits
    const [title, setTitle] = useState("")
    const [description, setDescription] = useState("")
    const [status, setStatus] = useState<IssueStatus>(IssueStatus.TODO)
    const [priority, setPriority] = useState<IssuePriority>(IssuePriority.MEDIUM)
    const [projectId, setProjectId] = useState<string>("")
    const [dueDate, setDueDate] = useState<string>("")
    const [assigneeId, setAssigneeId] = useState<string>("")

    const [users, setUsers] = useState<User[]>([])
    const [aiSummary, setAiSummary] = useState<IssueSummary | null>(null)
    const [summaryLoading, setSummaryLoading] = useState(false)
    const [dependencies, setDependencies] = useState<Issue[]>([])
    const [dependencyLoading, setDependencyLoading] = useState(false)

    // Fetch users on open
    useEffect(() => {
        if (isOpen) {
            api.get("/users/").then(res => setUsers(res.data)).catch(console.error)
        }
    }, [isOpen])

    // Better sync logic
    const [currentIssueId, setCurrentIssueId] = useState<string | null>(null)

    if (isOpen && issue && issue.id !== currentIssueId) {
        setTitle(issue.title)
        setDescription(issue.description || "")
        setStatus(issue.status)
        setPriority(issue.priority)
        setProjectId(issue.project_id || "")
        setProjectId(issue.project_id || "")
        // Format to YYYY-MM-DD in user timezone
        setDueDate(issue.due_date ? formatInTimezone(issue.due_date, "yyyy-MM-dd") : "")
        setAssigneeId(issue.assignee_id || "")
        setCurrentIssueId(issue.id)
        setAiSummary(null)
        setDependencies([])
    }

    useEffect(() => {
        if (!isOpen || !issue) return
        api.get(`/issues/${issue.id}/dependencies`)
            .then(res => setDependencies(res.data || []))
            .catch(console.error)
    }, [isOpen, issue?.id])

    const handleSave = async () => {
        if (!issue) return
        setLoading(true)
        try {
            await api.patch(`/issues/${issue.id}`, {
                title,
                description,
                status,
                priority,
                project_id: projectId,
                // Convert selected date (YYYY-MM-DD 00:00 user time) to UTC ISO
                due_date: dueDate ? fromZonedTime(dueDate + ' 00:00', timezone).toISOString() : null,
                assignee_id: assigneeId || null
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
            // Set to today in user timezone
            const today = formatInTimezone(new Date(), "yyyy-MM-dd")
            const targetDate = fromZonedTime(today + ' 00:00', timezone)
            await api.patch(`/issues/${issue.id}`, { due_date: targetDate.toISOString() })
            toast.success("Rescheduled to today")
            onUpdate()
        } catch (err) {
            toast.error("Failed to reschedule")
        } finally {
            setLoading(false)
        }
    }

    const handleGenerateSummary = async () => {
        if (!issue) return
        setSummaryLoading(true)
        try {
            const res = await api.post("/ai/summary", { issue_id: issue.id })
            setAiSummary(res.data)
        } catch (err) {
            console.error(err)
            toast.error("Failed to generate summary")
        } finally {
            setSummaryLoading(false)
        }
    }

    const handleDetectDependencies = async () => {
        if (!issue) return
        setDependencyLoading(true)
        try {
            const res = await api.post("/ai/dependencies", { issue_id: issue.id, project_id: issue.project_id })
            setDependencies(res.data || [])
        } catch (err) {
            console.error(err)
            toast.error("Failed to detect dependencies")
        } finally {
            setDependencyLoading(false)
        }
    }

    if (!issue) return null

    const overdue = isOverdue(issue, timezone)
    const isDone = issue.status === IssueStatus.DONE || issue.status === IssueStatus.CANCELED
    const needsScheduling = !dueDate && !isDone
    const isUnassigned = !assigneeId && !isDone

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-[600px] h-[85vh] overflow-hidden flex flex-col">
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
                            <div className="flex gap-1">
                                {overdue && <span className="bg-red-100 text-red-600 text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1"><AlertCircle className="w-3 h-3" /> Overdue</span>}
                                {isUnassigned && <span className="bg-blue-100 text-blue-600 text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1"><UserMinus className="w-3 h-3" /> Unassigned</span>}
                                {needsScheduling && <span className="bg-amber-100 text-amber-600 text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1"><HelpCircle className="w-3 h-3" /> Needs Date</span>}
                            </div>
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
                            This task was due on <strong>{issue.due_date && formatInTimezone(issue.due_date, "MMM d")}</strong>.
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

                <div className="grid gap-4 py-4 overflow-y-auto pr-2 flex-1">
                    <div className="grid grid-cols-2 gap-4">
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

                        {/* Assignee Selector */}
                        <div className="space-y-2">
                            <Label className={isUnassigned ? "text-blue-600 font-semibold" : ""}>Assign To</Label>
                            <Select value={assigneeId} onValueChange={(v) => { setAssigneeId(v); if (!isEditing) setIsEditing(true); }}>
                                <SelectTrigger className={cn("w-full", isUnassigned && "border-blue-300 bg-blue-50/30")}>
                                    <SelectValue placeholder="Unassigned" />
                                </SelectTrigger>
                                <SelectContent>
                                    {users.map(u => (
                                        <SelectItem key={u.id} value={u.id}>{u.full_name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
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
                        <Label className={needsScheduling ? "text-amber-600 font-semibold" : ""}>Due Date</Label>
                        {isEditing ? (
                            <Input
                                type="date"
                                value={dueDate}
                                onChange={(e) => setDueDate(e.target.value)}
                                className={needsScheduling ? "border-amber-300 bg-amber-50/30" : ""}
                            />
                        ) : (
                            <div
                                onClick={() => setIsEditing(true)}
                                className={cn(
                                    "flex items-center gap-2 text-sm p-2 rounded-md hover:bg-muted/50 cursor-pointer",
                                    overdue ? 'text-red-600 font-medium' :
                                        needsScheduling ? 'text-amber-600 font-medium bg-amber-50/30 border border-amber-200' :
                                            'text-muted-foreground'
                                )}
                            >
                                <CalendarIcon className="h-4 w-4" />
                                {dueDate ? format(parseISO(dueDate), "PPP") : "No due date set"}
                            </div>
                        )}
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

                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label>AI Summary</Label>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={handleGenerateSummary}
                                disabled={summaryLoading}
                            >
                                {summaryLoading ? "Summarizing..." : "Generate Summary"}
                            </Button>
                        </div>
                        <div className="border rounded-md p-3 bg-muted/20 text-sm space-y-2 min-h-[140px] max-h-[200px] overflow-y-auto">
                            {aiSummary ? (
                                <>
                                    <div>{aiSummary.summary}</div>
                                    {aiSummary.next_steps?.length > 0 && (
                                        <div>
                                            <div className="text-xs font-medium text-muted-foreground mb-1">Next steps</div>
                                            <div className="space-y-1">
                                                {aiSummary.next_steps.map((step, idx) => (
                                                    <div key={idx} className="text-sm">- {step}</div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div className="text-xs text-muted-foreground">
                                    Generate a concise summary and next steps for this issue.
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label>Dependencies</Label>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={handleDetectDependencies}
                                disabled={dependencyLoading}
                            >
                                {dependencyLoading ? "Detecting..." : "Detect Dependencies"}
                            </Button>
                        </div>
                        <div className="border rounded-md p-3 bg-muted/20 text-sm space-y-2 min-h-[120px] max-h-[200px] overflow-y-auto">
                            {dependencies.length > 0 ? (
                                dependencies.map((dep) => (
                                    <div key={dep.id} className="text-sm">
                                        <div className="font-medium">{dep.title}</div>
                                        <div className="text-xs text-muted-foreground">
                                            {dep.status} • {dep.priority} • {dep.id.slice(0, 8)}
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <div className="text-xs text-muted-foreground">
                                    No dependencies detected yet.
                                </div>
                            )}
                        </div>
                    </div>
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

function cn(...classes: any[]) {
    return classes.filter(Boolean).join(' ')
}
