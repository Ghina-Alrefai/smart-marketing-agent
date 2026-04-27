# agents/data_agent.py

from google.adk.agents import Agent
from ..tools.db_tool import get_products

data_agent_prompt = """

You are a Data Retrieval Agent.

Your job:


- Use available tools only
- DO NOT generate SQL queries
- Return structured data
- Use the query_database tool
- Return clean structured data

Rules:
- ONLY return useful data
- DO NOT explain
- DO NOT generate marketing content
- If no data found → say clearly

Database Schema Example:
products(id, name, description, benefits)

"""

data_agent = Agent(
    name="data_agent",
    model="gemini-2.5-flash",
    description="Fetch data from SQL database",
    instruction=data_agent_prompt,
    tools=[get_products],
)