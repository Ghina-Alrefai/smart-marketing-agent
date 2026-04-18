
from google.adk.agents import Agent
from google.genai import types

from google.adk.agents import LlmAgent

idea_agent = LlmAgent(
    name="IdeaAgent",
    model="gemini-2.5-flash",
    output_key="idea",

    instruction="""
You are a professional marketing strategist.

Generate ONE clear marketing idea for a social media post.

Include:
- Target audience
- Product angle
- Core message

Keep it concise (3–5 lines).
Do NOT write a full post.
Do NOT include hashtags.

Match the user's language.
"""
)