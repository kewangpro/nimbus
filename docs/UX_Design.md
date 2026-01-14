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

### 3.1 The Multi-View Dashboard
Users can toggle between three primary contexts:
1.  **Board:** Kanban style for workflow management.
2.  **Calendar (5-Day Sprint):** A focused view of the upcoming work week with daily columns. Supports drag-and-drop rescheduling.
3.  **List:** High-density view for bulk review.

### 3.2 AI Feature Access Points

#### ✨ Smart Search (Global)
*   **Location:** Header (accessible via Cmd+K).
*   **Interaction:** A modal dialog where users type natural language. Results appear as cards ranked by semantic relevance.

#### 🤖 AI Planner (Strategic)
*   **Location:** Header "AI Plan" button.
*   **Interaction:** A large text area for "brain dumping" project ideas. AI breaks it down into a reviewable list of tasks with pre-set priority/status.

#### 📅 AI Schedule (Tactical)
*   **Location:** Calendar View header ("AI Schedule").
*   **Interaction:** A single click that reorganizes open tasks into a balanced 5-day schedule, preventing overload.

#### 🪄 AI Auto-Triage (Operational)
*   **Location:** "New Issue" modal.
*   **Interaction:** A "Wand" button next to Priority that fills in fields based on the current title/description.

### 3.3 Issue Detail Modal
*   **Trigger:** Click on any issue in Board, Calendar, or List.
*   **Features:**
    *   Editable Title and Description.
    *   Dropdowns for Status and Priority.
    *   Delete functionality.
    *   Meta information (ID, Created At).

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
