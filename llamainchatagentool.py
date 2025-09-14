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
from promptstest import react_system_header_str
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

def getOneSearch(term:str)-> str:
    """Use this tool for questions about articles or books."""
    # Create a pager with a page size of 5
    pager = Works().paginate(per_page=5)
    response = []
    if term:
        response = Works().search(term).select(["display_name", "doi"]).get()
    else:
        response = "Could not extract search term"
    return response

def getKingbot(query:str)-> str:
    """Kingbot for SJSU library information, not for books or article search."""
    #engine = getBot()
    #response = engine.chat(query)
    index = getIndex()
    retriever = index.as_retriever()
    response = retriever.retrieve(query)
    return response

def date(query:str)-> str:
    '''Use this tool to retrieve today's date when answering questions about today's date, or current events and hours in the library '''
    response = "Today is " + datetime.date.today().strftime('%B %d, %Y')
    return response


def getAngent(memory):
    oneSearch_tool = FunctionTool.from_defaults(fn=getOneSearch,return_direct=False)
    bot_tool = FunctionTool.from_defaults(fn=getKingbot,return_direct=False)
    date_tool = FunctionTool.from_defaults(fn=date,return_direct=False)

    tools = [oneSearch_tool,bot_tool, date_tool]
    llm = OpenAI(model="gpt-4o-mini", temperature=0, api_key=st.secrets.openai.key)
    agent = ReActAgent.from_tools(
        tools,
        llm=llm,
        memory=memory,
        verbose=True,
        system_prompt=react_system_header_str,
    )
    return agent

