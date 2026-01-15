"use client"

import { useProject } from "@/components/project-provider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function ProjectSelector() {
  const { project, projects, setProject } = useProject()

  if (!project) return null

  return (
    <Select value={project.id} onValueChange={(val) => {
        const p = projects.find(proj => proj.id === val)
        if (p) setProject(p)
    }}>
      <SelectTrigger className="w-[180px]">
        <SelectValue placeholder="Select Project" />
      </SelectTrigger>
      <SelectContent>
        {projects.map(p => (
            <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
