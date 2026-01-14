"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { api } from "@/lib/api"
import { IssueStatus, IssuePriority } from "@/types"
import { Button } from "@/components/ui/button"
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

const formSchema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  priority: z.nativeEnum(IssuePriority),
  status: z.nativeEnum(IssueStatus),
})

interface CreateIssueDialogProps {
    onIssueCreated: () => void
}

export function CreateIssueDialog({ onIssueCreated }: CreateIssueDialogProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [triageLoading, setTriageLoading] = useState(false)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: "",
      description: "",
      priority: IssuePriority.MEDIUM,
      status: IssueStatus.TODO,
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

  async function onSubmit(values: z.infer<typeof formSchema>) {
    setLoading(true)
    try {
      await api.post("/issues/", values)
      setOpen(false)
      form.reset()
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
            <div className="flex justify-end">
                <Button 
                    type="button" 
                    variant="outline" 
                    size="sm" 
                    onClick={handleAutoTriage}
                    disabled={triageLoading}
                    className="text-purple-600 border-purple-200 hover:bg-purple-50"
                >
                    <Wand2 className="mr-2 h-3 w-3" />
                    {triageLoading ? "Analyzing..." : "AI Auto-Triage"}
                </Button>
            </div>
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
            <DialogFooter>
              <Button type="submit" disabled={loading}>
                  {loading ? "Creating..." : "Create Issue"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
