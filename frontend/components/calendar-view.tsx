"use client"

import { useState, useEffect, useMemo } from "react"
import { format, addDays, isSameDay, isToday, startOfDay, parseISO, isBefore, isAfter } from "date-fns"
import { DragDropContext, Droppable, Draggable, DropResult } from "@hello-pangea/dnd"
import { api } from "@/lib/api"
import { Issue, IssueStatus, IssuePriority } from "@/types"
import { Button } from "@/components/ui/button"
import { Wand2, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { IssueDetailModal } from "@/components/issue-detail-modal"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { isOverdue } from "@/lib/utils"
import { useTimezone } from "@/components/timezone-provider"
import { fromZonedTime } from "date-fns-tz"

interface CalendarViewProps {
    refreshTrigger?: number
    userId?: string
}

export function CalendarView({ refreshTrigger = 0, userId }: CalendarViewProps) {
    const [issues, setIssues] = useState<Issue[]>([])
    const [scheduling, setScheduling] = useState(false)
    const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null)
    const [showCompleted, setShowCompleted] = useState(false)
    const [showWeekends, setShowWeekends] = useState(true)
    const { timezone, toZoned } = useTimezone()

    // Load preferences from local storage on mount
    useEffect(() => {
        const savedCompleted = localStorage.getItem("nimbus_calendar_show_completed")
        if (savedCompleted !== null) setShowCompleted(JSON.parse(savedCompleted))

        const savedWeekends = localStorage.getItem("nimbus_calendar_show_weekends")
        if (savedWeekends !== null) setShowWeekends(JSON.parse(savedWeekends))
    }, [])

    // Save preferences whenever they change
    useEffect(() => {
        localStorage.setItem("nimbus_calendar_show_completed", JSON.stringify(showCompleted))
    }, [showCompleted])

    useEffect(() => {
        localStorage.setItem("nimbus_calendar_show_weekends", JSON.stringify(showWeekends))
    }, [showWeekends])

    const fetchIssues = async () => {
        try {
            const params: any = {}
            if (userId) params.assignee_id = userId
            const res = await api.get("/issues/", { params })
            setIssues(res.data)
        } catch (err) {
            console.error("Failed to fetch issues", err)
        }
    }

    const handleAutoSchedule = async () => {
        setScheduling(true)
        try {
            const res = await api.post("/ai/schedule")
            toast.success(res.data.message)
            fetchIssues()
        } catch (err) {
            console.error(err)
            toast.error("Failed to schedule tasks")
        } finally {
            setScheduling(false)
        }
    }

    // Refetch when refreshTrigger changes
    useEffect(() => {
        fetchIssues()
    }, [refreshTrigger, userId])

    const onDragEnd = async (result: DropResult) => {
        const { destination, source, draggableId } = result

        // Dropped outside or in same place
        if (!destination) return
        if (destination.droppableId === source.droppableId && destination.index === source.index) return

        // Optimistic Update
        const newDate = destination.droppableId // YYYY-MM-DD
        const updatedIssues = issues.map(issue =>
            issue.id === draggableId ? { ...issue, due_date: newDate } : issue
        )
        setIssues(updatedIssues)

        // API Call
        try {
            // Convert the target date (YYYY-MM-DD in user timezone) to UTC ISO string
            const targetDate = fromZonedTime(newDate + ' 00:00', timezone)
            await api.patch(`/issues/${draggableId}`, { due_date: targetDate.toISOString() })
        } catch (err) {
            console.error("Failed to move issue", err)
            toast.error("Failed to update date")
            fetchIssues() // Revert
        }
    }

    // Calculate dynamic date range
    const days = useMemo(() => {
        const today = startOfDay(toZoned(new Date()))
        let minDate = today
        let maxDate = addDays(today, 4) // Minimum 5 days

        issues.forEach(issue => {
            if (!issue.due_date) return
            if (!showCompleted && (issue.status === IssueStatus.DONE || issue.status === IssueStatus.CANCELED)) return

            const date = startOfDay(parseISO(issue.due_date))

            if (isBefore(date, minDate)) minDate = date
            if (isAfter(date, maxDate)) maxDate = date
        })

        // Generate range
        const dayList = []
        let current = minDate
        while (current <= maxDate) {
            // Filter weekends if toggle is off
            const isWeekend = current.getDay() === 0 || current.getDay() === 6
            if (showWeekends || !isWeekend) {
                dayList.push(current)
            }
            current = addDays(current, 1)
        }
        return dayList
    }, [issues, showCompleted, showWeekends])

    // Helper to split issues into days for render
    const getIssuesForDay = (date: Date) => {
        return issues.filter(issue => {
            // Filter out completed or canceled tasks if toggle is off
            if (!showCompleted && (issue.status === IssueStatus.DONE || issue.status === IssueStatus.CANCELED)) {
                return false
            }
            if (!issue.due_date) return false
            const issueDate = toZoned(issue.due_date)
            return isSameDay(issueDate, date)
        })
    }

    // Helper to split issues into days for render
    const getStatusStyles = (status: IssueStatus) => {
        switch (status) {
            case IssueStatus.TODO: return "bg-blue-50 border-blue-200 hover:bg-blue-100"
            case IssueStatus.IN_PROGRESS: return "bg-yellow-50 border-yellow-200 hover:bg-yellow-100"
            case IssueStatus.DONE: return "bg-green-50 border-green-200 hover:bg-green-100"
            case IssueStatus.CANCELED: return "bg-gray-100 border-gray-300 hover:bg-gray-200"
            default: return "bg-background border-border"
        }
    }

    return (
        <div className="h-full flex flex-col space-y-4">
            <div className="flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <h2 className="text-xl font-bold">My Sprint Plan ({days.length} Days)</h2>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center space-x-2 bg-muted/50 px-3 py-1 rounded-full border">
                            <Switch
                                id="show-completed"
                                checked={showCompleted}
                                onCheckedChange={setShowCompleted}
                            />
                            <Label htmlFor="show-completed" className="text-xs cursor-pointer">Show Completed</Label>
                        </div>
                        <div className="flex items-center space-x-2 bg-muted/50 px-3 py-1 rounded-full border">
                            <Switch
                                id="show-weekends"
                                checked={showWeekends}
                                onCheckedChange={setShowWeekends}
                            />
                            <Label htmlFor="show-weekends" className="text-xs cursor-pointer">Show Weekends</Label>
                        </div>
                    </div>
                </div>
                <div className="flex items-center space-x-2">
                    <Button
                        variant="secondary"
                        size="sm"
                        className="gap-2 text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200"
                        onClick={handleAutoSchedule}
                        disabled={scheduling}
                    >
                        {scheduling ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                        AI Schedule
                    </Button>
                    <Button variant="outline" size="icon" onClick={fetchIssues}>
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            <DragDropContext onDragEnd={onDragEnd}>
                <div className="flex-1 overflow-x-auto pb-2">
                    <div className="flex gap-4 h-full min-w-full px-1">
                        {days.map(day => {
                            const dateKey = format(day, 'yyyy-MM-dd')
                            const dayIssues = getIssuesForDay(day)

                            return (
                                <div
                                    key={dateKey}
                                    className={`flex flex-col w-[calc((100%-3rem)/4)] shrink-0 rounded-lg border bg-muted/30 h-full overflow-hidden ${isToday(day) ? 'ring-2 ring-primary/20 bg-primary/5' : ''
                                        }`}
                                >
                                    <div className={`p-3 text-center border-b bg-background ${isToday(day) ? 'text-primary' : ''}`}>
                                        <div className="font-bold flex items-center justify-center gap-2">
                                            {format(day, 'EEEE')}
                                            {isBefore(day, startOfDay(toZoned(new Date()))) && <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full">Overdue</span>}
                                        </div>
                                        <div className="text-sm opacity-80">{format(day, 'MMM d')}</div>
                                    </div>

                                    <Droppable droppableId={dateKey}>
                                        {(provided, snapshot) => (
                                            <div
                                                ref={provided.innerRef}
                                                {...provided.droppableProps}
                                                className={`flex-1 p-2 space-y-2 overflow-y-auto ${snapshot.isDraggingOver ? 'bg-primary/5' : ''}`}
                                            >
                                                {dayIssues.length === 0 && !snapshot.isDraggingOver && (
                                                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground opacity-50">
                                                        Free
                                                    </div>
                                                )}
                                                {dayIssues.map((issue, index) => (
                                                    <Draggable key={issue.id} draggableId={issue.id} index={index}>
                                                        {(provided, snapshot) => (
                                                            <div
                                                                ref={provided.innerRef}
                                                                {...provided.draggableProps}
                                                                {...provided.dragHandleProps}
                                                                onClick={() => setSelectedIssue(issue)}
                                                                style={{ ...provided.draggableProps.style }}
                                                                className={`p-3 rounded-md border shadow-sm transition-all cursor-pointer ${getStatusStyles(issue.status)} ${snapshot.isDragging ? 'opacity-50 ring-2 ring-primary' : ''
                                                                    } ${isOverdue(issue, timezone) ? 'border-red-300 ring-1 ring-red-200' : ''}`}
                                                            >
                                                                <div className="flex items-center justify-between mb-1">
                                                                    <div className="flex items-center gap-1.5">
                                                                        <span className={`w-2 h-2 rounded-full ${issue.priority === IssuePriority.URGENT ? 'bg-red-500' :
                                                                            issue.priority === IssuePriority.HIGH ? 'bg-orange-500' :
                                                                                issue.priority === IssuePriority.MEDIUM ? 'bg-blue-500' : 'bg-gray-400'
                                                                            }`} />
                                                                        {/* Display Project Name */}
                                                                        {/* Use type assertion if project is not yet in type definition but present in API */}
                                                                        {issue.project && (
                                                                            <span className="text-[10px] px-1.5 py-0.5 bg-background/50 rounded-sm font-medium opacity-70 truncate max-w-[80px]">
                                                                                {(issue.project as any).name}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <span className="text-[10px] text-muted-foreground font-mono">{issue.id.slice(0, 4)}</span>
                                                                </div>
                                                                <div className="text-sm font-medium leading-tight line-clamp-2 mb-1">{issue.title}</div>
                                                                <div className="text-[10px] text-muted-foreground capitalize">{issue.status.replace('_', ' ')}</div>
                                                            </div>
                                                        )}
                                                    </Draggable>
                                                ))}
                                                {provided.placeholder}
                                            </div>
                                        )}
                                    </Droppable>

                                    <div className="p-2 border-t bg-background/50 text-center text-xs text-muted-foreground">
                                        {dayIssues.length} Tasks
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            </DragDropContext>

            <IssueDetailModal
                issue={selectedIssue}
                isOpen={!!selectedIssue}
                onClose={() => setSelectedIssue(null)}
                onUpdate={() => {
                    fetchIssues()
                    setSelectedIssue(null)
                }}
            />
        </div>
    )
}