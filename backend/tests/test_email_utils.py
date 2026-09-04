import pytest
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.email_utils import clean_email_html, extract_email_body_from_message


def test_clean_email_html_strips_style_and_script():
    raw = """
    <html>
      <head>
        <style>
          body { color: red; }
          @media screen and (max-width: 600px) { .header { font-size: 12px !important; } }
        </style>
        <script>alert("test");</script>
      </head>
      <body>
        <h1>Hello World</h1>
        <p>This is a test email &amp; special offer.</p>
        <br>
        <div>Contact: service@example.com</div>
      </body>
    </html>
    """
    cleaned = clean_email_html(raw)
    assert "color: red" not in cleaned
    assert "@media" not in cleaned
    assert "alert" not in cleaned
    assert "Hello World" in cleaned
    assert "This is a test email & special offer." in cleaned
    assert "Contact: service@example.com" in cleaned


def test_clean_email_html_empty():
    assert clean_email_html("") == ""
    assert clean_email_html(None) == ""


def test_clean_email_html_zero_width_chars():
    raw = "<p>Title\u200b\ufeff\u00ad\u2007</p>"
    cleaned = clean_email_html(raw)
    assert cleaned == "Title"


def test_extract_email_body_clean_plain_text():
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText("This is pure plain text.", "plain"))
    msg.attach(MIMEText("<p>This is HTML.</p>", "html"))

    body = extract_email_body_from_message(msg)
    assert body == "This is pure plain text."


def test_extract_email_body_html_fallback():
    msg = MIMEMultipart()
    msg.attach(MIMEText("<p>Only HTML is provided.<br>Second line.</p>", "html"))

    body = extract_email_body_from_message(msg)
    assert "Only HTML is provided." in body
    assert "Second line." in body


def test_extract_email_body_corrupted_plain_text_falls_back_to_html():
    msg = MIMEMultipart("alternative")
    corrupted_plain = "@media screen and (max-width: 450px) { table{zoom:100%}.link{color:inherit !important} }"
    html_content = "<style>.link{color:red;}</style><p>Real human message content here.</p>"
    msg.attach(MIMEText(corrupted_plain, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    body = extract_email_body_from_message(msg)
    assert "Real human message content here." in body
    assert "@media" not in body
    assert "!important" not in body


def test_extract_email_body_single_part_html():
    msg = MIMEText("<style>body{color:black}</style><p>Single part message</p>", "html")
    body = extract_email_body_from_message(msg)
    assert body == "Single part message"
    assert "body{color:black}" not in body


def test_extract_email_body_single_part_plain():
    msg = MIMEText("Single part plain text", "plain")
    body = extract_email_body_from_message(msg)
    assert body == "Single part plain text"
