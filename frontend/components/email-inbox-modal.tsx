"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader2, Mail, Plus, CheckCircle2, RefreshCw } from "lucide-react"
import { toast } from "sonner"


interface Email {
    id: string
    subject: string
    from: string
    date: string
    snippet: string
}

export function EmailInboxModal() {
    const [open, setOpen] = useState(false)
    const [emails, setEmails] = useState<Email[]>([])
    const [loading, setLoading] = useState(false)
    const [processingId, setProcessingId] = useState<string | null>(null)

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
        if (open) {
            fetchInbox()
        }
    }, [open])

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
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                    <Mail className="h-4 w-4" />
                    View Inbox
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px] h-[80vh] flex flex-col">
                <DialogHeader className="flex flex-row items-center justify-between pr-6">
                    <div>
                        <DialogTitle>SSO Inbox</DialogTitle>
                        <DialogDescription>
                            Select an email to manually convert it into a task.
                        </DialogDescription>
                    </div>
                    <Button variant="ghost" size="icon" onClick={fetchInbox} disabled={loading}>
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                </DialogHeader>

                <div className="flex-1 overflow-hidden">
                    {loading && emails.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full space-y-4">
                            <Loader2 className="h-8 w-8 animate-spin text-primary" />
                            <p className="text-sm text-muted-foreground">Fetching your emails...</p>
                        </div>
                    ) : emails.length > 0 ? (
                        <div className="h-full pr-4 overflow-y-auto custom-scrollbar">
                            <div className="space-y-4">

                                {emails.map((email) => (
                                    <div key={email.id} className="p-4 border rounded-lg hover:border-primary/50 transition-colors bg-card">
                                        <div className="flex justify-between items-start gap-4">
                                            <div className="space-y-1 min-w-0">
                                                <h4 className="font-semibold text-sm truncate">{email.subject}</h4>
                                                <p className="text-xs text-muted-foreground truncate">{email.from}</p>
                                                <p className="text-[10px] text-muted-foreground/60">{email.date}</p>
                                            </div>
                                            <Button
                                                size="sm"
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
                                        <div className="mt-2 p-2 bg-muted/30 rounded text-xs text-muted-foreground line-clamp-2 italic">
                                            "{email.snippet}..."
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
            </DialogContent>
        </Dialog>
    )
}
