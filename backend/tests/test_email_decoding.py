import pytest
from app.core.email_polling import decode_mime_header

def test_decode_mime_header_vimeo_example():
    # The specific string provided by the user
    encoded_subject = "=?utf-8?Q?Vimeo=E2=80=99s?= subtitle trick =?utf-8?Q?=F0=9F=8E=A5=2C?= AI for better code =?utf-8?Q?=F0=9F=93=88=2C?= teachable AI agents =?utf-8?Q?=F0=9F=8E=93=C2=A0?="
    decoded = decode_mime_header(encoded_subject)
    
    # Check for key content
    assert "Vimeo’s" in decoded
    assert "subtitle trick" in decoded
    assert "🎥" in decoded
    assert "AI for better code" in decoded
    assert "📈" in decoded
    assert "teachable AI agents" in decoded
    assert "🎓" in decoded

def test_decode_mime_header_plain_text():
    assert decode_mime_header("Just a plain subject") == "Just a plain subject"

def test_decode_mime_header_empty():
    assert decode_mime_header("") == ""
    assert decode_mime_header(None) == ""

def test_decode_mime_header_mixed():
    mixed = "Hello =?utf-8?Q?=F0=9F=91=8B?="
    assert decode_mime_header(mixed) == "Hello 👋"
