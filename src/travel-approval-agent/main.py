import json
import logging
import os
from pathlib import Path
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from pydantic import Field
from azure.ai.agentserver.optimization import load_config, load_skills_from_dir

logger = logging.getLogger(__name__)


@tool(approval_mode="never_require")
def lookup_travel_policy() -> str:
    """Look up the company travel policy rules and limits."""
    return json.dumps({
        "company": "Contoso Ltd.",
        "approval_thresholds": {
            "auto": 1500, "manager": 3000,
            "director": 7500, "vp": "above 7500"
        },
        "lodging_per_night": {"domestic": 250, "international": 400},
        "airfare": "economy only; business class if flight > 6 hours",
        "advance_booking_days": 14,
    })


@tool(approval_mode="never_require")
def check_department_budget() -> str:
    """Check the remaining travel budget for the employee's department."""
    return json.dumps({
        "department": "Engineering",
        "total_budget": 50000, "remaining": 14800,
    })


@tool(approval_mode="never_require")
def get_flight_alternatives(
    destination: Annotated[str, Field(description="The travel destination city")],
) -> str:
    """Find cheaper flight alternatives for the given destination."""
    return json.dumps({
        "alternatives": [
            {"option": "Flexible dates (±2 days)", "savings": "$200-800"},
            {"option": "Nearby alternate airport", "savings": "$100-400"},
        ],
    })


def main():
    # Load optimization config from .agent_configs/
    config = load_config()

    # Load skills from local directory if not provided by optimization
    if not config.skills and config.skills_dir:
        config.skills.extend(load_skills_from_dir(Path(config.skills_dir)))

    model = config.model or os.environ.get(
        "AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini"
    )
    instructions = config.compose_instructions()

    # Apply optimized tool descriptions
    tools = [lookup_travel_policy, check_department_budget, get_flight_alternatives]
    config.apply_tool_descriptions(tools)

    logger.info(
        "Config source=%s | model=%s | prompt_len=%d | skills=%d",
        config.source, model, len(instructions), len(config.skills),
    )

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=model,
        credential=DefaultAzureCredential(),
    )

    agent = Agent(
        client=client,
        instructions=instructions,
        tools=tools,
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()