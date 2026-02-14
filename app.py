import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage
from tools import ListTablesTool, TableSchemaTool, SearchTablesTool, RelationshipTool

# Load environment variables
load_dotenv()

def create_pdm_agent():
    # Initialize LLM
    llm = ChatDeepSeek(
        model="deepseek-chat",
        temperature=0.1,
        max_tokens=2000,
        timeout=None,
        max_retries=2
    )

    # Initialize Tools
    tools = [
        ListTablesTool(),
        TableSchemaTool(),
        SearchTablesTool(),
        RelationshipTool()
    ]

    # Define the System Prompt
    system_message = SystemMessage(content="""You are a PDM expert assistant. 
    Help users understand table structure and relationships.
    
    1. For conceptual searches, use 'search_tables'.
    2. For table details, use 'get_table_schema' with the table's CODE.
    3. For connections, use 'find_relationships'.
    4. Respond in the user's language (Chinese/English).""")

    # Construct the Agent using LangGraph (Modern way)
    agent_executor = create_react_agent(llm, tools, prompt=system_message)
    
    return agent_executor

if __name__ == "__main__":
    # Simple CLI loop
    agent_executor = create_pdm_agent()
    print("PDM Assistant is ready! (Type 'exit' to quit)")
    
    messages = []
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
            
        # Run the agent
        response = agent_executor.invoke({
            "messages": [HumanMessage(content=user_input)]
        })
        
        # In LangGraph, the result is in the last message
        assistant_msg = response["messages"][-1].content
        print(f"Assistant: {assistant_msg}")
        
        # Optional: update message history for context (simplified here)
        messages.append(HumanMessage(content=user_input))
        messages.append(response["messages"][-1])
