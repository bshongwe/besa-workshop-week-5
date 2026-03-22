from mcp.server import FastMCP
from strands import Agent
from strands_tools import http_request

# Create the MCP server
mcp = FastMCP("Strands Agent MCP Server")

AGENT_SYSTEM_PROMPT = """
You are an expert agent that can answer questions.
You can use tools to answer questions.
"""

@mcp.tool(
    name="my_custom_expert", # Custom tool name for the Agent
    description="Use this tool to answer hard questions that require access to the internet", # Custom description
)
def my_agent(query: str) -> str:
    """
    Process and respond to questions
    """
    # Format the query for the agent with clear instructions
    formatted_query = f"Answer the following question: {query}"
    
    try:
        ai_agent = Agent(
            model="us.amazon.nova-pro-v1:0",
            system_prompt=AGENT_SYSTEM_PROMPT,
            tools=[http_request], # Allow it to access the internet
        )
        response = ai_agent(formatted_query)
        return str(response)
        
    except Exception as e:
        return f"Error processing your query: {str(e)}"

if __name__ == "__main__":
    print("Starting Strands Agent MCP Server...")
    mcp.run(transport="stdio") 