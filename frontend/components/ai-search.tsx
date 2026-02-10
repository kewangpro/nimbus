"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Search, Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import { Issue } from "@/types"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { AIButton } from "@/components/ai-button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { IssueDetailModal } from "@/components/issue-detail-modal"

export function AISearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<Issue[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    try {
      const res = await api.post("/ai/search", { query, limit: 5 })
      setResults(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleIssueUpdate = () => {
      // Refresh search results if something changed
      handleSearch({ preventDefault: () => {} } as any)
      setSelectedIssue(null)
  }

  return (
    <>
        <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
            <AIButton className="w-full justify-start gap-2 sm:w-64">
            🔎 AI Search
            </AIButton>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
            <DialogTitle>Semantic Search</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSearch} className="flex gap-2 mt-4">
            <Input 
                placeholder="Describe the issue (e.g. 'login error on mobile')..." 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
            />
            <Button type="submit" disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
            </Button>
            </form>
            
            <div className="mt-4 space-y-4 max-h-[60vh] overflow-y-auto">
                {results.length > 0 ? (
                    results.map(issue => (
                        <Card 
                            key={issue.id} 
                            className="cursor-pointer hover:bg-muted/50 transition-colors"
                            onClick={() => setSelectedIssue(issue)}
                        >
                            <CardHeader className="p-4 pb-2">
                                <div className="flex justify-between items-start">
                                    <CardTitle className="text-sm font-medium">{issue.title}</CardTitle>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="outline">{issue.status}</Badge>
                                        <Badge variant="secondary" className={
                                            issue.priority === "urgent" ? "text-red-600" :
                                            issue.priority === "high" ? "text-orange-500" : ""
                                        }>
                                            {issue.priority}
                                        </Badge>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent className="p-4 pt-0">
                                <p className="text-xs text-muted-foreground line-clamp-2">
                                    {issue.description}
                                </p>
                            </CardContent>
                        </Card>
                    ))
                ) : (
                    !loading && query && <p className="text-sm text-center text-muted-foreground">No semantically similar issues found.</p>
                )}
            </div>
        </DialogContent>
        </Dialog>

        <IssueDetailModal 
            issue={selectedIssue}
            isOpen={!!selectedIssue}
            onClose={() => setSelectedIssue(null)}
            onUpdate={handleIssueUpdate}
        />
    </>
  )
}
