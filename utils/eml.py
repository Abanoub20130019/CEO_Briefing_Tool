import email
from email import policy
from email.parser import BytesParser

def parse_eml_content(file_bytes):
    """
    Parses an EML file (bytes) and returns the plain text body.
    Falls back to simple HTML-to-text if no plain text part is found.
    """
    try:
        msg = BytesParser(policy=policy.default).parsebytes(file_bytes)
        body = ""

        if msg.is_multipart():
            # Iterate parts to find text/plain
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body = part.get_content()
                    break # Prefer the first text/plain part
        else:
            # Not multipart, get payload
            body = msg.get_content()
            
        return body.strip() if body else "[Could not extract text from EML]"
    except Exception as e:
        return f"[Error parsing EML: {str(e)}]"
