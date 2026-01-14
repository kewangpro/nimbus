"use client"

import { useState, useEffect } from "react"
import { format, addDays, isSameDay, isToday } from "date-fns"
import { DragDropContext, Droppable, Draggable, DropResult } from "@hello-pangea/dnd"
import { api } from "@/lib/api"
import { Issue, IssueStatus } from "@/types"
import { Button } from "@/components/ui/button"
import { Wand2, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { IssueDetailModal } from "@/components/issue-detail-modal"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"

interface CalendarViewProps {
    refreshTrigger?: number
}

export function CalendarView({ refreshTrigger = 0 }: CalendarViewProps) {
  const [currentDate, setCurrentDate] = useState(new Date())
  const [issues, setIssues] = useState<Issue[]>([])
  const [scheduling, setScheduling] = useState(false)
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null)
  const [showCompleted, setShowCompleted] = useState(false)

  // Load preference from local storage on mount
  useEffect(() => {
      const saved = localStorage.getItem("nimbus_calendar_show_completed")
      if (saved !== null) {
          setShowCompleted(JSON.parse(saved))
      }
  }, [])

  // Save preference whenever it changes
  useEffect(() => {
      localStorage.setItem("nimbus_calendar_show_completed", JSON.stringify(showCompleted))
  }, [showCompleted])

  const fetchIssues = async () => {
    try {
      const res = await api.get("/issues/")
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
  }, [refreshTrigger])

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
          await api.patch(`/issues/${draggableId}`, { due_date: newDate })
      } catch (err) {
          console.error("Failed to move issue", err)
          toast.error("Failed to update date")
          fetchIssues() // Revert
      }
  }

  // Generate next 5 days
  const days = Array.from({ length: 5 }, (_, i) => addDays(currentDate, i))

  // Helper to split issues into days for render
  const getIssuesForDay = (date: Date) => {
      return issues.filter(issue => {
          // Filter out completed or canceled tasks if toggle is off
          if (!showCompleted && (issue.status === IssueStatus.DONE || issue.status === IssueStatus.CANCELED)) {
              return false
          }
          if (!issue.due_date) return false
          return isSameDay(new Date(issue.due_date), date)
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold">5-Day Sprint Plan</h2>
            <div className="flex items-center space-x-2 bg-muted/50 px-3 py-1 rounded-full border">
                <Switch 
                    id="show-completed" 
                    checked={showCompleted} 
                    onCheckedChange={setShowCompleted} 
                />
                <Label htmlFor="show-completed" className="text-xs cursor-pointer">Show Completed</Label>
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
        <div className="grid grid-cols-5 gap-4 h-full overflow-hidden">
            {days.map(day => {
                const dateKey = format(day, 'yyyy-MM-dd')
                const dayIssues = getIssuesForDay(day)
                
                return (
                    <div 
                        key={dateKey} 
                        className={`flex flex-col rounded-lg border bg-muted/30 h-full overflow-hidden ${
                            isToday(day) ? 'ring-2 ring-primary/20 bg-primary/5' : ''
                        }`}
                    >
                        <div className={`p-3 text-center border-b bg-background ${isToday(day) ? 'text-primary' : ''}`}>
                            <div className="font-bold">{format(day, 'EEEE')}</div>
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
                                            Free Day
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
                                                    className={`p-3 rounded-md border shadow-sm transition-all cursor-pointer ${getStatusStyles(issue.status)} ${
                                                        snapshot.isDragging ? 'opacity-50 ring-2 ring-primary' : ''
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className={`w-2 h-2 rounded-full ${
                                                            issue.priority === 'URGENT' ? 'bg-red-500' : 
                                                            issue.priority === 'HIGH' ? 'bg-orange-500' : 
                                                            issue.priority === 'MEDIUM' ? 'bg-blue-500' : 'bg-gray-400'
                                                        }`} />
                                                        <span className="text-[10px] text-muted-foreground font-mono">{issue.id.slice(0,4)}</span>
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
