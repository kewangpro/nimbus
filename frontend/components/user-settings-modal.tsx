"use client"

import { useState } from "react"
import { api } from "@/lib/api"
import { User } from "@/types"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Loader2, Settings } from "lucide-react"
import { toast } from "sonner"
import { useTimezone } from "@/components/timezone-provider"

// Common timezones
const TIMEZONES = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Australia/Sydney",
    "Pacific/Auckland"
]

interface UserSettingsModalProps {
    user: User | null
    onUpdate: () => void
}

export function UserSettingsModal({ user, onUpdate }: UserSettingsModalProps) {
    const [open, setOpen] = useState(false)
    const [loading, setLoading] = useState(false)
    const { timezone, setTimezone } = useTimezone()
    const [selectedTimezone, setSelectedTimezone] = useState(user?.timezone || timezone)

    const handleSave = async () => {
        setLoading(true)
        try {
            await api.patch("/users/me", { timezone: selectedTimezone })
            setTimezone(selectedTimezone) // Update context immediately
            toast.success("Settings updated")
            onUpdate() // Trigger parent refresh (to update user object)
            setOpen(false)
        } catch (error) {
            console.error(error)
            toast.error("Failed to update settings")
        } finally {
            setLoading(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="ghost" size="icon" title="Settings">
                    <Settings className="h-4 w-4" />
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>User Settings</DialogTitle>
                    <DialogDescription>
                        Manage your profile settings and preferences.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="space-y-2">
                        <Label>Full Name</Label>
                        <div className="p-2 border rounded-md bg-muted/20 text-sm text-muted-foreground">
                            {user?.full_name}
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label>Email</Label>
                        <div className="p-2 border rounded-md bg-muted/20 text-sm text-muted-foreground">
                            {user?.email}
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label>Timezone</Label>
                        <Select value={selectedTimezone} onValueChange={setSelectedTimezone}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select timezone" />
                            </SelectTrigger>
                            <SelectContent>
                                {TIMEZONES.map((tz) => (
                                    <SelectItem key={tz} value={tz}>
                                        {tz}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <p className="text-[10px] text-muted-foreground">
                            All dates and times will be displayed in this timezone.
                        </p>
                    </div>
                </div>
                <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
                    <Button onClick={handleSave} disabled={loading}>
                        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Save Changes
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}
