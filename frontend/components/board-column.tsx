"use client"

import { Droppable } from "@hello-pangea/dnd"
import { Issue, IssueStatus } from "@/types"
import { BoardCard } from "@/components/board-card"

interface BoardColumnProps {
  id: IssueStatus
  title: string
  issues: Issue[]
  onIssueClick: (issue: Issue) => void
}

export function BoardColumn({ id, title, issues, onIssueClick }: BoardColumnProps) {
  return (
    <div className="flex flex-col w-80 min-w-[20rem] bg-secondary/50 rounded-lg p-2 mr-4 h-full">
      <div className="flex items-center justify-between p-2 mb-2">
        <h3 className="font-semibold text-sm uppercase text-muted-foreground">{title}</h3>
        <span className="text-xs text-muted-foreground font-mono bg-background px-2 py-1 rounded-full">
            {issues.length}
        </span>
      </div>
      
      <Droppable droppableId={id}>
        {(provided, snapshot) => (
          <div
            {...provided.droppableProps}
            ref={provided.innerRef}
            className={`flex-1 overflow-y-auto min-h-[150px] p-1 rounded-md transition-colors ${
                snapshot.isDraggingOver ? "bg-secondary/80" : ""
            }`}
          >
            {issues.map((issue, index) => (
              <BoardCard key={issue.id} issue={issue} index={index} onClick={onIssueClick} />
            ))}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </div>
  )
}
