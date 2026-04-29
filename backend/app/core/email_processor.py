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
            "You are an AI assistant for Nimbus, a project management tool. "
            "Convert the following email into a structured task. "
            "Extract a clear title, a detailed description, a priority, and a suggested due date if mentioned. "
            "Priority must be one of: low, medium, high, urgent. "
            "Due date must be in YYYY-MM-DD format. "
            "Respond ONLY with a JSON object."
        )

    async def extract_task(self, subject: str, body: str) -> Optional[Dict[str, Any]]:
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = (
            f"{self.base_system_prompt} "
            f"The current date is {current_date}. If a date is mentioned without a year, "
            f"infer the most logical year relative to today."
        )
        prompt = f"Email Subject: {subject}\n\nEmail Body:\n{body}"
        
        response_text = await ai.generate_completion(prompt, system_prompt=system_prompt)
        if not response_text:
            return None
        
        try:
            # Try to find JSON in the response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                task_data = json.loads(json_match.group(0))
                return task_data
        except Exception as e:
            print(f"Error parsing AI response for email: {e}")
            
        return None

email_processor = EmailProcessor()
