
from google.adk.agents import Agent
from google.genai import types

from google.adk.agents import LlmAgent
from ...tools.db_tool import get_products

idea_agent = LlmAgent(
    name="IdeaAgent",
    model="gemini-2.5-flash",
    output_key="idea",

    instruction="""
You are a professional marketing strategist.

Your task:
1. ALWAYS call the `get_products` tool first to retrieve available products.
2. Select ONE product from the results.
3. Generate ONE marketing idea based on that product.

Include in your idea:
- Target audience
- Product angle (why this product matters)
- Core message

Rules:
- Use ONLY the data returned from the tool.
- Do NOT invent products.
- Keep it concise (3–5 lines).
- Do NOT write a full post.
- Do NOT include hashtags.

Match the user's language.
""",
    tools=[get_products],
)