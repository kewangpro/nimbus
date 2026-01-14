"use client"

import { Draggable } from "@hello-pangea/dnd"
import { Issue, IssuePriority } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { isOverdue } from "@/lib/utils"
import { AlertCircle } from "lucide-react"

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
          <Card className={`cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow ${overdue ? "border-red-300 bg-red-50/20" : ""}`}>
            <CardHeader className="p-3 pb-0 space-y-0">
              <div className="flex justify-between items-start gap-2">
                <CardTitle className="text-sm font-medium leading-none break-words">
                  {issue.title}
                </CardTitle>
                {overdue && <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />}
              </div>
            </CardHeader>
            <CardContent className="p-3 pt-2">
                <div className="flex justify-between items-center text-xs text-muted-foreground mt-2">
                    <span className="font-mono">{issue.id.slice(0, 4)}</span>
                    <span className={getPriorityColor(issue.priority)}>{issue.priority}</span>
                </div>
            </CardContent>
          </Card>
        </div>
      )}
    </Draggable>
  )
}
