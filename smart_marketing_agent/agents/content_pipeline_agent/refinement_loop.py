from google.adk.agents import LoopAgent, LlmAgent, BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext


post_refiner = LlmAgent(
    name="PostRefiner",
    model="gemini-2.5-flash",
    output_key="current_post",
    instruction="Improve this post: {current_post}"
)


quality_checker = LlmAgent(
    name="PostQualityChecker",
    model="gemini-2.5-flash",
    output_key="quality_status",
    instruction="Return pass or fail for: {current_post}"
)


class CheckQualityAndStop(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext):
        status = ctx.session.state.get("quality_status", "fail")
        should_stop = (status.strip().lower() == "pass")

        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_stop)
        )


refinement_loop = LoopAgent(
    name="PostRefinementLoop",
    max_iterations=4,
    sub_agents=[
        post_refiner,
        quality_checker,
        CheckQualityAndStop(name="StopChecker")
    ]
)