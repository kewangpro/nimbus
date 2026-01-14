"use client"

import { Draggable } from "@hello-pangea/dnd"
import { Issue, IssuePriority } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

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
          <Card className="cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow">
            <CardHeader className="p-3 pb-0 space-y-0">
              <div className="flex justify-between items-start">
                <CardTitle className="text-sm font-medium leading-none">
                  {issue.title}
                </CardTitle>
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
