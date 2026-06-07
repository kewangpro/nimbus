"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import { useTimezone } from "@/components/timezone-provider"
import { Button } from "@/components/ui/button"
import { Loader2, Plus, CheckCircle2, RefreshCw, Mail, Check } from "lucide-react"
import { toast } from "sonner"
import { Email } from "@/types"

interface EmailInboxViewProps {
    persistentEmails: Email[]
    setPersistentEmails: (emails: Email[]) => void
    hasFetched: boolean
    setHasFetched: (fetched: boolean) => void
}

export function EmailInboxView({ 
    persistentEmails, 
    setPersistentEmails, 
    hasFetched, 
    setHasFetched 
}: EmailInboxViewProps) {
    const [loading, setLoading] = useState(false)
    const [isProcessingBulk, setIsProcessingBulk] = useState(false)
    const [selectedEmailIds, setSelectedEmailIds] = useState<Set<string>>(new Set())
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
            setPersistentEmails(response.data)
            setHasFetched(true)
            setSelectedEmailIds(new Set())
        } catch (error) {
            console.error(error)
            toast.error("Failed to fetch inbox. Make sure SSO is connected.")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        // fetchInbox() // Removed auto-fetch as per user request
    }, [])

    const toggleSelection = (id: string) => {
        const newSelection = new Set(selectedEmailIds)
        if (newSelection.has(id)) {
            newSelection.delete(id)
        } else {
            newSelection.add(id)
        }
        setSelectedEmailIds(newSelection)
    }

    const toggleSelectAll = () => {
        if (selectedEmailIds.size === persistentEmails.length) {
            setSelectedEmailIds(new Set())
        } else {
            setSelectedEmailIds(new Set(persistentEmails.map(e => e.id)))
        }
    }

    const handleBulkCreateTask = async () => {
        if (selectedEmailIds.size === 0) return
        
        setIsProcessingBulk(true)
        const emailsToProcess = persistentEmails.filter(e => selectedEmailIds.has(e.id))
        
        try {
            await api.post("/email-oauth/create-tasks-bulk", emailsToProcess)
            toast.success(`Successfully created tasks from ${selectedEmailIds.size} emails!`)
            setSelectedEmailIds(new Set())
        } catch (error) {
            console.error(error)
            toast.error("Failed to create tasks")
        } finally {
            setIsProcessingBulk(false)
        }
    }

    return (
        <div className="flex flex-col h-full space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">My Inbox</h2>
                    <p className="text-muted-foreground">
                        Select one or more emails to convert them into tasks in the General project.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {selectedEmailIds.size > 0 && (
                        <Button 
                            variant="default" 
                            className="gap-2" 
                            onClick={handleBulkCreateTask}
                            disabled={isProcessingBulk}
                        >
                            {isProcessingBulk ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Plus className="h-4 w-4" />
                            )}
                            +Task ({selectedEmailIds.size})
                        </Button>
                    )}
                    <Button variant="outline" size="icon" onClick={fetchInbox} disabled={loading}>
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                </div>
            </div>

            <div className="flex-1 overflow-hidden">
                {loading && persistentEmails.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full space-y-4">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                        <p className="text-sm text-muted-foreground">Fetching your emails...</p>
                    </div>
                ) : !hasFetched ? (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4 border-2 border-dashed rounded-xl bg-muted/5">
                        <div className="p-4 bg-primary/10 rounded-full">
                            <Mail className="h-8 w-8 text-primary" />
                        </div>
                        <div className="space-y-2 max-w-[280px]">
                            <p className="text-lg font-semibold">Inbox Ready</p>
                            <p className="text-sm text-muted-foreground">Click the refresh button above to retrieve your latest emails.</p>
                        </div>
                        <Button onClick={fetchInbox} className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Fetch Emails
                        </Button>
                    </div>
                ) : persistentEmails.length > 0 ? (
                    <div className="h-full pr-4 overflow-y-auto custom-scrollbar flex flex-col space-y-4">
                        <div className="flex items-center gap-2 px-1">
                            <Button 
                                variant="ghost" 
                                size="sm" 
                                className="text-xs h-7"
                                onClick={toggleSelectAll}
                            >
                                {selectedEmailIds.size === persistentEmails.length ? "Deselect All" : "Select All"}
                            </Button>
                            <span className="text-xs text-muted-foreground">
                                {selectedEmailIds.size} selected
                            </span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-4">
                            {persistentEmails.map((email) => (
                                <div 
                                    key={email.id} 
                                    className={`p-4 border rounded-lg transition-all cursor-pointer flex flex-col justify-between h-full relative group ${
                                        selectedEmailIds.has(email.id) 
                                        ? 'border-primary bg-primary/5 ring-1 ring-primary/20' 
                                        : 'hover:border-primary/40 bg-card hover:bg-accent/5'
                                    }`}
                                    onClick={() => toggleSelection(email.id)}
                                >
                                    <div className="space-y-4 flex-1">
                                        <div className="flex justify-between items-start gap-4">
                                            <div className="space-y-1 min-w-0">
                                                <h4 className="font-semibold text-sm truncate pr-6">{email.subject}</h4>
                                                <p className="text-xs text-muted-foreground truncate">{email.from}</p>
                                                <p className="text-[10px] text-muted-foreground/60">{formatEmailDate(email.date)}</p>
                                            </div>
                                            <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                                selectedEmailIds.has(email.id) 
                                                ? 'bg-primary border-primary text-primary-foreground' 
                                                : 'border-muted-foreground/30 group-hover:border-primary/50'
                                            }`}>
                                                {selectedEmailIds.has(email.id) && <Check className="h-3 w-3" />}
                                            </div>
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
                        <Button variant="ghost" size="sm" onClick={fetchInbox} className="mt-2">Try Again</Button>
                    </div>
                )}
            </div>
        </div>
    )
}
