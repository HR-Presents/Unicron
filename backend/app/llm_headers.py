"""Keep authenticated Qwen endpoint credentials on the server."""
import os

def completion_headers():
    headers = {'Content-Type': 'application/json'}
    token = os.getenv('CIVITAS_LLM_API_KEY', '').strip()
    if token:
        headers['Authorization'] = 'Bearer ' + token
    return headers
