# UX/UI Design Specification: Nimbus

## 1. Design Philosophy
*   **"Speed is a Feature":** All interactions use optimistic UI updates — the UI responds immediately, the server catches up.
*   **AI-Augmented, Not AI-Gated:** AI features are "magic shortcuts" (✨ / 🪄 labels), never required steps.
*   **Clean & Focused:** Minimalist aesthetic that reduces visual clutter and surfaces what matters.
*   **SSO-Native:** The user's identity is their email account. No separate email settings needed.

---

## 2. Visual Style Guide
*   **Backgrounds:** `#0F1115` (Dark), `#FFFFFF` (Light).
*   **AI Accent:** Purple shades (`#A371F7`) for all AI-powered actions.
*   **Status Colors:**
    *   **Todo:** Blue (`bg-blue-50`)
    *   **In Progress:** Yellow (`bg-yellow-50`)
    *   **Done:** Green (`bg-green-50`)
    *   **Canceled:** Grey (`bg-gray-100`)

---

## 3. Key Interfaces

### 3.1 Dashboard Layout
*   **Sidebar (left):** Primary navigation.
    *   **My Calendar** — Global, user-centric sprint timeline.
    *   **Projects** — List of all projects. Clicking opens the project workspace.
    *   **User Profile / Settings** — Logout and preferences (including email automation toggle).
*   **Main Content Area:** Dynamic based on sidebar selection.

### 3.2 View Contexts

**My Calendar (Global)**
*   Responsive horizontal-scroll timeline for the upcoming week.
*   Shows all tasks assigned to the current user across **all projects**.
*   Visual indicators: project context on each card, overdue highlights.

**Project Workspace**
*   **Board:** Kanban for workflow management.
*   **List:** High-density sortable table.


### 3.3 My Inbox View

*   **Trigger:** "Inbox" button located in the **sidebar under "My Calendar"**.
*   **Layout:** Primary view in the main pane (similar to My Calendar).
*   **Content:** 
    *   Responsive grid of recent emails (subject, from, date, snippet).
    *   "Task" button on each email card.
*   **Action:** Clicking "Task" uses AI to extract task details and creates it in the **"General"** project.


*   **Refresh button** (↻) to re-fetch latest emails.
*   Empty state: "No recent emails found. Your inbox is clear or SSO isn't fully linked."

### 3.4 User Settings
*   **Email Automation:** Checkbox to enable/disable automatic background email polling.
    *   When **enabled**: Background worker polls every minute for UNSEEN emails from the last 3 days and creates tasks automatically.
    *   When **disabled**: No automatic polling; manual inbox access is still available.

### 3.5 AI Feature Access Points

#### 🤖 AI Planner
*   **Location:** Global header "AI Plan" button.
*   **Interaction:** Text area for free-form project brain dumps.
*   **Output:** Structured tasks with auto-scheduled due dates (Mon-Fri), auto-assigned to the current user.

#### 📅 AI Schedule
*   **Location:** Calendar view "AI Schedule" button.
*   **Interaction:** One click to redistribute all open/overdue tasks across the next 5 business days.

#### 🔎 Smart Search
*   **Location:** Global header "Smart Search..." input.
*   **Interaction:** Semantic search across all issues using vector embeddings.

#### 🪄 Other AI Tools (in Issue Detail / Create dialogs)
*   **Auto-Triage:** Suggests priority on new issues.
*   **Similar Issues:** Detects likely duplicates during creation.
*   **AI Summary:** Generates per-issue summary + next steps.
*   **AI Filters:** Natural language filters in List View.
*   **Client Update:** Drafts weekly status summaries per project.
*   **Detect Dependencies:** Identifies blocking relationships between issues.

---

## 4. Visual Indicators
Consistent across Board, List, and Calendar:
*   **🔴 Overdue:** Red border/background — high urgency, past due date.
*   **🟠 Unscheduled:** Amber border/background — active task with no due date.
*   **🔵 Unassigned:** Blue border/background — active task with no owner.
*   **Priority Pips:** Color-coded dots (Red=Urgent, Orange=High, Blue=Medium, Grey=Low).

---

## 5. Key User Flows

### 5.1 "Email to Task" (Manual)
1. User clicks **"View Inbox"** in the sidebar (under My Calendar).
2. Modal loads the last 3 days of inbox emails via SSO.
3. User reviews an email, clicks **"+ Task"**.
4. AI extracts task details; task is created in the **General** project, assigned to the user.

### 5.2 "Email to Task" (Automatic)
1. User enables **"Email Automation"** in User Settings.
2. System polls the inbox every minute for new unseen emails from the last 3 days.
3. AI processes each email → creates a task in the **General** project, assigned to the user.


### 5.3 "Plan to Execution"
1. User opens **AI Planner** → types a free-form project plan.
2. AI generates structured issues with balanced due dates.
3. User confirms → switches to **Calendar** → clicks **AI Schedule** for final optimization.
4. User opens the **Board** to begin drag-and-drop workflow management.

### 5.4 Sprint Management
1. User views **My Calendar**.
2. Toggles "Show Completed" for progress review.
3. Drags a task to reschedule. Preference is auto-saved.
