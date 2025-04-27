class GithubAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.model = TachyonLangchainClient(model="gemini-2.0-flash")
        self.mcp_session_manager = MCPSessionManager(package_name="tachyon-ecp-github")

    async def initialize_tools(self):
        # your full initialize_tools() code
        ...

    async def invoke(self, query, session) -> str:
        # your full invoke() code
        ...

    async def stream(self, query, session):
        # your full stream() code
        ...

    async def get_agent_response(self, config):
        # your full get_agent_response() code
        ...