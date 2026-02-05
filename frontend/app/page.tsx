"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { User } from "@/types"
import { ProjectProvider } from "@/components/project-provider"
import { Dashboard } from "@/components/dashboard"

export default function Home() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.localStorage?.getItem !== "function") {
      return
    }
    const token = window.localStorage.getItem('token')
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
      if (typeof window !== "undefined" && typeof window.localStorage?.removeItem === "function") {
        window.localStorage.removeItem('token')
      }
      router.push('/login')
  }

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>

  return (
    <ProjectProvider>
        <Dashboard user={user} logout={logout} />
    </ProjectProvider>
  )
}
