"use client"

import { useState } from "react"
import { api } from "@/lib/api"
import { 
    Dialog, 
    DialogContent, 
    DialogDescription, 
    DialogHeader, 
    DialogTitle, 
    DialogTrigger 
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { 
    Activity, 
    Loader2, 
    ArrowRight, 
    FolderPlus, 
    Edit3, 
    Trash2, 
    PlusCircle, 
    FileEdit, 
    RefreshCw, 
    LogIn, 
    UserCircle, 
    Mail, 
    MailCheck, 
    Paperclip,
    HelpCircle,
    Sparkles
} from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { AuditLog } from "@/types"
import { format } from "date-fns"

const ACTION_CONFIG: Record<string, { label: string, icon: any, color: string }> = {
    "project.create": { label: "Project Created", icon: FolderPlus, color: "text-green-500" },
    "project.update": { label: "Project Updated", icon: Edit3, color: "text-blue-500" },
    "project.delete": { label: "Project Deleted", icon: Trash2, color: "text-red-500" },
    "issue.create": { label: "Issue Created", icon: PlusCircle, color: "text-green-500" },
    "issue.update": { label: "Issue Updated", icon: FileEdit, color: "text-blue-500" },
    "issue.delete": { label: "Issue Deleted", icon: Trash2, color: "text-red-500" },
    "issue.backfill": { label: "AI Backfill Started", icon: RefreshCw, color: "text-purple-500" },
    "auth.login": { label: "Successful Login", icon: LogIn, color: "text-indigo-500" },
    "user.update_me": { label: "Profile Updated", icon: UserCircle, color: "text-orange-500" },
    "email.task_created": { label: "Auto-Task (Email)", icon: Mail, color: "text-sky-500" },
    "email.task_created_manual": { label: "Manual-Task (Email)", icon: MailCheck, color: "text-sky-500" },
    "file.upload": { label: "File Uploaded", icon: Paperclip, color: "text-teal-500" },
    "ai_schedule": { label: "AI Schedule", icon: Sparkles, color: "text-purple-500" },
}

function getActionInfo(log: AuditLog) {
    const config = ACTION_CONFIG[log.action] || { label: log.action, icon: HelpCircle, color: "text-muted-foreground" }
    
    // Special handling for AI Scheduler
    if (log.action === "issue.update" && log.details?.via === "ai_scheduler") {
        return { 
            label: "AI Schedule", 
            icon: Sparkles, 
            color: "text-purple-500" 
        }
    }
    
    return config
}

function getLogDetailSummary(log: AuditLog) {
    if (!log.details) return null
    
    const parts: string[] = []
    
    // 1. Capture Title / Name
    const name = log.details.name || log.details.title
    if (name) {
        parts.push(`"${name}"`)
    }

    // 2. Capture specific snippets
    if (log.action === "email.task_created" || log.action === "email.task_created_manual") {
        if (log.details.email_subject) parts.push(`Subject: ${log.details.email_subject}`)
    }
    if (log.action === "file.upload") {
        if (log.details.filename) parts.push(`File: ${log.details.filename}`)
    }
    if (log.action === "auth.login") {
        parts.push(`via ${log.details.provider || "SSO"}`)
    }
    if (log.action === "issue.backfill") {
        parts.push(`Job ID: ${log.details.job_id?.split('-')[0]}...`)
    }

    // 3. Highlight changes
    if (log.details.changes && Array.isArray(log.details.changes) && log.details.changes.length > 0) {
        parts.push(`Changes: ${log.details.changes.join(", ")}`)
    }
    
    return parts.length > 0 ? parts.join(" • ") : null
}

export function AuditLogsModal() {
    const [open, setOpen] = useState(false)

    // Fetch logs
    const { data: logs, isLoading: loadingLogs } = useQuery({
        queryKey: ['auditLogs'],
        queryFn: async () => {
            const res = await api.get("/audit-logs/")
            return res.data as AuditLog[]
        },
        enabled: open,
    })

    // Fetch stats
    const { data: stats, isLoading: loadingStats } = useQuery({
        queryKey: ['auditStats'],
        queryFn: async () => {
            const res = await api.get("/audit-logs/stats")
            return res.data as { action_counts: Record<string, number> }
        },
        enabled: open,
    })

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="ghost" size="icon" title="Audit Logs">
                    <Activity className="h-4 w-4" />
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[700px] h-[80vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Audit Logs</DialogTitle>
                    <DialogDescription>
                        View recent activity and statistics across the workspace.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto pr-2 space-y-6 mt-4">
                    
                    {/* Stats Section */}
                    <div>
                        <h3 className="text-sm font-semibold mb-3">Action Statistics</h3>
                        {loadingStats ? (
                            <div className="flex justify-center p-4"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
                        ) : stats ? (
                            <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
                                {Object.entries(stats.action_counts).map(([action, count]) => {
                                    // Use a mock log object for stats label mapping
                                    const { label, icon: Icon, color } = getActionInfo({ action } as AuditLog)
                                    return (
                                        <div key={action} className="p-2 border rounded-lg bg-muted/20 flex items-center gap-3">
                                            <div className={`p-1.5 rounded-md bg-background border ${color}`}>
                                                <Icon className="h-3.5 w-3.5" />
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-[10px] text-muted-foreground leading-none mb-1 truncate uppercase tracking-tighter" title={action}>{label}</p>
                                                <p className="text-base font-bold leading-none">{count}</p>
                                            </div>
                                        </div>
                                    )
                                })}
                                {Object.keys(stats.action_counts).length === 0 && (
                                    <div className="text-sm text-muted-foreground col-span-full">No actions recorded yet.</div>
                                )}
                            </div>
                        ) : null}
                    </div>

                    {/* Logs Table / List */}
                    <div>
                        <h3 className="text-sm font-semibold mb-3">Recent Activity</h3>
                        {loadingLogs ? (
                            <div className="flex justify-center p-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
                        ) : logs ? (
                            <div className="space-y-2">
                                {logs.map((log) => {
                                    const { label, icon: Icon, color } = getActionInfo(log)
                                    const detailSummary = getLogDetailSummary(log)
                                    
                                    return (
                                        <div key={log.id} className="text-sm p-3 border rounded-lg flex items-start gap-3 bg-muted/5 hover:bg-muted/10 transition-colors">
                                            <div className={`mt-0.5 p-2 rounded-lg bg-background border ${color} shrink-0`}>
                                                <Icon className="h-4 w-4" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p className="font-semibold text-sm truncate">{label}</p>
                                                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground whitespace-nowrap">
                                                        {format(new Date(log.created_at), "MMM d, h:mm a")}
                                                    </span>
                                                </div>
                                                
                                                {detailSummary && (
                                                    <p className="text-xs text-secondary-foreground/70 mt-1 italic font-medium truncate">
                                                        {detailSummary}
                                                    </p>
                                                )}

                                                {(log.entity_type || log.entity_id) && (
                                                    <p className="text-[10px] text-muted-foreground mt-1.5 flex items-center gap-1.5 opacity-80">
                                                        {log.entity_type && <span className="uppercase tracking-widest font-bold text-[9px] bg-muted px-1.5 py-0.5 rounded">{log.entity_type}</span>}
                                                        {log.entity_id && (
                                                            <>
                                                                <ArrowRight className="h-2.5 w-2.5" />
                                                                <span className="font-mono">{log.entity_id}</span>
                                                            </>
                                                        )}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    )
                                })}
                                {logs.length === 0 && (
                                    <div className="text-sm text-center text-muted-foreground py-8 border rounded-lg border-dashed">
                                        No logs found.
                                    </div>
                                )}
                            </div>
                        ) : null}
                    </div>
                </div>

            </DialogContent>
        </Dialog>
    )
}
