# Nimbus Frontend ☁️

The frontend for **Nimbus**, an AI-native project management system. Built with Next.js 15 App Router, Tailwind CSS, Shadcn/UI, and React Query.

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ (tested on Node.js 20 & 25)
- npm or yarn

### Installation
```bash
npm install
```

### Environment Variables
Create a `.env.local` file in the `frontend` directory:
```ini
NEXT_PUBLIC_API_URL=http://localhost:8100/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8100/api/v1/ws
```

### Development Server
Run the local dev server on port 3100:
```bash
PORT=3100 npm run dev
```
Open [http://localhost:3100](http://localhost:3100) with your browser.

## 🧪 Testing & Verification

Nimbus includes unit tests using Node.js's native test runner:
```bash
npm test
```
This runs the unit test suites (such as `lib/sprint-plan.test.ts` for sprint boundary calculation, weekend skipping, and overdue lookback rules).

To run a production build verification:
```bash
npm run build
```

## 🏗️ Architecture & Views
- **`components/calendar-view.tsx`**: Bounded 2-week sprint timeline (10 weekdays + up to 7-day overdue lookback), real-time AI schedule progress bar (`GET /api/v1/ai/schedule/progress`), and outlier dropdown menu.
- **`components/board-view.tsx`**: Drag-and-drop Kanban board with optimistic React Query mutations.
- **`components/list-view.tsx`**: High-density sortable and filterable task list with overdue indicators.
- **`components/inbox-modal.tsx`**: SSO-linked IMAP email inbox with manual and bulk task conversion.
- **`lib/sprint-plan.ts`**: Pure calculation functions for 10-weekday sprint windowing, weekend avoidance, and outlier detection.
- **`lib/api.ts`**: API client for the FastAPI backend with token management and auto-retry.
