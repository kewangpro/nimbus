"use client"

import { Draggable } from "@hello-pangea/dnd"
import { Issue, IssuePriority, IssueStatus } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { isOverdue } from "@/lib/utils"
import { AlertCircle, Calendar as CalendarIcon, HelpCircle, UserMinus } from "lucide-react"
import { format } from "date-fns"

interface BoardCardProps {
  issue: Issue
  index: number
  onClick: (issue: Issue) => void
}

const getPriorityColor = (priority: IssuePriority) => {
    switch (priority) {
        case IssuePriority.LOW: return "text-gray-500"
        case IssuePriority.MEDIUM: return "text-blue-500"
        case IssuePriority.HIGH: return "text-orange-500"
        case IssuePriority.URGENT: return "text-red-500 font-bold"
        default: return "text-gray-500"
    }
}

export function BoardCard({ issue, index, onClick }: BoardCardProps) {
  const overdue = isOverdue(issue)
  const needsScheduling = !issue.due_date && issue.status !== IssueStatus.DONE && issue.status !== IssueStatus.CANCELED
  const isUnassigned = !issue.assignee_id && issue.status !== IssueStatus.DONE && issue.status !== IssueStatus.CANCELED

  return (
    <Draggable draggableId={issue.id} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={`mb-2 ${snapshot.isDragging ? "opacity-50" : ""}`}
          onClick={() => onClick(issue)}
        >
          <Card className={`cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow ${
              overdue ? "border-red-300 bg-red-50/20" : 
              isUnassigned ? "border-blue-200 bg-blue-50/10" :
              needsScheduling ? "border-amber-200 bg-amber-50/10" : ""
          }`}>
            <CardHeader className="p-3 pb-0 space-y-0">
              <div className="flex justify-between items-start gap-2">
                <CardTitle className="text-sm font-medium leading-none break-words">
                  {issue.title}
                </CardTitle>
                <div className="flex gap-1 shrink-0">
                    {overdue && <AlertCircle className="w-4 h-4 text-red-500" />}
                    {isUnassigned && <UserMinus className="w-4 h-4 text-blue-500" />}
                    {needsScheduling && <HelpCircle className="w-4 h-4 text-amber-500" />}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-3 pt-2">
                <div className="flex justify-between items-center text-xs text-muted-foreground mt-2">
                    <div className="flex items-center gap-2">
                        {issue.assignee ? (
                            <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-medium text-primary" title={issue.assignee.full_name}>
                                {issue.assignee.full_name.charAt(0).toUpperCase()}
                            </div>
                        ) : (
                            <div className="w-5 h-5 rounded-full border border-dashed border-muted-foreground/50 flex items-center justify-center text-[10px]" title="Unassigned">
                                ?
                            </div>
                        )}
                        {issue.due_date ? (
                            <div className={`flex items-center gap-1 ${overdue ? "text-red-500 font-medium" : ""}`} title="Due Date">
                                <CalendarIcon className="w-3 h-3" />
                                <span>{format(new Date(issue.due_date), "MMM d")}</span>
                            </div>
                        ) : (
                            needsScheduling && (
                                <div className="flex items-center gap-1 text-amber-600 font-medium animate-pulse" title="Needs Scheduling">
                                    <CalendarIcon className="w-3 h-3" />
                                    <span>No Date</span>
                                </div>
                            )
                        )}
                    </div>
                    <span className={getPriorityColor(issue.priority)}>{issue.priority}</span>
                </div>
            </CardContent>
          </Card>
        </div>
      )}
    </Draggable>
  )
}
