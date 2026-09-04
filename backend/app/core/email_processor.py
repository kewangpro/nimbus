import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
from app.core import ai
from app.schemas.issue import IssueCreate
from app.models.issue import IssuePriority

class EmailProcessor:
    def __init__(self):
        self.base_system_prompt = (
            "You are an AI assistant for Nimbus, a project management tool.\n"
            "Your first job is to filter the email. If the email is a general newsletter, marketing email, advertisement, promotional offer, automated system notification, receipt, or does not contain personal actionable work items or direct requests for the user, you MUST ignore it by returning an empty JSON object {}.\n\n"
            "For emails that DO contain personal actionable requests or tasks for the user, convert them into a structured task and respond ONLY with a single JSON object containing these keys:\n"
            "- 'title': concise summary/title\n"
            "- 'summary': concise summary of the email and key takeaways/action items\n"
            "- 'priority': 'low', 'medium', 'high', or 'urgent'\n"
            "- 'due_date': 'YYYY-MM-DD' or null. ONLY suggest a due date if there is a clear, explicit actionable deadline mentioned in the email (e.g., 'submit by July 15', 'due next Tuesday'). DO NOT use the email's publication date, sent date, or general calendar dates mentioned in newsletters/updates as a due date. If no explicit deadline is mentioned, return null."
        )

    async def extract_task(self, subject: str, body: str) -> Optional[Dict[str, Any]]:
        # Truncate extremely long email bodies to prevent stalling or crashing the local LLM
        max_body_len = 10000
        if len(body) > max_body_len:
            print(f"WARNING: Email body length ({len(body)}) exceeds limit. Truncating to {max_body_len} characters to protect local LLM.")
            body = body[:max_body_len] + "\n\n... [Email body truncated by Nimbus for length] ..."

        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = (
            f"{self.base_system_prompt}\n\n"
            f"The current date is {current_date}. If a date is mentioned without a year, "
            f"infer the most logical year relative to today."
        )
        prompt = f"Email Subject: {subject}\n\nEmail Body:\n{body}"
        
        response_text = await ai.generate_completion(
            prompt, 
            system_prompt=system_prompt,
            model_name=ai.CHAT_MODEL
        )
        if not response_text or not response_text.strip():
            return None
        
        # Use robust shared JSON parser helper
        task_data = ai.parse_json_robust(response_text)
        if isinstance(task_data, list):
            task_data = task_data[0] if task_data else {}
            
        if isinstance(task_data, dict):
            if not task_data:
                return {}
            if "title" in task_data:
                return task_data
        return None


email_processor = EmailProcessor()
