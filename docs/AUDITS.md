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

## Log Data Structure
Each audit log entry captures:
- `user_id`: The ID of the user who performed the action.
- `action`: The specific action key (e.g., `issue.update`).
- `entity_type`: The type of resource mutated (e.g., `issue`, `project`).
- `entity_id`: The unique identifier corresponding to that specific entity.
- `details`: (Optional) Additional contextual metadata regarding the change.
- `created_at`: The precise UTC timestamp when the action occurred.

## Extensibility 

The `crud_audit.log_action()` helper makes it simple to extend auditing to other resources (like comments, user management, or integrations).
