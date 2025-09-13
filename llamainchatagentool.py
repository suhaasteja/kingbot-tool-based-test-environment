__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI
import time, datetime
import streamlit as st
from llama_index.core.memory import ChatMemoryBuffer
import toml
from llama_index.core.tools import QueryEngineTool, FunctionTool
from llama_index.core.agent import ReActAgent
from prompts import react_system_header_str
from pyalex import Works


@st.cache_resource(ttl="1d", show_spinner=False)
def getIndex():
    client = chromadb.PersistentClient(path='./llamachromadb')
    embedding = OpenAIEmbedding(api_key=st.secrets.openai.key)
    collection = client.get_collection(name="sjsulib")
    cvstore = ChromaVectorStore(chroma_collection=collection)
    index = VectorStoreIndex.from_vector_store(
        cvstore,
        embed_model=embedding,
    )
    return index

@st.cache_resource(ttl="1d", show_spinner=False)
def getBot():
    index = getIndex()
    llm = OpenAI(model="gpt-4o-mini", temperature=0, api_key=st.secrets.openai.key)
    today = datetime.date.today().strftime('%B %d, %Y')

    system_prompt = (
        "You are Kingbot, the AI assistant for SJSU MLK Jr. Library. Respond supportively and professionally like a peer mentor. \n\n"
        "Guidelines: \n\n"
        "1. No creative content (stories, poems, tweets, code) "
        "2. Simple jokes are allowed, but avoid jokes that could hurt any group "
        "3. Use up to two emojis when applicable "
        "4. Provide relevant search terms if asked "
        "5. Avoid providing information about celebrities, influential politicians, or state heads "
        "6. Keep responses under 300 characters"
        "7. For unanswerable research questions, include the 'Ask A Librarian' URL: https://library.sjsu.edu/ask-librarian "
        "8. Do not make assumptions or fabricate answers or urls"
        "9. Use only the database information and do not add extra information if the database is insufficient "
        "10. If you don't know the answer, just say that you don't know, and refer users to the 'Ask A Librarian' URL: https://library.sjsu.edu/ask-librarian "
        "11. Do not provide book recommendations and refer the user to try their search on a library database"
        "12. Please end your response with a reference url from the source of the response content."
        f"13. Today is {today}. Always use this information to answer time-sensitive questions about library hours or events. For library building hours and department hours, always refer to live data from library.sjsu.edu. If you cannot retrieve live data, inform the user to check Library Hours.\n"
        #"14. When users ask about research or subject-specific topics first recommend OneSearch as a general tool for broad searches across multiple databases. Provide a hyperlink to OneSearch (https://csu-sjsu.primo.exlibrisgroup.com/discovery/search?vid=01CALS_SJO:01CALS_SJO&lang=en). Example: Try using our [OneSearch SJSU's Library Database](https://csu-sjsu.primo.exlibrisgroup.com/discovery/search?vid=01CALS_SJO:01CALS_SJO&lang=en) to explore a range of library resources. After suggesting OneSearch, recommend specific databases for specialized searches. For example, health topics like 'dementia' may include PubMed, CINAHL, or PsycINFO.\n"
        "14. For questions about library building and department hours, display and differentiate between King Library Building Hours, hours for SJSU affiliates, and San Jose Public Library hours listed on the Library Hours page: https://library.sjsu.edu/library-hours/library-hours  \n"
        "15. When users ask about research or subject-specific topics first recommend OneSearch as a general tool for broad searches across multiple databases. Provide a hyperlink to OneSearch (https://csu-sjsu.primo.exlibrisgroup.com/discovery/search?vid=01CALS_SJO:01CALS_SJO&lang=en). Example: Try using our [OneSearch SJSU's Library Database](https://csu-sjsu.primo.exlibrisgroup.com/discovery/search?vid=01CALS_SJO:01CALS_SJO&lang=en) to explore a range of library resources. After suggesting OneSearch, recommend specific databases for specialized searches. For example, health topics like 'dementia' may include PubMed, CINAHL, or PsycINFO.\n"
        "{context}"
    )
    chat_engine = index.as_chat_engine(
        chat_mode="condense_plus_context",
        llm=llm,
        system_prompt=system_prompt,
        verbose=False,
        )

    return chat_engine


def getOneSearch(term:str)-> str:
    """Use this tool for questions about articles or books."""
    # Create a pager with a page size of 5
    pager = Works().paginate(per_page=5)
    response = []
    if term:
        response = Works().search(term).get()
    else:
        response = "Could not extract search term"
    return response


def getKingbot(query:str)-> str:
    """Kingbot for SJSU library information, not for books or article search."""
    engine = getBot()
    response = engine.chat(query)
    return response


def getAngent(memory):
    oneSearch_tool = FunctionTool.from_defaults(fn=getOneSearch,return_direct=False)
    bot_tool = FunctionTool.from_defaults(fn=getKingbot,return_direct=True)

    tools = [oneSearch_tool,bot_tool]
    agent_prompt = '''You are the agent for SJSU library chatbot. Please format the response from OneSearch, \
            by displaying of number lists of titles and authors, and please link the titles with the link field provided.  \
        '''
    llm = OpenAI(model="gpt-4o-mini", temperature=0, api_key=st.secrets.openai.key)
    agent = ReActAgent.from_tools(
        tools,
        llm=llm,
        memory=memory,
        verbose=True,
        system_prompt=react_system_header_str,
    )
    return agent

