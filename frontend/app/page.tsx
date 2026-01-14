"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { useWebSocket } from "@/lib/use-websocket"
import { Button } from "@/components/ui/button"
import { IssueList } from "@/components/issue-list"
import { Board } from "@/components/board"
import { CreateIssueDialog } from "@/components/create-issue-dialog"
import { AISearch } from "@/components/ai-search"
import { AIPlanner } from "@/components/ai-planner"
import { CalendarView } from "@/components/calendar-view"
import { User } from "@/types"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { toast } from "sonner"

export default function Home() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  // Stable handler for WebSocket messages
  const handleWebSocketMessage = useCallback((data: { type: string }) => {
      console.log("WebSocket update:", data)
      if (['ISSUE_CREATED', 'ISSUE_UPDATED', 'ISSUE_DELETED'].includes(data.type)) {
          setRefreshKey(prev => prev + 1)
          toast.success("Board updated")
      }
  }, [])

  useWebSocket(handleWebSocketMessage)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/login')
      return
    }

    api.defaults.headers.common['Authorization'] = `Bearer ${token}`

    api.get('/users/me')
      .then(res => {
        setUser(res.data)
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        router.push('/login')
      })
  }, [router])

  const logout = () => {
      localStorage.removeItem('token')
      router.push('/login')
  }

  const handleIssueCreated = () => {
      // The WebSocket will trigger the refresh, but we can also do it optimistically/immediately
      // setRefreshKey(prev => prev + 1) 
  }

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>

  return (
    <div className="p-8 max-w-full mx-auto h-screen flex flex-col">
      <div className="flex justify-between items-center mb-8 shrink-0">
        <div>
            <h1 className="text-3xl font-bold tracking-tight">Nimbus</h1>
            <p className="text-muted-foreground">Welcome back, {user?.full_name}</p>
        </div>
        <div className="flex items-center gap-4">
            <AIPlanner onIssuesCreated={handleIssueCreated} />
            <AISearch />
            <CreateIssueDialog onIssueCreated={handleIssueCreated} />
            <Button onClick={logout} variant="outline">Logout</Button>
        </div>
      </div>
      
      <main className="flex-1 overflow-hidden">
        <Tabs defaultValue="board" className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <TabsList>
                    <TabsTrigger value="board">Board</TabsTrigger>
                    <TabsTrigger value="calendar">Calendar</TabsTrigger>
                    <TabsTrigger value="list">List</TabsTrigger>
                </TabsList>
            </div>
            
            <TabsContent value="board" className="flex-1 overflow-hidden">
                <Board refreshTrigger={refreshKey} />
            </TabsContent>
            <TabsContent value="calendar" className="flex-1 overflow-hidden">
                <CalendarView refreshTrigger={refreshKey} />
            </TabsContent>
            <TabsContent value="list" className="flex-1 overflow-auto">
                <IssueList refreshTrigger={refreshKey} />
            </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}