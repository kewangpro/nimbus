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
            "You are an AI assistant for Nimbus, a project management tool. "
            "Convert the following email into a structured task. "
            "Extract a clear title, a detailed description, a priority, and a suggested due date if mentioned. "
            "Priority must be one of: low, medium, high, urgent. "
            "Due date must be in YYYY-MM-DD format. "
            "Respond ONLY with a JSON object."
        )

    async def extract_task(self, subject: str, body: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        # Truncate extremely long email bodies to prevent stalling or crashing the local LLM
        max_body_len = 10000
        if len(body) > max_body_len:
            print(f"WARNING: Email body length ({len(body)}) exceeds limit. Truncating to {max_body_len} characters to protect local LLM.")
            body = body[:max_body_len] + "\n\n... [Email body truncated by Nimbus for length] ..."

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
        
        # Try full parse first (either as object or array)
        try:
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            parsed = json.loads(clean_text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass

        # If full parse failed, use a robust brace-matching parser to recover individual objects
        try:
            recovered_objects = []
            last_end_idx = 0
            for match in re.finditer(r'\{', response_text):
                start_idx = match.start()
                if start_idx < last_end_idx:
                    continue  # Skip nested objects that were already parsed as part of a parent object
                depth = 0
                for i in range(start_idx, len(response_text)):
                    if response_text[i] == '{':
                        depth += 1
                    elif response_text[i] == '}':
                        depth -= 1
                        if depth == 0:
                            candidate = response_text[start_idx:i+1]
                            try:
                                obj = json.loads(candidate)
                                if isinstance(obj, dict):
                                    recovered_objects.append(obj)
                                    last_end_idx = i + 1
                            except Exception:
                                pass
                            break
            if recovered_objects:
                if len(recovered_objects) == 1:
                    return recovered_objects[0]
                return recovered_objects
        except Exception as e:
            print(f"Error recovering JSON objects from AI response: {e}")
            
        return None

email_processor = EmailProcessor()
