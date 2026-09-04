import html
import re
from email.message import Message


def clean_email_html(raw_html: str) -> str:
    """
    Cleans raw HTML email content to produce clean, readable plain text.
    - Strips <style> and <script> tags and all their inner CSS/JS contents
    - Converts line-break and block-level tags to newlines
    - Strips remaining HTML tags
    - Unescapes HTML entities (&amp;, &nbsp;, etc.)
    - Removes zero-width preheader padding characters
    - Normalizes spacing and line breaks
    """
    if not raw_html:
        return ""

    # 1. Remove style and script tags along with their inner contents
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', raw_html, flags=re.IGNORECASE)
    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', text, flags=re.IGNORECASE)

    # 2. Convert common block-level / line-break HTML elements to newlines
    text = re.sub(r'<(?:br|br\s*/|/p|/div|/tr|/li|/h[1-6])\s*>', '\n', text, flags=re.IGNORECASE)

    # 3. Strip all remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # 4. Decode HTML entities (&nbsp;, &amp;, &quot;, &#39;, etc.)
    text = html.unescape(text)

    # 5. Remove non-printable / zero-width formatting characters commonly found in email preheaders
    text = re.sub(r'[\u034f\u200b-\u200f\ufeff\u00ad\u2007\u2008]+', '', text)

    # 6. Normalize whitespace on each line while preserving paragraphs
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    text = '\n'.join(lines)

    # 7. Collapse 3+ consecutive newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_email_body_from_message(msg: Message) -> str:
    """
    Extracts clean plain text body from an email Message.
    Prefers text/plain part unless it is corrupted with raw CSS stylesheets,
    in which case it falls back to cleaned text/html.
    """
    plain_text = ""
    html_candidate = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not plain_text:
                payload = part.get_payload(decode=True)
                if payload:
                    plain_text = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
            elif ct == "text/html" and not html_candidate:
                payload = part.get_payload(decode=True)
                if payload:
                    html_candidate = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            raw_payload = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
            if msg.get_content_type() == "text/html":
                html_candidate = raw_payload
            else:
                plain_text = raw_payload

    # Detect if plain_text is actually garbage CSS (e.g. newsletter senders who dump stylesheets into plain_text)
    is_css_garbage = bool(re.search(r'(@media|@font-face|!important|\{[a-z\-]+:[^\}]*\})', plain_text, re.IGNORECASE))
    if plain_text and not is_css_garbage:
        return plain_text.strip()
    if html_candidate:
        return clean_email_html(html_candidate)
    return plain_text.strip()
