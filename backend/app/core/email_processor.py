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
            "Convert the following email into one or more structured tasks. "
            "For each task, extract: "
            "- title: a clear, concise summary of the task"
            "- description: a detailed explanation of what needs to be done"
            "- priority: one of 'low', 'medium', 'high', or 'urgent'"
            "- due_date: YYYY-MM-DD format if mentioned, otherwise null\n\n"
            "Respond ONLY with a JSON list of objects. Do not include any other text.\n"
            "Example response format (always return a list):\n"
            '[{"title": "Task title", "description": "Task description", "priority": "medium", "due_date": null}]'
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
        if not response_text or not response_text.strip():
            return None
        
        # Try full parse first (either as object or array)
        try:
            clean_text = response_text.strip()
            # Remove markdown code blocks if present
            clean_text = re.sub(r'^```json\s*', '', clean_text, flags=re.MULTILINE)
            clean_text = re.sub(r'\s*```$', '', clean_text, flags=re.MULTILINE)
            clean_text = clean_text.strip()
            
            parsed = json.loads(clean_text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception as e:
            # We will try recovery next, so no need to log error here yet
            pass

        # If full parse failed, use a robust brace-matching parser to recover individual objects
        try:
            recovered_objects = []
            # Look for JSON objects {...} or arrays [...]
            # This regex is a bit naive but can help skip conversational filler
            potential_jsons = re.findall(r'(\{.*\}|\[.*\])', response_text, re.DOTALL)
            
            for candidate in potential_jsons:
                try:
                    # Clean up the candidate in case it has trailing/leading junk from the greedy dotall
                    # Try to find the first '{' and last '}'
                    start_brace = candidate.find('{')
                    end_brace = candidate.rfind('}')
                    if start_brace != -1 and end_brace != -1:
                        obj_text = candidate[start_brace:end_brace+1]
                        obj = json.loads(obj_text)
                        if isinstance(obj, dict):
                            recovered_objects.append(obj)
                        elif isinstance(obj, list):
                            recovered_objects.extend([o for o in obj if isinstance(o, dict)])
                except Exception:
                    continue

            if recovered_objects:
                if len(recovered_objects) == 1:
                    return recovered_objects[0]
                return recovered_objects
            
            # Last ditch effort: simple brace matching for multiple objects
            last_end_idx = 0
            for match in re.finditer(r'\{', response_text):
                start_idx = match.start()
                if start_idx < last_end_idx:
                    continue
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

            print(f"Failed to recover any JSON objects from AI response. Raw response: {response_text}")
        except Exception as e:
            print(f"Error recovering JSON objects from AI response: {e}. Raw response: {response_text}")

            
        return None

email_processor = EmailProcessor()
