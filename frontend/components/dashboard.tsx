"use client"

import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { useWebSocket } from "@/lib/use-websocket"
import { Button } from "@/components/ui/button"
import { IssueList } from "@/components/issue-list"
import { Board } from "@/components/board"
import { CreateIssueDialog } from "@/components/create-issue-dialog"
import { AISearch } from "@/components/ai-search"
import { AIPlanner } from "@/components/ai-planner"
import { AIClientUpdate } from "@/components/ai-client-update"
import { CalendarView } from "@/components/calendar-view"
import { EmailInboxView } from "@/components/email-inbox-view"

import { User, Email } from "@/types"


import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { toast } from "sonner"
import { useProject } from "@/components/project-provider"
import { CreateProjectDialog } from "@/components/create-project-dialog"
import { CalendarDays, Layout, LogOut, Plus, FolderKanban, Mail } from "lucide-react"
import { cn } from "@/lib/utils"
import { TimezoneProvider } from "@/components/timezone-provider"
import { UserSettingsModal } from "@/components/user-settings-modal"
import { AuditLogsModal } from "@/components/audit-logs-modal"

interface DashboardProps {
    user: User | null
    logout: () => void
}

type ViewMode = 'calendar' | 'project' | 'inbox'

export function Dashboard({ user, logout }: DashboardProps) {
    const [refreshKey, setRefreshKey] = useState(0)
    const { project, projects, setProject } = useProject()
    const [viewMode, setViewMode] = useState<ViewMode>('calendar')
    
    // Persistent Inbox State
    const [inboxEmails, setInboxEmails] = useState<Email[]>([])
    const [hasFetchedInbox, setHasFetchedInbox] = useState(false)

    const handleWebSocketMessage = useCallback((data: unknown) => {
        const payload = data as { type: string }
        console.log("WebSocket update:", payload)
        if (['ISSUE_CREATED', 'ISSUE_UPDATED', 'ISSUE_DELETED'].includes(payload.type)) {
            setRefreshKey(prev => prev + 1)
            toast.success("Board updated")
        }
    }, [])

    useWebSocket(handleWebSocketMessage)

    const handleIssueCreated = () => {
        // The WebSocket will trigger the refresh, but we can also do it optimistically/immediately
        setRefreshKey(prev => prev + 1)
    }

    return (
        <TimezoneProvider user={user}>
            <div className="flex h-screen bg-background">
                {/* Sidebar */}
                <div className="w-64 border-r flex flex-col bg-muted/10">
                    <div className="p-6">
                        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                                <span className="text-primary-foreground font-bold">N</span>
                            </div>
                            Nimbus
                        </h1>
                    </div>

                    <div className="flex-1 px-4 space-y-6 overflow-y-auto">
                        {/* My Views */}
                        <div className="space-y-1">
                            <h3 className="mb-2 px-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                My Views
                            </h3>
                            <Button
                                variant={viewMode === 'calendar' ? "secondary" : "ghost"}
                                className="w-full justify-start"
                                onClick={() => setViewMode('calendar')}
                            >
                                <CalendarDays className="mr-2 h-4 w-4" />
                                My Calendar
                            </Button>
                            <Button
                                variant={viewMode === 'inbox' ? "secondary" : "ghost"}
                                className="w-full justify-start"
                                onClick={() => setViewMode('inbox')}
                            >
                                <Mail className="mr-2 h-4 w-4" />
                                My Inbox
                            </Button>

                        </div>

                        {/* Projects */}
                        <div>
                            <div className="flex items-center justify-between px-2 mb-2">
                                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                    Projects
                                </h3>
                                <CreateProjectDialog />
                            </div>
                            <div className="space-y-1">
                                {projects.map(p => (
                                    <Button
                                        key={p.id}
                                        variant={viewMode === 'project' && project?.id === p.id ? "secondary" : "ghost"}
                                        className="w-full justify-start truncate"
                                        onClick={() => {
                                            setProject(p)
                                            setViewMode('project')
                                        }}
                                    >
                                        <FolderKanban className="mr-2 h-4 w-4 shrink-0" />
                                        <span className="truncate">{p.name}</span>
                                    </Button>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="p-4 border-t">
                        <div className="flex items-center gap-2 px-2 mb-4">
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium">
                                {user?.full_name?.charAt(0) || "U"}
                            </div>
                            <div className="flex-1 overflow-hidden">
                                <p className="text-sm font-medium truncate">{user?.full_name}</p>
                                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                            </div>
                        </div>
                        <Button onClick={logout} variant="outline" className="w-full justify-start text-muted-foreground">
                            <LogOut className="mr-2 h-4 w-4" /> Logout
                        </Button>
                    </div>
                </div>

                {/* Main Content */}
                <div className="flex-1 flex flex-col min-w-0">
                    {/* View Content */}
                    <header className="h-16 border-b px-8 flex items-center justify-between shrink-0 bg-background/50 backdrop-blur-sm">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span className={viewMode === 'calendar' ? "text-foreground font-medium" : ""}>
                                {viewMode === 'calendar' ? "My Calendar" : viewMode === 'inbox' ? "Inbox" : "Workspace"}
                            </span>
                            <span>/</span>
                            {viewMode === 'project' && project && (
                                <span className="text-foreground font-medium">{project.name}</span>
                            )}
                        </div>
                        <div className="flex items-center gap-3">
                            <AuditLogsModal />
                            <UserSettingsModal user={user} onUpdate={() => window.location.reload()} />
                            <AIPlanner onIssuesCreated={handleIssueCreated} projectId={project?.id} userId={user?.id} />
                            {viewMode === 'project' && project && (
                                <AIClientUpdate key={project.id} projectId={project.id} />
                            )}
                            <AISearch />

                            <CreateIssueDialog onIssueCreated={handleIssueCreated} projectId={project?.id} userId={user?.id} />

                        </div>
                    </header>

                    <main className="flex-1 overflow-hidden p-8 pt-6">
                        {viewMode === 'calendar' ? (
                            <CalendarView refreshTrigger={refreshKey} userId={user?.id} />
                        ) : viewMode === 'inbox' ? (
                            <EmailInboxView 
                                persistentEmails={inboxEmails} 
                                setPersistentEmails={setInboxEmails}
                                hasFetched={hasFetchedInbox}
                                setHasFetched={setHasFetchedInbox}
                            />
                        ) : project ? (
                            <Tabs defaultValue="board" className="h-full flex flex-col">
                                <div className="flex justify-between items-center mb-4 shrink-0">
                                    <div className="flex items-center gap-4">
                                        <h2 className="text-2xl font-bold tracking-tight">{project.name}</h2>
                                        <TabsList>
                                            <TabsTrigger value="board">Board</TabsTrigger>
                                            <TabsTrigger value="list">List</TabsTrigger>
                                        </TabsList>


                                    </div>
                                </div>

                                <TabsContent value="board" className="flex-1 overflow-hidden mt-0">
                                    <Board refreshTrigger={refreshKey} projectId={project.id} />
                                </TabsContent>
                                <TabsContent value="list" className="flex-1 overflow-auto mt-0">
                                    <IssueList refreshTrigger={refreshKey} projectId={project.id} />
                                </TabsContent>


                            </Tabs>
                        ) : (
                            <div className="flex h-full items-center justify-center text-muted-foreground">
                                Select a view or project
                            </div>
                        )}
                    </main>
                </div>
            </div>
        </TimezoneProvider>
    )


}
