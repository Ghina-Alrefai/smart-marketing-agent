
from google.adk.agents import Agent,LlmAgent
from google.genai import types

seo_agent = LlmAgent(
    name="SEOAgent",
    model="gemini-2.5-flash",
    output_key="optimized_content",

    instruction="""
You are an SEO expert.

Improve the following post:
{content}

Tasks:
- Add 5–10 relevant hashtags at the end
- Improve keyword usage slightly

Rules:
- Do NOT rewrite the entire post
- Keep meaning and tone the same

Match the language.
"""
)