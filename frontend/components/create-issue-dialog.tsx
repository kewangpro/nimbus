"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { api } from "@/lib/api"
import { IssueStatus, IssuePriority, Issue } from "@/types"
import { Button } from "@/components/ui/button"
import { AIButton } from "@/components/ai-button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Plus, Wand2 } from "lucide-react"
import { toast } from "sonner"
import { useTimezone } from "@/components/timezone-provider"
import { fromZonedTime } from "date-fns-tz"

const formSchema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  priority: z.nativeEnum(IssuePriority),
  status: z.nativeEnum(IssueStatus),
  due_date: z.string().optional(),
})

interface CreateIssueDialogProps {
  onIssueCreated: () => void
  projectId?: string
  userId?: string
}

export function CreateIssueDialog({ onIssueCreated, projectId, userId }: CreateIssueDialogProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [triageLoading, setTriageLoading] = useState(false)
  const [similarLoading, setSimilarLoading] = useState(false)
  const [similarIssues, setSimilarIssues] = useState<Issue[]>([])
  const { timezone } = useTimezone()

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: "",
      description: "",
      priority: IssuePriority.MEDIUM,
      status: IssueStatus.TODO,
      due_date: "",
    },
  })

  async function handleAutoTriage() {
    const { title, description } = form.getValues()
    if (!title) {
      toast.error("Please enter a title first")
      return
    }

    setTriageLoading(true)
    try {
      const res = await api.post("/ai/triage", { title, description: description || "" })
      const { priority } = res.data
      form.setValue("priority", priority)
      toast.success("AI suggested: " + priority)
    } catch (err) {
      console.error(err)
      toast.error("Failed to run AI triage")
    } finally {
      setTriageLoading(false)
    }
  }

  async function handleFindSimilar() {
    const { title, description } = form.getValues()
    if (!title) {
      toast.error("Please enter a title first")
      return
    }
    setSimilarLoading(true)
    try {
      const res = await api.post("/ai/similar", {
        title,
        description: description || "",
        project_id: projectId,
        limit: 5,
      })
      setSimilarIssues(res.data || [])
      if (!res.data?.length) {
        toast("No similar issues found")
      }
    } catch (err) {
      console.error(err)
      toast.error("Failed to find similar issues")
    } finally {
      setSimilarLoading(false)
    }
  }

  async function onSubmit(values: z.infer<typeof formSchema>) {
    setLoading(true)
    try {
      let formattedDueDate = undefined
      if (values.due_date) {
        // Convert the selected date (YYYY-MM-DD 00:00 user time) to UTC ISO
        formattedDueDate = fromZonedTime(values.due_date + ' 00:00', timezone).toISOString()
      }

      const payload = {
        ...values,
        project_id: projectId,
        assignee_id: userId,
        due_date: formattedDueDate
      }

      await api.post("/issues/", payload)
      setOpen(false)
      form.reset()
      setSimilarIssues([])
      onIssueCreated()
      toast.success("Issue created")
    } catch (err) {
      console.error(err)
      toast.error("Failed to create issue")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" /> New Issue
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create New Issue</DialogTitle>
          <DialogDescription>
            Add a new task to your project board.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Title</FormLabel>
                  <FormControl>
                    <Input placeholder="Fix the login bug..." {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="status"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Status</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select status" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={IssueStatus.TODO}>Todo</SelectItem>
                        <SelectItem value={IssueStatus.IN_PROGRESS}>In Progress</SelectItem>
                        <SelectItem value={IssueStatus.DONE}>Done</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Priority</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select priority" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={IssuePriority.LOW}>Low</SelectItem>
                        <SelectItem value={IssuePriority.MEDIUM}>Medium</SelectItem>
                        <SelectItem value={IssuePriority.HIGH}>High</SelectItem>
                        <SelectItem value={IssuePriority.URGENT}>Urgent</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="due_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Due Date</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea placeholder="Details about the issue..." {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex gap-2 justify-end">
              <AIButton
                type="button"
                size="sm"
                onClick={handleAutoTriage}
                disabled={triageLoading}
              >
                <Wand2 className="mr-2 h-3 w-3" />
                {triageLoading ? "Analyzing..." : "✨ AI Auto-Triage"}
              </AIButton>
              <AIButton
                type="button"
                size="sm"
                onClick={handleFindSimilar}
                disabled={similarLoading}
              >
                {similarLoading ? "Searching..." : "🧭 Find Similar"}
              </AIButton>
            </div>

            {similarIssues.length > 0 && (
              <div className="border rounded-md p-3 bg-muted/20">
                <div className="text-sm font-medium mb-2">Possible duplicates</div>
                <div className="space-y-2">
                  {similarIssues.map((issue) => (
                    <div key={issue.id} className="text-sm">
                      <div className="font-medium">{issue.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {issue.status} • {issue.priority} • {issue.id.slice(0, 8)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <DialogFooter>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Creating..." : "Create Issue"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
