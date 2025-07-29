from langgraph.graph import StateGraph
from mcp import StdioServerParams, ClientSession
# from myclient import CustomClient
# from myagents import create_react_agent

class Newsretrievalandsummarizationgraph:
    class State:
        news_list: list[str ]
        news_summary: str
        user_query: str

    def __init__(self):
        self.llm_gemini_flash_model = CustomClient("Gemini Flash", temparature=0.4, top_k=50, top_p=0.9)

    def internal_news_api(self):
        def get_internal_news(category: str) -> List[str]:
            # Simulate API call
            return [f'Internal news headline for {category} 1', f'Internal news headline for {category} 2']

    def create_web_news_search_server(self):
        params = StdioServerParams(**{
        "SEARCH_API_KEY": "your_api_key",
        "SEARCH_ENGINE": "google"
})
        return ClientSession(command="python run_web_search_agent.py", params=params)

    def news_retriever(self, state):
        # Node ID: node_retrieve_news
        tools = [internal_news_api, web_news_search]
        agent = create_react_agent(self.llm_gemini_flash_model, "If user asks for news, use the appropriate tool to fetch news articles for the requested category. Use MCP for internet search, and Python tool for internal news API.", tools)
        return agent.invoke(state)

    def news_summarizer(self, state):
        # Node ID: node_summarize_news
        tools = []
        agent = create_react_agent(self.llm_gemini_flash_model, "Summarize the given list of news articles into a short paragraph.", tools)
        return agent.invoke(state)


    def build(self):
        builder = StateGraph(self.State)
        builder.add_node("news_retriever", self.news_retriever)
        builder.add_node("news_summarizer", self.news_summarizer)
        builder.add_edge("news_retriever", "news_summarizer")
        return builder.compile()