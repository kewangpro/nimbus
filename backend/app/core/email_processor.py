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
            model_name="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
        )
        if not response_text or not response_text.strip():
            return None
        
        # Pre-clean: remove common AI errors like comments
        clean_text = response_text.strip()
        # Remove markdown code blocks if present (more robustly)
        clean_text = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', clean_text, flags=re.DOTALL | re.IGNORECASE)
        # If still has one-sided markers
        clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text, flags=re.MULTILINE | re.IGNORECASE)
        clean_text = re.sub(r'\s*```$', '', clean_text, flags=re.MULTILINE)
        
        # Remove trailing comments (e.g., # or //) that break JSON, but only if they are at the end of a line
        # and not part of a string (this is naive but handles common AI output)
        clean_text = re.sub(r'[ \t]+[#//].*$', '', clean_text, flags=re.MULTILINE)
        clean_text = clean_text.strip()

        # Try full parse first (either as object or array)
        tasks = None
        try:
            tasks = json.loads(clean_text)
        except Exception:
            # Try ast.literal_eval for single-quoted "JSON"
            try:
                import ast
                # Prepare for Python eval by mapping JSON constants
                eval_text = clean_text.replace('null', 'None').replace('true', 'True').replace('false', 'False')
                tasks = ast.literal_eval(eval_text)
            except Exception:
                pass

        if tasks is not None:
            if isinstance(tasks, dict):
                tasks = [tasks]
            if isinstance(tasks, list):
                # Filter out any non-dict items and validate required keys
                return [t for t in tasks if isinstance(t, dict) and "title" in t]

        # If full parse failed, use a robust brace-matching parser to recover individual objects
        try:
            recovered_objects = []
            # Look for JSON objects {...} or arrays [...]
            potential_jsons = re.findall(r'(\{.*\}|\[.*\])', clean_text, re.DOTALL)
            
            for candidate in potential_jsons:
                try:
                    start_brace = candidate.find('{')
                    end_brace = candidate.rfind('}')
                    if start_brace != -1 and end_brace != -1:
                        obj_text = candidate[start_brace:end_brace+1]
                        # Clean comments again within the object text
                        obj_text = re.sub(r'\s*[#//].*$', '', obj_text, flags=re.MULTILINE)
                        obj = json.loads(obj_text)
                        if isinstance(obj, dict):
                            recovered_objects.append(obj)
                        elif isinstance(obj, list):
                            recovered_objects.extend([o for o in obj if isinstance(o, dict)])
                except Exception:
                    continue

            if recovered_objects:
                return [t for t in recovered_objects if "title" in t]
            
            # Last ditch effort: simple brace matching for multiple objects
            last_end_idx = 0
            for match in re.finditer(r'\{', clean_text):
                start_idx = match.start()
                if start_idx < last_end_idx:
                    continue
                depth = 0
                for i in range(start_idx, len(clean_text)):
                    if clean_text[i] == '{':
                        depth += 1
                    elif clean_text[i] == '}':
                        depth -= 1
                        if depth == 0:
                            candidate = clean_text[start_idx:i+1]
                            try:
                                obj = json.loads(candidate)
                                if isinstance(obj, dict):
                                    recovered_objects.append(obj)
                                    last_end_idx = i + 1
                            except Exception:
                                pass
                            break
            
            if recovered_objects:
                return [t for t in recovered_objects if "title" in t]

            print(f"Failed to recover any JSON objects from AI response. Raw response: {response_text}")
        except Exception as e:
            print(f"Error recovering JSON objects from AI response: {e}. Raw response: {response_text}")

        return None


email_processor = EmailProcessor()
