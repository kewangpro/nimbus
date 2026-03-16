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
import { Activity, Loader2, ArrowRight } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { AuditLog } from "@/types"
import { format } from "date-fns"

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
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                {Object.entries(stats.action_counts).map(([action, count]) => (
                                    <div key={action} className="p-3 border rounded-lg bg-muted/20 flex flex-col">
                                        <span className="text-xs text-muted-foreground truncate" title={action}>{action}</span>
                                        <span className="text-lg font-bold">{count}</span>
                                    </div>
                                ))}
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
                            <div className="space-y-3">
                                {logs.map((log) => (
                                    <div key={log.id} className="text-sm p-3 border rounded-lg flex items-start gap-3 bg-muted/10">
                                        <div className="mt-0.5 w-2 h-2 rounded-full bg-primary/40 shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between gap-2">
                                                <p className="font-medium truncate">{log.action}</p>
                                                <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                    {format(new Date(log.created_at), "MMM d, h:mm a")}
                                                </span>
                                            </div>
                                            {(log.entity_type || log.entity_id) && (
                                                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                                                    {log.entity_type && <span className="uppercase tracking-wider font-semibold">{log.entity_type}</span>}
                                                    {log.entity_type && log.entity_id && <ArrowRight className="h-3 w-3" />}
                                                    {log.entity_id && <span className="font-mono">{log.entity_id.split('-')[0]}...</span>}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                ))}
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
