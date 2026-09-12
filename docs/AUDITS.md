# Audit Logs

The Nimbus application tracks and audits significant changes across the workspace. This ensures accountability and visibility into who performs which actions. 

Audit logs can be viewed securely from the **Activity / Audit Logs** icon located in the main header of the dashboard, next to the User Settings.

## Audited Actions

Currently, the system audits the following core entities:

### 📁 Projects
Actions related to the creation, modification, and deletion of user workspaces (projects).

| Action Type | Trigger Description |
| :--- | :--- |
| `project.create` | When a user creates a new project workspace. |
| `project.update` | When a user modifies project details (e.g., renaming the project). |
| `project.delete` | When a user deletes an entire project and its contents. |

### 📝 Issues
Actions related to task (issue) management within projects.

| Action Type | Trigger Description |
| :--- | :--- |
| `issue.create` | When a user creates a new issue on the board or list. |
| `issue.update` | When an issue is updated (e.g., status changed, assignee updated, description modified). |
| `issue.delete` | When an issue is permanently removed from the system. |
| `issue.backfill` | When AI embeddings are backfilled for existing issues. |
| `ai_schedule` | When the [AI Schedule](#📅-ai-schedule) organizes your tasks for the week. |

### 👤 User & Auth
Actions related to user accounts and authentication.

| Action Type | Trigger Description |
| :--- | :--- |
| `auth.login` | When a user logs in via SSO (Gmail/Outlook). |
| `auth.login_failed` | When an SSO login attempt fails during token exchange. |
| `user.update_me` | When a user updates their own profile details. |

### ✉️ Email Integrations
Actions related to the email-to-task automation.

| Action Type | Trigger Description | Error Classification |
| :--- | :--- | :--- |
| `email.task_created` | When a task is automatically created from a polled email. | Success |
| `email.task_created_manual` | When a user manually creates a task from their inbox. | Success |
| `email.task_creation_failed` | When an error occurs while creating a task from an email. | **Permanent Failure** (`is_transient: false`): Mark email `\Seen` and record in audit log to isolate poison-pill emails and avoid infinite retry loops. |
| `email.token_refresh_failed` | When OAuth access token refresh fails. Throttled to max 1 per hour per user. | **Transient** (`is_transient: true`) for HTTP 5xx or network drops; **Permanent** (`is_transient: false`) for HTTP 400/401 (e.g. expired client secret or missing token, requiring re-login). |
| `email.auth_failed` | When IMAP XOAUTH2 authentication is still rejected after forcing an OAuth token refresh and retrying IMAP in the same poll. Throttled to max 1 per hour per user. | **Permanent** (`is_transient: false`): Access token was stale or revoked; a same-cycle refresh+IMAP retry already failed, so the user must re-authenticate. A first IMAP `NO` is treated as a stale-token retry and is not logged. |
| `email.connection_failed` | When connection to the IMAP server fails or times out. Throttled to max 1 per hour per user. | **Transient** (`is_transient: true`): Poller auto-retries in 3s, and background worker retries every 60s. Unread emails remain `UNSEEN` and are preserved for subsequent processing. |
| `email.connection_recovered` | When IMAP connection and authentication succeed following a previous connection failure or auth failure. | **Recovery Success**: Confirms background retries succeeded and connection/auth is restored. |
| `email.ignored` | When a polled email does not contain actionable tasks (e.g., promotional ad or newsletter). | Informational (Non-Task) |

### 📂 Files
Actions related to file management.

| Action Type | Trigger Description |
| :--- | :--- |
| `file.upload` | When a user uploads a file/attachment. |

## Log Data Structure
Each audit log entry captures:
- `user_id`: The ID of the user who performed the action.
- `action`: The specific action key (e.g., `issue.update`).
- `entity_type`: The type of resource mutated (e.g., `issue`, `project`).
- `entity_id`: The unique identifier corresponding to that specific entity.
- `details`: Rich contextual metadata including:
    - `title` / `name`: The human-readable identifier of the entity (persisted even if the entity is deleted).
    - `changes`: An array of field names that were modified during an update (e.g., `["status", "priority", "due_date"]`).
    - `via`: Identifies the system/tool that triggered the update (e.g., `ai_scheduler`).
    - `email_subject`: For tasks created from email.
    - `filename`: For file uploads.
    - `error_class`: Classification of integration errors (`"transient"` vs `"permanent"`).
    - `is_transient`: Boolean flag indicating whether the failure is transient (auto-retrying in background) or permanent (requires user/admin action).
    - `error_description`: Human-readable explanation of why the failure occurred.
- `created_at`: The precise UTC timestamp when the action occurred.

## Extensibility 

The `crud_audit.log_action()` helper makes it simple to extend auditing to other resources (like comments, user management, or integrations).

