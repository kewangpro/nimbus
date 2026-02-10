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
import { isOverdue } from "@/lib/utils"
import { AlertCircle, ChevronUp, ChevronDown, HelpCircle, UserMinus } from "lucide-react"
import { useTimezone } from "@/components/timezone-provider"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

interface IssueListProps {
  refreshTrigger?: number
  projectId?: string
}

const PRIORITY_WEIGHT = {
  [IssuePriority.LOW]: 1,
  [IssuePriority.MEDIUM]: 2,
  [IssuePriority.HIGH]: 3,
  [IssuePriority.URGENT]: 4,
}

const STATUS_WEIGHT = {
  [IssueStatus.TODO]: 1,
  [IssueStatus.IN_PROGRESS]: 2,
  [IssueStatus.DONE]: 3,
  [IssueStatus.CANCELED]: 4,
}

export function IssueList({ refreshTrigger = 0, projectId }: IssueListProps) {
  const [issues, setIssues] = useState<Issue[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null)
  const { timezone, formatInTimezone } = useTimezone()
  const [filterText, setFilterText] = useState("")
  const [filterLoading, setFilterLoading] = useState(false)
  const [filterParams, setFilterParams] = useState<any | null>(null)

  // Sorting state
  const [sortKey, setSortKey] = useState<keyof Issue | "overdue">("overdue")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")

  const fetchIssues = async (extraParams?: any) => {
    try {
      const params: any = {}
      if (projectId) params.project_id = projectId
      if (filterParams) Object.assign(params, filterParams)
      if (extraParams) Object.assign(params, extraParams)
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
  }, [refreshTrigger, projectId, filterParams])

  const handleAiFilter = async () => {
    if (!filterText.trim()) {
      toast.error("Enter a filter query")
      return
    }
    setFilterLoading(true)
    try {
      const res = await api.post("/ai/query", { text: filterText, project_id: projectId })
      setFilterParams(res.data)
      toast.success("Filter applied")
    } catch (err) {
      console.error(err)
      toast.error("Failed to apply AI filter")
    } finally {
      setFilterLoading(false)
    }
  }

  const handleClearFilter = () => {
    setFilterParams(null)
    setFilterText("")
  }

  const handleSort = (key: keyof Issue | "overdue") => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortOrder(key === "overdue" || key === "priority" ? "desc" : "asc")
    }
  }

  const getSortIcon = (key: keyof Issue | "overdue") => {
    if (sortKey !== key) return null
    return sortOrder === "asc" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />
  }

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

  const sortedIssues = [...issues].sort((a, b) => {
    let aVal: any
    let bVal: any

    if (sortKey === "overdue") {
      aVal = isOverdue(a) ? 1 : 0
      bVal = isOverdue(b) ? 1 : 0
    } else if (sortKey === "priority") {
      aVal = PRIORITY_WEIGHT[a.priority]
      bVal = PRIORITY_WEIGHT[b.priority]
    } else if (sortKey === "status") {
      aVal = STATUS_WEIGHT[a.status]
      bVal = STATUS_WEIGHT[b.status]
    } else {
      aVal = a[sortKey]
      bVal = b[sortKey]
    }

    if (aVal === bVal) {
      // Tie breaker: created_at descending
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    }

    if (aVal === undefined || aVal === null) return 1
    if (bVal === undefined || bVal === null) return -1

    const modifier = sortOrder === "asc" ? 1 : -1
    return aVal > bVal ? modifier : -modifier
  })

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder="AI filter (e.g. overdue high priority for Alice)"
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
        />
        <Button
          type="button"
          variant="secondary"
          onClick={handleAiFilter}
          disabled={filterLoading}
          className="text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200"
        >
          {filterLoading ? "Filtering..." : "🔎 AI Filter"}
        </Button>
        {filterParams && (
          <Button type="button" variant="ghost" onClick={handleClearFilter}>
            Clear
          </Button>
        )}
      </div>
      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px] cursor-pointer hover:bg-muted/50" onClick={() => handleSort("id")}>
                <div className="flex items-center gap-1">ID {getSortIcon("id")}</div>
              </TableHead>
              <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort("title")}>
                <div className="flex items-center gap-1">Title {getSortIcon("title")}</div>
              </TableHead>
              <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort("status")}>
                <div className="flex items-center gap-1">Status {getSortIcon("status")}</div>
              </TableHead>
              <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort("priority")}>
                <div className="flex items-center gap-1">Priority {getSortIcon("priority")}</div>
              </TableHead>
              <TableHead className="cursor-pointer hover:bg-muted/50">
                <div className="flex items-center gap-1">Assignee</div>
              </TableHead>
              <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort("due_date")}>
                <div className="flex items-center gap-1">Due Date {getSortIcon("due_date")}</div>
              </TableHead>
              <TableHead className="text-right cursor-pointer hover:bg-muted/50" onClick={() => handleSort("created_at")}>
                <div className="flex items-center justify-end gap-1">Created {getSortIcon("created_at")}</div>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedIssues.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center h-24">
                  No issues found. Create one to get started.
                </TableCell>
              </TableRow>
            ) : (
              sortedIssues.map((issue) => {
                const overdue = isOverdue(issue, timezone)
                const needsScheduling = !issue.due_date && issue.status !== IssueStatus.DONE && issue.status !== IssueStatus.CANCELED
                const isUnassigned = !issue.assignee_id && issue.status !== IssueStatus.DONE && issue.status !== IssueStatus.CANCELED

                return (
                  <TableRow
                    key={issue.id}
                    className={`cursor-pointer hover:bg-muted/50 ${overdue ? "bg-red-50/30 hover:bg-red-50/50" :
                      isUnassigned ? "bg-blue-50/20 hover:bg-blue-50/40" :
                        needsScheduling ? "bg-amber-50/20 hover:bg-amber-50/40" : ""
                      }`}
                    onClick={() => setSelectedIssue(issue)}
                  >
                    <TableCell className="font-mono text-xs">{issue.id.slice(0, 8)}</TableCell>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {issue.title}
                        {overdue && <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />}
                        {isUnassigned && <UserMinus className="w-4 h-4 text-blue-500 shrink-0" />}
                        {needsScheduling && <HelpCircle className="w-4 h-4 text-amber-500 shrink-0" />}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={getStatusColor(issue.status)}>{issue.status}</Badge>
                    </TableCell>
                    <TableCell className={getPriorityColor(issue.priority)}>
                      {issue.priority}
                    </TableCell>
                    <TableCell>
                      {issue.assignee ? (
                        <div className="flex items-center gap-2" title={issue.assignee.email}>
                          <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-medium text-primary">
                            {issue.assignee.full_name.charAt(0).toUpperCase()}
                          </div>
                          <span className="text-xs text-muted-foreground truncate max-w-[100px] hidden sm:inline-block">
                            {issue.assignee.full_name}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">Unassigned</span>
                      )}
                    </TableCell>
                    <TableCell className={`text-sm ${overdue ? "text-red-600 font-medium" :
                      needsScheduling ? "text-amber-600 font-medium" : "text-muted-foreground"
                      }`}>
                      {issue.due_date ? formatInTimezone(issue.due_date, "PPP") : "No Date"}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground text-sm">
                      {formatInTimezone(issue.created_at, "P")}
                    </TableCell>
                  </TableRow>
                )
              })
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
