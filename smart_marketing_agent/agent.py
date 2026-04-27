from google.adk.agents import Agent

from .agents.data_agent import data_agent

from .agents.anlysis_parallel_agent.analysis_parallel_agent import analysis_parallel_agent

from .agents.strategy_agent import strategy_agent
from .agents.content_pipeline_agent.content_pipeline_agent import content_pipeline_agent
from .agents.design_agent import design_agent

orchestrator_prompt = """

You are a Smart Marketing Orchestrator Agent.


Your role is to coordinate between agents:

- Strategy → strategy_agent
- Data → data_agent
- Content → content_pipeline_agent
- Design → design_agent
- Analysis → analysis_parallel_agent
If the user asks to create posts for past/upcoming days
  → transfer to strategy_agent immediately
- For any other marketing question → answer directly
- Always respond in the user's language

Special Flow:
If user asks for posts (e.g. "5 days posts"):
1. Call strategy_agent → generate plan
2. Call data_agent → fetch relevant product/service data
3. Call content_pipeline_agent → generate posts using plan + data

Rules:
- DO NOT generate content yourself
- DO NOT modify responses
- Just orchestrate


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
    ],
)