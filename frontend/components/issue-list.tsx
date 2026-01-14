"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { Issue, IssueStatus, IssuePriority } from "@/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { IssueDetailModal } from "@/components/issue-detail-modal"

interface IssueListProps {
    refreshTrigger?: number
}

export function IssueList({ refreshTrigger = 0 }: IssueListProps) {
  const [issues, setIssues] = useState<Issue[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null)

  const fetchIssues = async () => {
    try {
      const res = await api.get("/issues/")
      setIssues(res.data)
    } catch (err) {
      console.error("Failed to fetch issues", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchIssues()
  }, [refreshTrigger])

  const getStatusColor = (status: IssueStatus) => {
    switch (status) {
      case IssueStatus.TODO: return "bg-gray-500"
      case IssueStatus.IN_PROGRESS: return "bg-blue-500"
      case IssueStatus.DONE: return "bg-green-500"
      case IssueStatus.CANCELED: return "bg-red-500"
      default: return "bg-gray-500"
    }
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

  if (loading) return <div>Loading issues...</div>

  return (
    <div className="space-y-4">
      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">ID</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead className="text-right">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {issues.length === 0 ? (
                <TableRow>
                    <TableCell colSpan={5} className="text-center h-24">
                        No issues found. Create one to get started.
                    </TableCell>
                </TableRow>
            ) : (
                issues.map((issue) => (
                <TableRow 
                    key={issue.id} 
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedIssue(issue)}
                >
                    <TableCell className="font-mono text-xs">{issue.id.slice(0, 8)}</TableCell>
                    <TableCell className="font-medium">{issue.title}</TableCell>
                    <TableCell>
                    <Badge className={getStatusColor(issue.status)}>{issue.status}</Badge>
                    </TableCell>
                    <TableCell className={getPriorityColor(issue.priority)}>
                        {issue.priority}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground text-sm">
                        {new Date(issue.created_at).toLocaleDateString()}
                    </TableCell>
                </TableRow>
                ))
            )}
          </TableBody>
        </Table>
      </div>
      
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