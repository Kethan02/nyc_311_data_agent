"""The starter's agent loop, session store, and FastAPI routes."""

import json
import os
import uuid
from pathlib import Path

import litellm
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from tools import TOOLS, run_tool

load_dotenv(Path(__file__).with_name(".env"))
MODEL = os.getenv("MODEL", "vertex_ai/gemini-3.5-flash-lite")
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """You are NYC 311 Scout, helping New Yorkers understand reported
nuisances before choosing where to live. Be concise, specific, and conversational.
Use the tools for all claims about report counts, comparisons, or trends. Never
make up data. Ask for a five-digit NYC ZIP code if none is provided; do not guess
a neighborhood's ZIP. Remember ZIPs, date windows, and concerns from this chat.
Default to the last 30 complete days. Supported concerns are noise, sanitation,
rodents, housing, and parking. Use compare_zip_priorities when the user compares
places based on what bothers them, and get_concern_trend for changes over time.
Explain the result in plain language, give the period, and name NYC Open Data 311
as the source. If tools return errors or no reports, explain that instead of
claiming the ZIP has no problems. When comparing, name each ZIP and show counts
alongside shares. Lower counts or shares do not prove better living conditions.
311 records are resident reports, not verified incidents or measurements of noise,
safety, cleanliness, or habitability. Population and reporting habits differ;
these are not population-adjusted rates. ZIPs do not exactly match neighborhoods.
Use the tool's definitions: concerns can overlap, 'other' topics are not counted
as selected concerns, and a submitted date does not establish time of an incident.
Never label a place safe/unsafe or assign an overall quality-of-life score. Mention
the relevant caveat briefly, rather than repeating a long disclaimer every turn.
Offer a useful follow-up, such as examining the trend for the user's main concern.
"""


def run_agent(messages: list[dict]) -> tuple[str, list[dict]]:
    """Call Gemini, execute requested tools, then send results back to Gemini."""
    tool_calls = []
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            reply = litellm.completion(
                model=MODEL,
                vertex_location=os.getenv("VERTEXAI_LOCATION", "global"),
                messages=messages,
                tools=TOOLS,
            ).choices[0].message
        except Exception as error:
            # Keep any completed tool calls visible even if a later model call fails.
            return (
                f"Gemini request failed ({type(error).__name__}). Check your model, "
                "credentials, billing, and network connection, then try again.",
                tool_calls,
            )

        messages.append(reply.model_dump())
        if not reply.tool_calls:
            return reply.content or "Please try rephrasing your question.", tool_calls

        for call in reply.tool_calls:
            try:
                args = json.loads(call.function.arguments)
                result = run_tool(call.function.name, args)
            except json.JSONDecodeError:
                args = {"invalid_arguments": call.function.arguments}
                result = json.dumps({"error": "Arguments must be a JSON object. Retry the tool."})
            tool_calls.append({"name": call.function.name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return "I reached the tool-call limit. Try asking about one ZIP or concern at a time.", tool_calls


# Sessions last while this process runs. See README for Cloud Run limitations.
sessions: dict[str, list] = {}
app = FastAPI(title="NYC 311 Scout")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: list[dict]


@app.get("/")
def index():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    sessions[session_id].append({"role": "user", "content": request.message})
    response, tool_calls = run_agent(sessions[session_id])
    return ChatResponse(response=response, session_id=session_id, tool_calls=tool_calls)


@app.post("/clear")
def clear(session_id: str | None = None):
    sessions.pop(session_id, None)
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
