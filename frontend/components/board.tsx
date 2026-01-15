"use client"

import { useEffect, useState } from "react"
import { DragDropContext, DropResult } from "@hello-pangea/dnd"
import { api } from "@/lib/api"
import { Issue, IssueStatus } from "@/types"
import { BoardColumn } from "@/components/board-column"
import { IssueDetailModal } from "@/components/issue-detail-modal"

const COLUMNS = [
  { id: IssueStatus.TODO, title: "To Do" },
  { id: IssueStatus.IN_PROGRESS, title: "In Progress" },
  { id: IssueStatus.DONE, title: "Done" },
  { id: IssueStatus.CANCELED, title: "Canceled" },
]

interface BoardProps {
    refreshTrigger?: number
    projectId?: string
}

export function Board({ refreshTrigger = 0, projectId }: BoardProps) {
  const [issues, setIssues] = useState<Issue[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null)

  const fetchIssues = async () => {
    try {
      const params: any = {}
      if (projectId) params.project_id = projectId
      const res = await api.get("/issues/", { params })
      setIssues(res.data)
    } catch (err) {
      console.error("Failed to fetch issues", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchIssues()
  }, [refreshTrigger, projectId])

  const onDragEnd = async (result: DropResult) => {
    const { destination, source, draggableId } = result

    if (!destination) return

    if (
      destination.droppableId === source.droppableId &&
      destination.index === source.index
    ) {
      return
    }

    // Optimistic Update
    const newStatus = destination.droppableId as IssueStatus
    const updatedIssues = issues.map(issue => 
        issue.id === draggableId ? { ...issue, status: newStatus } : issue
    )
    
    setIssues(updatedIssues)

    // API Call
    try {
        await api.patch(`/issues/${draggableId}`, { status: newStatus })
    } catch (err) {
        console.error("Failed to move issue", err)
        // Revert on failure
        fetchIssues() 
    }
  }

  if (loading) return <div>Loading board...</div>

  // Group issues by status
  const issuesByStatus = issues.reduce((acc, issue) => {
    if (!acc[issue.status]) acc[issue.status] = []
    acc[issue.status].push(issue)
    return acc
  }, {} as Record<IssueStatus, Issue[]>)

  return (
    <div className="h-full flex flex-col overflow-hidden pb-4">
        <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex h-full gap-4">
            {COLUMNS.map(col => (
            <BoardColumn
                key={col.id}
                id={col.id}
                title={col.title}
                issues={issuesByStatus[col.id] || []}
                onIssueClick={setSelectedIssue}
            />
            ))}
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
