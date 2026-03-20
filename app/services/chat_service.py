"""
app/services/chat_service.py

Phase 1: NL Function Calling via Google Gemini.

Orchestrates a conversational loop where:
  1. User sends a natural-language financial question
  2. Gemini decides which wallet tool(s) to call
  3. Tools execute against the user's live snapshot data
  4. Gemini synthesises a plain-language answer

Supports multi-turn tool calls in a single request (Gemini may chain
multiple function calls before producing the final answer).
"""
from __future__ import annotations

import json
import logging
from typing import Any

import google.genai as genai
from google.genai import types as genai_types
from app.config import settings
from app.services.function_tools import GEMINI_TOOL_DECLARATIONS, TOOL_REGISTRY

log = logging.getLogger("chat_service")

_SYSTEM_INSTRUCTION = """
You are ByteWallet AI Assistant — a friendly, empathetic personal finance advisor
for ASEAN youth. Your role is to help users understand their wallet, budget, and
spending habits using real-time data from their wallet.

Guidelines:
- Always use the available tools to fetch real data before answering financial questions.
- Give specific, numerical answers whenever possible (amounts, percentages, dates).
- Communicate in simple, jargon-free language suitable for Gen Z and young adults.
- Be supportive and non-judgmental about spending habits.
- If the user questions involve affordability, always run the appropriate tool first.
- Respond in the same language the user wrote in (English default).
- Keep responses concise — 3 to 5 sentences max unless detail is explicitly requested.
"""


def _build_gemini_tools() -> list:
    """Convert our tool declarations into google.genai Tool format."""
    declarations = []
    for td in GEMINI_TOOL_DECLARATIONS:
        declarations.append(
            genai_types.FunctionDeclaration(
                name=td["name"],
                description=td["description"],
                parameters=td.get("parameters", {}),
            )
        )
    return [genai_types.Tool(function_declarations=declarations)]



def _dispatch_tool(tool_name: str, tool_args: dict, snapshot: dict) -> Any:
    """
    Execute a tool from the registry, injecting the user snapshot as context.
    All tools accept `snapshot` as their first argument; some accept extra kwargs.
    """
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        log.warning(f"Unknown tool requested by LLM: {tool_name}")
        return {"error": f"Tool '{tool_name}' not found."}
    try:
        return fn(snapshot, **tool_args)
    except Exception as e:
        log.error(f"Tool '{tool_name}' raised an error: {e}")
        return {"error": str(e)}


async def answer_user_question(
    question: str,
    snapshot: dict,
    rag_context: str | None = None,
) -> tuple[str, list[str]]:
    """
    Main entry point.

    Args:
        question:    The user's natural language question.
        snapshot:    The raw wallet snapshot dict (PredictBurnRateRequest fields).
        rag_context: Optional extra context from Phase 2 RAG retrieval.

    Returns:
        (answer: str, tools_used: list[str])
    """
    api_key = settings.gemini_api_key
    if not api_key:
        log.warning("GEMINI_API_KEY not set — falling back to rule-based answer.")
        return _rule_based_fallback(question, snapshot), []

    # Build initial prompt — optionally include RAG context
    user_content = question
    if rag_context:
        user_content = (
            f"[Relevant historical context from past transactions]\n{rag_context}\n\n"
            f"[User question]\n{question}"
        )

    # Add basic user context to help LLM choose tools
    currency     = snapshot.get("currency", "VND")
    current_date = snapshot.get("current_date", "unknown")
    system_hint  = (
        f"User context: currency={currency}, current_date={current_date}. "
        f"Use the available tools to answer with real data."
    )
    full_prompt = f"{system_hint}\n\n{user_content}"

    tools_used: list[str] = []

    try:
        client = genai.Client(api_key=api_key)

        # Agentic loop — keep executing until Gemini produces a final text answer
        contents = [genai_types.Content(parts=[genai_types.Part(text=full_prompt)], role="user")]
        tools    = _build_gemini_tools()

        for _turn in range(5):  # max 5 tool-call rounds
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    tools=tools,
                ),
            )

            # Check for function calls
            fn_calls = []
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fn_calls.append(part.function_call)

            if not fn_calls:
                break  # Final text answer

            # Append model's response to conversation history
            contents.append(response.candidates[0].content)

            # Execute each tool and build function response parts
            fn_response_parts = []
            for fc in fn_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                log.info(f"Gemini calling tool: {tool_name} with args {tool_args}")
                tools_used.append(tool_name)

                result = _dispatch_tool(tool_name, tool_args, snapshot)
                fn_response_parts.append(
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=tool_name,
                            response={"result": json.dumps(result, ensure_ascii=False, default=str)},
                        )
                    )
                )

            # Append tool results to conversation
            contents.append(genai_types.Content(parts=fn_response_parts, role="tool"))

        # Extract final answer text
        final_text = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                final_text += part.text

        if not final_text:
            final_text = "Unable to generate an answer. Please check your GEMINI_API_KEY in .env."

        return final_text.strip(), tools_used

    except Exception as e:
        log.error(f"Gemini call failed: {e}")
        return _rule_based_fallback(question, snapshot), []


def _rule_based_fallback(question: str, snapshot: dict) -> str:
    """
    A deterministic fallback answer when Gemini is not configured.
    Uses function_tools directly to compute and answer common questions.
    """
    from app.services.function_tools import get_predicted_burn_rate, get_wallet_balance
    q_lower = question.lower()
    currency = snapshot.get("currency", "VND")

    if any(kw in q_lower for kw in ["balance", "money", "wallet", "how much"]):
        bal = get_wallet_balance(snapshot)
        return (
            f"Current balance: {bal['banking']:,.0f} (banking) + {bal['cash']:,.0f} (cash) "
            f"= {bal['total']:,.0f} {currency}."
        )

    if any(kw in q_lower for kw in ["risk", "burn", "shortfall", "budget"]):
        stats = get_predicted_burn_rate(snapshot)
        return (
            f"Current risk level: {stats['risk_level'].upper()}. "
            f"Shortfall probability: {stats['shortfall_probability'] * 100:.1f}%. "
            f"Projected spend by month-end: {stats['predicted_total_spend']:,.0f} {currency} "
            f"vs. budget of {stats['budget_total']:,.0f} {currency}."
        )

    return (
        "To get AI-powered answers to financial questions, please configure a GEMINI_API_KEY "
        "in your .env file. The system is currently running in rule-based mode only."
    )
