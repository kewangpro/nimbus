import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from app.core import ai
from app.schemas.issue import IssueCreate
from app.models.issue import IssuePriority

class EmailProcessor:
    def __init__(self):
        self.base_system_prompt = (
            "You are an AI assistant for Nimbus, a project management tool.\n"
            "Your goal is to extract REAL, ACTIONABLE tasks from the email provided below.\n\n"
            "### CRITICAL EXTRACTION RULES ###\n"
            "1. ACTIONABLE ONLY: Only extract items that require a specific action from the user (e.g., 'Reply to client', 'Fix bug', 'Prepare presentation').\n"
            "2. IGNORE BOILERPLATE: Absolutely ignore all marketing footers, navigation links, and legal text. Examples of things to IGNORE:\n"
            "   - 'Unsubscribe', 'Manage Preferences', 'View in Browser'\n"
            "   - 'Help Center', 'Questions?', 'Contact Support', 'More Info'\n"
            "   - 'Privacy Policy', 'Terms of Service', 'Copyright 2026'\n"
            "   - Social media links (Facebook, Twitter, etc.)\n"
            "3. NO HALLUCINATIONS: Only extract tasks mentioned in the email body. Do not invent tasks.\n"
            "4. EMPTY LIST: If the email is an advertisement, newsletter, receipt, or notification with NO actionable tasks for the user, return an empty list: [].\n"
            "   - EXAMPLE: An email announcing a new movie on Netflix with links like 'Watch Trailer' or 'Add to My List' is NOT actionable. Return [].\n\n"
            "### OUTPUT FORMAT ###\n"
            "Respond ONLY with a valid JSON list of objects. No comments, no markdown code blocks, no preamble.\n"
            "Each object must have these keys:\n"
            "- 'title': concise summary\n"
            "- 'description': detailed explanation\n"
            "- 'priority': 'low', 'medium', 'high', or 'urgent'\n"
            "- 'due_date': 'YYYY-MM-DD' or null\n\n"
            "### EXAMPLES ###\n\n"
            "Email Subject: Action Needed: Approve Expense Report\n"
            "Email Body: Please approve the latest report by Friday.\n"
            "Response: "
            '[{"title": "Approve Expense Report", "description": "Approve the latest report mentioned in the email", "priority": "high", "due_date": "2026-06-12"}]\n\n'
            "Email Subject: New Movies this Weekend\n"
            "Email Body: Netflix: Watch Trailer | Add to My List | Unsubscribe\n"
            "Response: []\n\n"
            "### CRITICAL REMINDER ###\n"
            "IGNORE ALL FOOTERS. DO NOT EXTRACT 'Unsubscribe', 'Questions?', 'More Info', etc. "
            "If no real work task exists, return [].\n"
            "Respond ONLY with JSON."
        )

    async def extract_task(self, subject: str, body: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
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
        tasks = ai.parse_json_robust(response_text)
        if tasks is not None:
            if isinstance(tasks, dict):
                tasks = [tasks]
            if isinstance(tasks, list):
                # Filter out any non-dict items and validate required keys
                return [t for t in tasks if isinstance(t, dict) and "title" in t]
        return None


email_processor = EmailProcessor()
