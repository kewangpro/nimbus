"use client"

import { createContext, useContext, useState, useEffect, ReactNode } from "react"
import { Project } from "@/types"
import { api } from "@/lib/api"
import { toast } from "sonner"

interface ProjectContextType {
  project: Project | null
  setProject: (project: Project) => void
  projects: Project[]
  refreshProjects: () => void
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<Project | null>(null)
  const [projects, setProjects] = useState<Project[]>([])

  const fetchProjects = async () => {
    try {
      const res = await api.get("/projects/")
      setProjects(res.data)
      
      // Default to "General" if no project selected
      if (!project && res.data.length > 0) {
        const general = res.data.find((p: Project) => p.name === "General")
        setProject(general || res.data[0])
      }
    } catch (err) {
      console.error("Failed to fetch projects", err)
      toast.error("Failed to load projects")
    }
  }

  useEffect(() => {
      fetchProjects()
  }, [])

  return (
    <ProjectContext.Provider value={{ project, setProject, projects, refreshProjects: fetchProjects }}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject() {
  const context = useContext(ProjectContext)
  if (context === undefined) {
    throw new Error("useProject must be used within a ProjectProvider")
  }
  return context
}
