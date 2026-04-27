from google.adk.agents import ParallelAgent

from .audience_agent import audience_agent
from .competitor_agent import competitor_agent
from .trends_agent import trends_agent

analysis_parallel_agent = ParallelAgent(
    name="ProductAnalysisParallel",
    sub_agents=[
        audience_agent,
        competitor_agent,
        trends_agent,
    ]
)