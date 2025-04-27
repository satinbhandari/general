from abc import ABC, abstractmethod

class BaseAgent(ABC):
    def __init__(self):
        self.model = None
        self.mcp_session_manager = None
        self.graph = None

    @abstractmethod
    async def initialize_tools(self):
        pass

    @abstractmethod
    async def invoke(self, query, session) -> str:
        pass

    @abstractmethod
    async def stream(self, query, session):
        pass

    @abstractmethod
    async def get_agent_response(self, config):
        pass