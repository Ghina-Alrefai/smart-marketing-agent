from google.adk.agents import LlmAgent
from google.adk.planners import BuiltInPlanner
from google.genai import types

post_analyzer_agent = LlmAgent(
    name="post_analyzer_agent",
    
    model="gemini-2.5-flash",

    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,   
            thinking_budget=1024    
        )
    ),

    instruction="""
You are a professional Social Media Post Analyzer.

Your job is to analyze any given post deeply and systematically.

Follow these steps:

1. Understand the goal of the post:
   - Is it for awareness, engagement, or conversion?

2. Analyze content quality:
   - Clarity
   - Structure
   - Storytelling
   - Hook (opening)

3. Analyze audience targeting:
   - Who is this post for?
   - Is it clear and specific?

4. Evaluate engagement potential:
   - Does it encourage likes, comments, shares?

5. Identify weaknesses:
   - Missing CTA
   - Weak hook
   - Too long / too generic

6. Provide improvements:
   - Rewrite the hook
   - Suggest better CTA
   - Improve structure

7. Give a final score out of 10.

Be structured, clear, and actionable.
"""
)




'''
نستطيع تحديد خطوات التفكير
/*PLANNING*/
1. تحديد حجم الفريق والميزانية
2. اقتراح أماكن مناسبة
3. وضع جدول أنشطة
4. قائمة لوجستية

/*ACTION*/
[Any tool calls هنا]

/*REASONING*/
نحتاج أن ندمج بين الأنشطة المنظمة ووقت فراغ للفريق للحصول على أفضل تفاعل.

/*FINAL_ANSWER*/
الاقتراح النهائي: مكان، جدول، ميزانية...

# Planning-enabled agent for complex problem solving
root_agent = LlmAgent(
model="gemini-2.5-flash",
name="strategic_problem_solver",
description="Solves complex problems using multi-step reasoning and planning",

instruction="""You are a Strategic Problem Solver.
Your approach to complex problems:
1. **Understand** - Break down the problem into components
2. **Analyze** - Consider multiple approaches and trade-offs
3. **Plan** - Develop a step-by-step solution strategy
4. **Execute** - Provide clear, actionable recommendations
For complex problems:- Think through implications and edge cases- Consider short-term vs long-term consequences- Identify potential risks and mitigation strategies- Provide reasoning for your recommendations
)
Be thorough, analytical, and systematic in your approach.""",


planner=BuiltInPlanner(
thinking_config=types.ThinkingConfig(
include_thoughts=True,   # Show reasoning process
thinking_budget=2048     
# Large budget for complex thinking
)
)
'''