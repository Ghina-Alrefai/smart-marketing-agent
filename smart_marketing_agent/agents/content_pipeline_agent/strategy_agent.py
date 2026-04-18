from google.adk.agents import Agent

strategy_agent = Agent(
    name="marketing_strategy_agent",
    model="gemini-2.5-flash",
    description="Creates marketing strategies",
    instruction="""
You are a digital marketing strategist.

Create a marketing strategy for the business.

Return:

Target Audience
Content Pillars
Posting Frequency
Campaign Ideas

Support Arabic and English.
Respond in the same language as the user.
"""
)