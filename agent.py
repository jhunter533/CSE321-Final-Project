import json
import os
import requests
import tools
import database

# Variables for config of AI
OPENROUTER_URL="https://openrouter.ai/api/v1/chat/completions"
MAX_TOOL_CALLS = 5
TIMEOUT_SECONDS = 30

# promt that is used to tell how the AI should behave and it's role
SYSTEM_PROMPT = (
    "Imagine that you are a course scheduler assistant for students who attend New Mexico Tech. "
    "When running, always start by calling tools and make sure not to invent courses that are not real. "
    "In your first response, call get_schedule and search_courses together at the same time since a new student won't have a schedule. "
    "Use get_schedule to see the student's current schedule. "
    "Use search_courses to look for a specific Requirement or Subject. "
    "Only call check_conflicts with a section_id that you already know "
    "You can't and will not modify the student's schedule on your own accord. "
)

# List that contains the tools that OpenRouter can tell the AI that they are available
# Consists of "search_courses", "check_conflicts", and "get_schedule"
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_courses",
            "description": "Search for NMT courses using a given subject or general education requirement. Examples include PHYS, MATH, and AREA7",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A requirement code such as AREA7 or a subject such as PHYS",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_conflicts",
            "description": "Check whether a course section conflicts with the user's current existing schedule or a given day restriction",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "integer",
                        "description": "The section ID that is used to check for conflicts",
                    },
                    "avoid_day": {
                        "type": "string",
                        "description": "Optional day name such as Monday",
                    }, 
                },
                "required": ["section_id"],
            },
        },
    },
    {
        "type": "function", 
        "function": {
            "name": "get_schedule",
            "description": "Obtain all of the courses that are currently in the user's existing schedule",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
                "required": [],
            },
        },
    },
]

# Custom exception for errors that are related to the AI agent
class AgentError(Exception):
    "Error. Something went wrong"
    pass

# Function handles communication with OpenRouter
def callOpenRouter(messages):

    # Get API key and model from .env file
    APIkey = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")

    if not APIkey or not model:
        raise AgentError("OPENROUTER_API_KEY or OPENROUTER_MODEL is not set correctly.")

    # Sends an HTTP POST request to the API endpoint OPENROUTER_URL with a json that contains the info we are sending
    try:
        response = requests.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {APIkey}"}, json={"model": model, "messages": messages, "tools": TOOL_DEFINITIONS}, timeout=TIMEOUT_SECONDS)
    except requests.RequestException:
        raise AgentError("Could not reach the LLM provider.")
    
    if response.status_code != 200:
        raise AgentError(f"LLM provider returned HTTP {response.status_code}")

    # Convert the response into JSON format
    try:
        return response.json()
    except ValueError:
        raise AgentError("LLM provider returned an invalid JSON file.")

# Handles the entire process for running the agent
def runAgent(connection, userID, scheduleID, goal):

    # Create the conversations that will be sent to OpenRouter (first = AI Instructions, second = student request)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]    

    # Ask the model what tools it wants
    data = callOpenRouter(messages)

    # Extract the model's message
    try:
        message = data["choices"][0]["message"]
    except(KeyError, IndexError, TypeError):
        raise AgentError("An unexpected response was given from the LLM provider")

    # Get the requested tool call that the AI wants to execute
    toolCalls = message.get("tool_calls") or []
    results = []

    # Loop through the tool calls
    for call in toolCalls[:MAX_TOOL_CALLS]:

        # first get the function and name
        function = call.get("function") or {}
        name = str(function.get("name", ""))

        # The model sends the arguments as a JSON string, so first convert to python dictionary
        try:
            args = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}

        # Check agent perms, then execute the approved tool
        if name not in tools.AGENT_TOOLS:
            output = {"success": False, "error": "Tool is not allowed to be used by agent"}
        else:
            try:
                output = tools.runTool(connection, scheduleID, name, args)
            except tools.ValidationError as e:
                output = {"success": False, "error": str(e)}

        # Record every tool call
        database.log_agent_tool(connection, userID, name, args, output, scheduleID, iteration_number=1)
        connection.commit()

        # Keep what happened so that it can be shown to the user
        results.append({"tool": name, "input": args, "output": output})

    # return the final result
    return {"success": True, "message": message.get("content") or "", "tool_results": results,}
