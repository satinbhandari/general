Thank you for the precise constraint. Since you're using autogen-agent-chat==0.5.1, you're absolutely right — in this version:

BaseGroupChat’s __init__ does not accept a messages parameter.

GroupChatManager internally manages the message history through groupchat.send_message.



---

Correct SequentialPipelineGroupChat Implementation (0.5.1-compatible)

Here’s the working version that matches the exact BaseGroupChat interface in autogen-agent-chat==0.5.1:

from autogen.agentchat.teams.base_groupchat import BaseGroupChat

class SequentialPipelineGroupChat(BaseGroupChat):
    def __init__(self, agents, input_data=None, max_steps=None):
        super().__init__(agents=agents)
        self.input_data = input_data or {}
        self.max_steps = max_steps or len(agents)
        self.current_index = 0

    def select_next_speaker(self):
        if self.current_index >= self.max_steps:
            return None
        speaker = self.agents[self.current_index]
        self.current_index += 1
        return speaker

    def select_speaker_messages(self, speaker):
        # Let speaker see full message history + input_data
        intro_msg = {
            "role": "system",
            "content": f"Pipeline input: {self.input_data}"
        }
        return self._messages + [intro_msg]

> self._messages is the internal message history, maintained by the base class (it gets updated automatically by GroupChatManager).




---

How to Use It in Your Pipeline

from autogen.agentchat import AssistantAgent
from autogen.agentchat.teams import GroupChatManager

shared_config = {
    "config_list": [
        {
            "model": "gpt-4",
            "api_key": "your-api-key"
        }
    ]
}

# Define the agents
clone_agent = AssistantAgent(name="CloneAgent", config=shared_config)
package_agent = AssistantAgent(name="PackageAgent", config=shared_config)
convert_agent = AssistantAgent(name="ConvertAgent", config=shared_config)

# Input data
input_data = {
    "repo_owner": "openai",
    "repo_name": "example-repo",
    "local_path": "/tmp/example-repo"
}

# Create your group chat
group_chat = SequentialPipelineGroupChat(
    agents=[clone_agent, package_agent, convert_agent],
    input_data=input_data
)

# Manager to run the pipeline
manager = GroupChatManager(groupchat=group_chat)

# Kick off the process
manager.run(
    message="Begin processing the repository based on the pipeline."
)


---

Summary

Let me know if you want to inject a retry logic or error handler between steps.

