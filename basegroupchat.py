This is a great case for using a sequential multi-agent workflow, where:

1. Agent A clones the GitHub repo.


2. Agent B packages the code using the repo-mix library.


3. Agent C translates COBOL files to Python or Java.



Now, choosing the right group chat type is crucial:


---

Best Group Type: BaseGroupChat (Custom Sequential Logic)

Why not RoundRobinGroupChat?

It treats all agents equally in a loop without task-specific roles.

It doesn't allow for conditional logic like "only run Agent B after Agent A succeeds".

It’s designed more for brainstorming or evenly distributed contributions.


Why BaseGroupChat with custom logic?

You can strictly control agent order and pass state between them.

You can exit early if a step fails (e.g., repo cloning fails).

It matches real-world pipelines where each step is dependent on the previous one.



---

Implementation Overview

User input

input_data = {
    "repo_owner": "some-owner",
    "repo_name": "some-repo",
    "local_path": "/path/to/clone/repo"
}

Agent Roles

CloneAgent: Clones the GitHub repo.

PackageAgent: Runs the packaging logic using repo-mix.

ConvertAgent: Converts COBOL to Python/Java.



---

Custom SequentialGroupChat Implementation

from autogen.agentchat.teams.base_groupchat import BaseGroupChat
from autogen.agentchat import AssistantAgent
from autogen.agentchat.teams import GroupChatManager

class SequentialPipelineGroupChat(BaseGroupChat):
    def __init__(self, agents, messages=None, input_data=None):
        super().__init__(agents=agents, messages=messages or [])
        self.input_data = input_data
        self.current_index = 0

    def select_next_speaker(self):
        if self.current_index >= len(self.agents):
            return None
        speaker = self.agents[self.current_index]
        self.current_index += 1
        return speaker

    def select_speaker_messages(self, speaker):
        # All agents get previous messages and input data
        return self.messages + [{"role": "system", "content": f"Input data: {self.input_data}"}]


---

Setting Up the Agents

shared_config = {
    "config_list": [
        {
            "model": "gpt-4",
            "api_key": "your_api_key"
        }
    ]
}

clone_agent = AssistantAgent(name="CloneAgent", config=shared_config)
package_agent = AssistantAgent(name="PackageAgent", config=shared_config)
convert_agent = AssistantAgent(name="ConvertAgent", config=shared_config)

pipeline_chat = SequentialPipelineGroupChat(
    agents=[clone_agent, package_agent, convert_agent],
    messages=[{"role": "user", "content": "Start the pipeline."}],
    input_data={
        "repo_owner": "my-org",
        "repo_name": "legacy-app",
        "local_path": "/tmp/legacy-app"
    }
)

manager = GroupChatManager(groupchat=pipeline_chat)
manager.run()


---

How Each Agent Should Behave

Each agent can be prompted using a custom system message (you can customize this via select_speaker_messages or use SystemMessageGenerator), for example:

CloneAgent prompt:

> "Clone the GitHub repo from https://github.com/{repo_owner}/{repo_name} into {local_path}. Use GitPython or system git."



PackageAgent prompt:

> "Run packaging using the repo-mix library on the local path {local_path}."



ConvertAgent prompt:

> "Search for .cob files in {local_path}, and convert them to Python or Java using available translation tools."





---

Summary


---

Let me know if you'd like help fleshing out the prompts or wiring real code execution (e.g., subprocess, git, or COBOL converter integration).

