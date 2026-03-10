"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import { useTimezone } from "@/components/timezone-provider"
import { Button } from "@/components/ui/button"
import { Loader2, Plus, CheckCircle2, RefreshCw, Mail } from "lucide-react"
import { toast } from "sonner"

interface Email {
    id: string
    subject: string
    from: string
    date: string
    snippet: string
}

export function EmailInboxView() {
    const [emails, setEmails] = useState<Email[]>([])
    const [loading, setLoading] = useState(false)
    const [processingId, setProcessingId] = useState<string | null>(null)
    const { formatInTimezone } = useTimezone()

    const formatEmailDate = (dateStr: string) => {
        try {
            const date = new Date(dateStr)
            if (isNaN(date.getTime())) return dateStr
            return formatInTimezone(date, "MMM d, yyyy h:mm a zzz")
        } catch {
            return dateStr
        }
    }

    const fetchInbox = async () => {
        setLoading(true)
        try {
            const response = await api.get("/email-oauth/inbox")
            setEmails(response.data)
        } catch (error) {
            console.error(error)
            toast.error("Failed to fetch inbox. Make sure SSO is connected.")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchInbox()
    }, [])

    const handleCreateTask = async (email: Email) => {
        setProcessingId(email.id)
        try {
            await api.post("/email-oauth/create-task-from-email", {
                subject: email.subject,
                snippet: email.snippet
            })
            toast.success("Task created from email!")
        } catch (error) {
            console.error(error)
            toast.error("Failed to create task")
        } finally {
            setProcessingId(null)
        }
    }

    return (
        <div className="flex flex-col h-full space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">My Inbox</h2>
                    <p className="text-muted-foreground">

                        Select an email to manually convert it into a task in the General project.
                    </p>
                </div>
                <Button variant="outline" size="icon" onClick={fetchInbox} disabled={loading}>
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
            </div>

            <div className="flex-1 overflow-hidden">
                {loading && emails.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full space-y-4">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                        <p className="text-sm text-muted-foreground">Fetching your emails...</p>
                    </div>
                ) : emails.length > 0 ? (
                    <div className="h-full pr-4 overflow-y-auto custom-scrollbar">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {emails.map((email) => (
                                <div key={email.id} className="p-4 border rounded-lg hover:border-primary/50 transition-colors bg-card flex flex-col justify-between h-full">
                                    <div className="space-y-4 flex-1">
                                        <div className="flex justify-between items-start gap-4">
                                            <div className="space-y-1 min-w-0">
                                                <h4 className="font-semibold text-sm truncate">{email.subject}</h4>
                                                <p className="text-xs text-muted-foreground truncate">{email.from}</p>
                                                <p className="text-[10px] text-muted-foreground/60">{formatEmailDate(email.date)}</p>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant="secondary"
                                                className="shrink-0 h-8 gap-1"
                                                onClick={() => handleCreateTask(email)}
                                                disabled={processingId === email.id}
                                            >
                                                {processingId === email.id ? (
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                ) : (
                                                    <Plus className="h-3 w-3" />
                                                )}
                                                Task
                                            </Button>
                                        </div>
                                        <div className="p-2 bg-muted/30 rounded text-xs text-muted-foreground italic line-clamp-3">
                                            "{email.snippet}..."
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-2">
                        <div className="p-3 bg-muted rounded-full">
                            <CheckCircle2 className="h-6 w-6 text-muted-foreground" />
                        </div>
                        <p className="text-sm font-medium">No recent emails found</p>
                        <p className="text-xs text-muted-foreground">Your inbox is clear or SSO isn't fully linked.</p>
                    </div>
                )}
            </div>
        </div>
    )
}
