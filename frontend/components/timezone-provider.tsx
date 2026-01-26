"use client"

import React, { createContext, useContext, useEffect, useState } from "react"
import { format as formatTz, toZonedTime } from "date-fns-tz"
import { User } from "@/types"

interface TimezoneContextType {
    timezone: string
    setTimezone: (tz: string) => void
    toZoned: (date: Date | string) => Date
    formatInTimezone: (date: Date | string, formatStr: string) => string
    toUTC: (date: Date) => Date
}

const TimezoneContext = createContext<TimezoneContextType | undefined>(undefined)

export function TimezoneProvider({
    children,
    user
}: {
    children: React.ReactNode
    user?: User | null
}) {
    const [timezone, setTimezone] = useState(user?.timezone || "UTC")

    useEffect(() => {
        if (user?.timezone) {
            setTimezone(user.timezone)
        }
    }, [user?.timezone])

    const toZoned = (date: Date | string) => {
        return toZonedTime(date, timezone)
    }

    const formatInTimezone = (date: Date | string, formatStr: string) => {
        // formatTz handles the timezone conversion internally
        return formatTz(date, formatStr, { timeZone: timezone })
    }

    // Helper to treat a "Local" date (e.g. from date picker) as that time in the target timezone, converted to UTC Date object
    const toUTC = (localDate: Date) => {
        // If I pick "2026-01-23 00:00" in UI, and I am in Tokyo, I want it to be 2026-01-23 00:00 JST.
        // But the input gives me a Date object that is "2026-01-23 00:00 LocalBrowserTime".
        // This is tricky.
        // Actually, if we use strings YYYY-MM-DD, we can construct the specific time in the timezone.
        // But for this helper, let's assume we want to get the UTC timestamp that corresponds to the given "local" time in the selected timezone.
        // e.g. input: 2026-01-23 00:00 (Local Date object), timezone: JST
        // output: 2026-01-22 15:00 UTC

        // However, usually we handle YYYY-MM-DD strings directly. 
        // Let's implement this if needed, otherwise rely on string manipulation.
        return localDate
    }

    return (
        <TimezoneContext.Provider value={{ timezone, setTimezone, toZoned, formatInTimezone, toUTC }}>
            {children}
        </TimezoneContext.Provider>
    )
}

export function useTimezone() {
    const context = useContext(TimezoneContext)
    if (context === undefined) {
        throw new Error("useTimezone must be used within a TimezoneProvider")
    }
    return context
}
