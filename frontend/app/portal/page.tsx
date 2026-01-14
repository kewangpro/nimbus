"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { User, Issue } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export default function ClientPortal() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [issues, setIssues] = useState<Issue[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/login')
      return
    }

    api.defaults.headers.common['Authorization'] = `Bearer ${token}`

    const fetchData = async () => {
        try {
            const userRes = await api.get('/users/me')
            setUser(userRes.data)
            
            // In a real app, this endpoint would filter for issues assigned to the client
            const issuesRes = await api.get('/issues/') 
            setIssues(issuesRes.data)
        } catch (err) {
            console.error(err)
            router.push('/login')
        } finally {
            setLoading(false)
        }
    }
    
    fetchData()
  }, [router])

  const logout = () => {
      localStorage.removeItem('token')
      router.push('/login')
  }

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading Portal...</div>

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-8">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Client Portal</h1>
                <p className="text-muted-foreground">Overview for {user?.full_name}</p>
            </div>
            <Button onClick={logout} variant="outline">Logout</Button>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {issues.map((issue) => (
                <Card key={issue.id} className="hover:shadow-lg transition-shadow">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">
                            {issue.title}
                        </CardTitle>
                        <Badge variant={issue.status === 'done' ? 'default' : 'secondary'}>
                            {issue.status}
                        </Badge>
                    </CardHeader>
                    <CardContent>
                        <p className="text-xs text-muted-foreground mt-2">
                            {issue.description || "No description provided."}
                        </p>
                        <div className="mt-4 text-xs font-mono text-gray-400">
                            ID: {issue.id.slice(0, 8)}
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
      </div>
    </div>
  )
}
