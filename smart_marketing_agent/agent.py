from google.adk.agents import Agent

from .agents.anlysis_parallel_agent.analysis_parallel_agent import analysis_parallel_agent

from .agents.content_pipeline_agent.strategy_agent import strategy_agent
from .agents.content_pipeline_agent.content_pipeline_agent import content_pipeline_agent
from .agents.design_agent import design_agent
from .agents.post_analyzer_agent import post_analyzer_agent
orchestrator_prompt = """

You are a Smart Marketing Orchestrator Agent.

Your role is to understand the user's request and decide which agent(s) should handle it:

- If the user asks about marketing strategy → use strategy_agent
- If the user asks for content creation → content_pipeline_agent
- If the user asks for design → use design_agent
- If the user asks to extract product info → use extract_product_info_agent
- If the user asks to analysis a post or product → use analysis_parallel_agent

Rules:
- DO NOT generate structured JSON yourself
- DO NOT rewrite the response
- Simply call the appropriate agent and return its response as-is

Always respond in the same language as the user.
"""



root_agent = Agent(
    name="smart_marketing_orchestrator",
    model="gemini-2.5-flash",
    description="Smart Marketing Multi-Agent System",
    instruction=orchestrator_prompt,
    sub_agents=[
        strategy_agent,
        content_pipeline_agent,
        design_agent,
        analysis_parallel_agent
    ],
)