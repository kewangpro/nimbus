# UX/UI Design Specification: Nimbus

## 1. Design Philosophy
*   **"Speed is a Feature":** Interactions must be immediate (optimistic UI updates).
*   **AI-Augmented, Not AI-Gated:** AI features should feel like "magic shortcuts" (buttons with sparkles ✨ or wands 🪄) rather than hurdles.
*   **Clean & Focused:** Minimalist aesthetic that reduces visual clutter.

## 2. Visual Style Guide
*   **Backgrounds:** `#0F1115` (Dark), `#FFFFFF` (Light)
*   **AI Accent:** Purple shades (`#A371F7`) to indicate intelligence-powered features.
*   **Status Colors:**
    *   **Todo:** Blue (`bg-blue-50`)
    *   **In Progress:** Yellow (`bg-yellow-50`)
    *   **Done:** Green (`bg-green-50`)
    *   **Canceled:** Grey (`bg-gray-100`)

## 3. Key Interfaces

### 3.1 The Dashboard Layout
*   **Sidebar:** Primary navigation context.
    *   **My Views:** "My Calendar" (Global view of all tasks assigned to the user).
    *   **Projects:** List of active projects. Clicking a project opens its workspace.
    *   **User Profile:** Logout and settings.
*   **Main Content Area:** Dynamic view based on sidebar selection.

### 3.2 View Contexts
1.  **My Calendar (Global):**
    *   A responsive, horizontal-scroll timeline.
    *   Shows all tasks assigned to the current user across **all projects**.
    *   Visual indicators for project context on each card.
2.  **Project Workspace (Board/List):**
    *   **Board:** Kanban style for workflow management within a specific project.
    *   **List:** High-density view for bulk review of project tasks.

### 3.3 AI Feature Access Points
*   **Location:** Global Header (accessible from any view).

#### 🤖 AI Planner (Strategic)
*   **Location:** Header "AI Plan" button.
*   **Interaction:** A large text area for "brain dumping" project ideas.
*   **Intelligence:**
    *   Breaks input down into structured tasks.
    *   **Auto-Schedules:** Assigns balanced due dates (Mon-Fri) to tasks based on urgency and workload.
    *   **Auto-Assigns:** Sets the current user as assignee and links to the active project.

#### 📅 AI Schedule (Tactical)
    *   **Overdue Actions:** If a task is past due, a red alert box provides one-click actions:
        *   **"Do Today":** Reschedules the task to the current date.
        *   **"Complete"::** Marks the task as Done.

### 3.4 Visual Indicators
The UI uses color-coded highlights to signal actionable states across all views (Board, List, Detail):
*   **🔴 Overdue:** Red border/background. High urgency.
*   **🟠 Needs Date:** Amber border/background. Indicates an active task that hasn't been scheduled yet.
*   **🔵 Unassigned:** Blue border/background. Indicates an active task waiting for an owner.
*   **Priority:** Visual pips (Red/Orange/Blue/Gray) indicate Urgency level.

## 4. User Interaction Flows

### 4.1 "Plan to Execution" Flow
1.  User enters `AI Planner`.
2.  Types: "We need to launch the MVP. That means finishing the Auth, setting up the DB, and deploying to AWS."
3.  AI generates 3 structured issues.
4.  User clicks `Create 3 Issues`.
5.  User switches to `Calendar`.
6.  User clicks `AI Schedule`.
7.  Tasks are assigned dates for this week, balanced for workload.
8.  User switches to `Board` to begin dragging cards to "In Progress".

### 4.2 Sprint Management
1.  User views the `5-Day Sprint`.
2.  Toggles "Show Completed" to see progress.
3.  Drags an issue from "Wednesday" to "Friday" to reschedule.
4.  Preferences are saved automatically.
