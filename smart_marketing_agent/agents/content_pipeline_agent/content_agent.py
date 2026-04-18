from google.adk.agents import Agent
from google.genai import types
from google.adk.agents import Agent, LlmAgent

content_agent = LlmAgent(
    name="ContentAgent",
    model="gemini-2.5-flash",
    output_key="content",

    instruction="""
You are a skilled social media copywriter.

Using this IDEA:
{idea}

Write a complete social media post that includes:
- Hook
- Product description
- Benefits
- Call to action

Rules:
- Do NOT include hashtags
- Do NOT use labels
- Keep it engaging and realistic

Match the language of the input.
"""
)