"""Minimal example: authenticate and list organizations.

Configure via environment variables:
    ACTION1_CLIENT_ID     e.g. api-key-xxxx@action1.com
    ACTION1_CLIENT_SECRET
    ACTION1_REGION        north_america | europe | australia (default: north_america)
"""

import os

from action1_client import Action1Client

client = Action1Client(
    client_id=os.environ["ACTION1_CLIENT_ID"],
    client_secret=os.environ["ACTION1_CLIENT_SECRET"],
    region=os.environ.get("ACTION1_REGION", "north_america"),
)

with client:
    for org in client.list_organizations():
        print(org["id"], org["name"])
