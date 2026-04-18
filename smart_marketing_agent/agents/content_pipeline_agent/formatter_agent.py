from google.adk.agents import Agent, LlmAgent

formatter_agent = LlmAgent(
    name="FormatterAgent",
    model="gemini-2.5-flash",
    output_key="current_post",  

    instruction="""
Format the post:
{optimized_content}

- Improve spacing
- Add light emojis
- Keep it clean

Return final formatted post.
"""
)