from anthropic.types import ToolParam
from sqlalchemy import or_
from sqlmodel import col, select

from src.models.campaign import Checkpoint

# TODO: campaign creation tool should try and use predefined npcs, checkpoints, and maybe themes for it's story.
#
# campaign_creation_tool = { "name": "juice_up_campaign",
#     "description": "Pull story elements and non player characters from the database to spice up the campaing narrative. Use when creating a brand new player campaign to define characters, milestones and story elements.",
#     "input_schema": {
#         "type": "object",
#         "properties": {
#             "theme": {
#                 "type": "string",
#                 "description": "A short, impactful description of the narrative, e.g. ''",
#             }
#         },
#     },
# }

# okay I think the idea is some text-classification based on a description from the user, and the model will return tags we can search our db for.
search_checkpoints_tool: ToolParam = {
    "name": "search_checkpoints",
    "description": "Search the checkpoint library for pre-authored story milestones to include in a campaign. Call this when building a new campaign to find checkpoints that fit the theme and narrative.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tags": {
                "type": "string",
                "description": "Comma-separated tags to filter by, e.g. 'combat,boss,undead'",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of checkpoints to return. Defaults to 10.",
            },
        },
        "required": ["tags", "limit"],
    },
}


def handle_search_checkpoints(session, tags: str, limit: int = 10):
    print("In handle_search_checkpoints")
    with session:
        query = select(Checkpoint)

        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            query = query.where(
                or_(*[col(Checkpoint.tags).contains(tag) for tag in tag_list])
            )

        query = query.limit(limit)
        results = session.exec(query)

        print(results)
        return [
            {
                "id": cp.id,
                "title": cp.title,
                "description": cp.description,
                "objective": cp.objective,
                "tags": cp.tags,
            }
            for cp in results
        ]


def handle_campaign_creation():
    # something
    print("get some npcs")
