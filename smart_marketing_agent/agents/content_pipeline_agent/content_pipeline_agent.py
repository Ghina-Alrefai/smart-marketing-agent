
from google.genai import types
from .content_agent import content_agent
from .seo_agent import seo_agent
from .idea_agent import idea_agent
from .formatter_agent import formatter_agent
from google.adk.agents import SequentialAgent

content_pipeline_agent = SequentialAgent(
    name="ContentPipelineWithRefinement",
    sub_agents=[
        idea_agent,
        content_agent,
        seo_agent,
        formatter_agent,   
       # refinement_loop    #  يحسّن بشكل تكراري
    ]
)