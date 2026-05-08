"""
Kairos AI — Agent Base (Google ADK)
Uses Google's official Agent Development Kit (google-adk).

Framework: google-adk (pip install google-adk)
Docs: https://google.github.io/adk-docs/

This provides:
- LlmAgent: The core agent that uses Gemini to reason + call tools
- Runner: Executes the agent loop (THINK → ACT → OBSERVE)
- InMemorySessionService: Manages conversation state
- FunctionTool: Wraps Python functions as agent tools
"""
import os
import asyncio
import uuid
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ──────────────────────────────────────────────
# Session service (shared across all agents)
# ──────────────────────────────────────────────
session_service = InMemorySessionService()

APP_NAME = "kairos_ai"


async def run_agent(
    agent: LlmAgent,
    user_message: str,
    user_id: str = None,
    session_id: str = None
) -> dict:
    """
    Run a Google ADK agent and return its final response.
    
    This is the standard way to invoke any ADK agent:
    1. Create a session
    2. Create a runner
    3. Send a message and collect the final response
    
    Args:
        agent: An LlmAgent instance with tools and instructions
        user_message: The task/query for the agent
        user_id: Optional user identifier
        session_id: Optional session identifier
        
    Returns:
        dict with 'response' (text), 'events' (all events), 'session_id'
    """
    if not user_id:
        user_id = f"kairos_{uuid.uuid4().hex[:8]}"
    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    # Create session
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )

    # Create runner for this agent
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    # Build user message
    content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)]
    )

    # Run the agent and collect events
    final_text = ""
    all_events = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    ):
        all_events.append({
            "id": str(event.id) if hasattr(event, 'id') else "unknown",
            "author": str(event.author) if hasattr(event, 'author') else "unknown",
        })

        # Log tool calls for visibility
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    print(f"  [{agent.name}] TOOL_CALL: {part.function_call.name}({dict(part.function_call.args) if part.function_call.args else {}})")
                if hasattr(part, 'function_response') and part.function_response:
                    print(f"  [{agent.name}] TOOL_RESULT: {part.function_response.name}")

        # Capture final response
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    final_text = part.text.strip()

    print(f"[{agent.name}] Final: {final_text[:200]}...")

    return {
        "response": final_text,
        "events": all_events,
        "session_id": session_id
    }
