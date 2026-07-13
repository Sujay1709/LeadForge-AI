"""Agent definitions for lead generation workflow.

Uses google-genai SDK directly (no phidata) for Python 3.14 compatibility.
Composio runs in a subprocess to isolate potential segfaults on Python 3.14.
"""

import json
import subprocess
import sys
import tempfile
import os
from typing import List
from google import genai
from config import DEFAULT_MODEL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Query Transform Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TRANSFORM_PROMPT = """Transform detailed queries into concise descriptions (3-6 words).

Examples:
Input: "Looking for users who need AI video editing software"
Output: AI video editing software

Input: "Find SaaS founders who struggle with customer onboarding"
Output: SaaS customer onboarding tools

Input: "Looking for companies that need a better CRM for small sales teams"
Output: best CRM small sales team

Input: "Find businesses looking to automate their invoice and billing process"
Output: automate invoicing billing software

Input: "Find marketing managers who need help with SEO and organic traffic growth"
Output: SEO organic traffic growth tools

Input: "Looking for e-commerce store owners struggling with email marketing automation"
Output: ecommerce email marketing automation

Input: "Find engineering teams looking for CI/CD pipeline improvements"
Output: CI CD pipeline best practices

Input: "Find HR teams that need applicant tracking systems for high-volume hiring"
Output: applicant tracking system hiring

Input: "Find CFOs looking for better financial forecasting and budgeting tools"
Output: financial forecasting budgeting software

Input: "Find healthcare providers looking for patient scheduling and telehealth platforms"
Output: patient scheduling telehealth platform

Rules:
- Return ONLY the concise description, nothing else.
- 3-6 words max. Drop filler words.
- Use pain-point language Quora users would search for."""


def create_prompt_transform_agent(google_api_key: str):
    """Create a Gemini client for query transformation."""
    return genai.Client(api_key=google_api_key)


def transform_query(client, user_query: str) -> str:
    """Transform a verbose lead query into a concise search phrase."""
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=f'{TRANSFORM_PROMPT}\n\nInput: "{user_query}"\nOutput:',
    )
    return response.text.strip().strip('"').strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Google Sheets Export (subprocess-isolated)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_SHEETS_SCRIPT = '''
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

api_key = sys.argv[1]
data_file = sys.argv[2]

with open(data_file) as f:
    leads = json.load(f)

from composio import Composio
composio = Composio(api_key=api_key)

result = composio.tools.execute(
    user_id="default",
    slug="GOOGLESHEETS_SHEET_FROM_JSON",
    arguments={
        "title": "AI Lead Generation Results",
        "json_data": json.dumps(leads),
    },
    dangerously_skip_version_check=True,
)

if isinstance(result, dict):
    if result.get("error"):
        print(json.dumps({"error": result["error"]}))
    else:
        data = result.get("data", result)
        if isinstance(data, dict):
            url = data.get("spreadsheet_url") or data.get("url") or str(data)
        else:
            url = str(data)
        print(json.dumps({"url": url}))
else:
    print(json.dumps({"url": str(result)}))
'''


def write_to_google_sheets(
    flattened_data: List[dict],
    composio_api_key: str,
) -> str:
    """Create a Google Sheet with lead data using Composio.

    Runs in a subprocess to prevent Python 3.14 segfaults from crashing
    the main Streamlit process.
    """
    # Write leads to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(flattened_data, f)
        data_file = f.name

    # Write the script to a temp file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "_sheets_export.py")
    with open(script_path, "w") as f:
        f.write(_SHEETS_SCRIPT)

    try:
        result = subprocess.run(
            [sys.executable, script_path, composio_api_key, data_file],
            capture_output=True, text=True, timeout=60,
            cwd=script_dir,
        )

        # Clean up
        os.unlink(data_file)
        if os.path.exists(script_path):
            os.unlink(script_path)

        if result.returncode != 0:
            stderr = result.stderr.strip()
            # Check if it's a segfault
            if result.returncode < 0:
                return f"Error: Composio crashed (signal {-result.returncode}). Google Sheets export unavailable on Python 3.14."
            return f"Error: {stderr[-200:]}" if stderr else "Error: Export failed"

        stdout = result.stdout.strip()
        if not stdout:
            return "Error: No response from export"

        parsed = json.loads(stdout)
        return parsed.get("url") or parsed.get("error") or str(parsed)

    except subprocess.TimeoutExpired:
        os.unlink(data_file)
        return "Error: Export timed out after 60s"
    except Exception as e:
        return f"Error: {e}"
