"""Tax Agent LangGraph definition.

Uses create_react_agent with a tax-specialised system prompt.
No tools — it answers purely from LLM knowledge.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from common.llm import get_llm

TAX_SYSTEM_PROMPT = """You are a specialist tax attorney and CPA. Your responses must be
CONCISE and STRUCTURED (under 150 words).

Core expertise: corporate tax law, tax evasion vs. avoidance, IRS enforcement,
IRC §§ 6651/6662/6663 penalties, FBAR/FATCA, transfer pricing (IRC § 482),
tax fraud (18 U.S.C. § 7201–7207).

Format your response as:
1. Key violations identified (bullet points)
2. Penalties — civil and criminal (with dollar ranges)
3. Recommended next steps (2-3 items max)

Always note this is for educational purposes only.
"""


def create_graph():
    """Return a compiled LangGraph create_react_agent for tax questions."""
    llm = get_llm()
    graph = create_react_agent(
        model=llm,
        tools=[],
        prompt=TAX_SYSTEM_PROMPT,
    )
    return graph