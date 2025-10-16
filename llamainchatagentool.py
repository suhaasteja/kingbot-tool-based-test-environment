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

# ---- Langfuse Setup (v3 API) ----
import os
from langfuse import Langfuse

os.environ["LANGFUSE_PUBLIC_KEY"] = st.secrets.langfuse["LANGFUSE_PUBLIC_KEY"]
os.environ["LANGFUSE_SECRET_KEY"] = st.secrets.langfuse["LANGFUSE_SECRET_KEY"]
os.environ["LANGFUSE_HOST"] = st.secrets.langfuse["LANGFUSE_HOST"]

langfuse_client = Langfuse()

# Verify connection
try:
    if langfuse_client.auth_check():
        print("✓ Langfuse authenticated successfully")
except Exception as e:
    print(f"⚠ Langfuse auth warning: {e}")
# ---- end Langfuse setup ----


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


def getOneSearch(term: str) -> str:
    """Use this tool for questions about articles or books."""
    
    start_time = time.time()
    retrieved_data = []
    error = None
    
    try:
        if not term:
            error = "No search term provided"
            return "Could not extract search term"
        
        # Perform search
        response = Works().search(term).select(["display_name", "doi"]).get()
        
        # Extract data for logging
        for item in response:
            retrieved_data.append({
                "title": item.get("display_name", ""),
                "doi": item.get("doi", "")
            })
        
        return response
        
    except Exception as e:
        error = str(e)
        raise
    finally:
        elapsed = time.time() - start_time
        # Store tool execution info in session state for parent trace to pick up
        if 'tool_executions' not in st.session_state:
            st.session_state.tool_executions = []
        st.session_state.tool_executions.append({
            "tool": "getOneSearch",
            "time_seconds": round(elapsed, 2),
            "retrieved_data": retrieved_data,
            "error": error
        })


def getKingbot(query: str) -> str:
    """Kingbot for SJSU library information, not for books or article search."""
    
    start_time = time.time()
    retrieved_data = []
    error = None
    
    try:
        index = getIndex()
        retriever = index.as_retriever()
        response = retriever.retrieve(query)
        
        # Extract retrieved document data for logging
        for i, node in enumerate(response): 
            retrieved_data.append({
                "rank": i + 1,
                "text_preview": node.node.text,
                "score": round(node.score, 4) if hasattr(node, 'score') else None
            })
        
        return response
        
    except Exception as e:
        error = str(e)
        raise
    finally:
        elapsed = time.time() - start_time
        # Store tool execution info in session state for parent trace to pick up
        if 'tool_executions' not in st.session_state:
            st.session_state.tool_executions = []
        st.session_state.tool_executions.append({
            "tool": "getKingbot",
            "time_seconds": round(elapsed, 2),
            "retrieved_data": retrieved_data,
            "error": error
        })


def date(query: str) -> str:
    '''Use this tool to retrieve today's date when answering questions about today's date, or current events and hours in the library'''
    
    start_time = time.time()
    error = None
    today_str = None
    
    try:
        today_str = datetime.date.today().strftime('%B %d, %Y')
        response = "Today is " + today_str
        return response
        
    except Exception as e:
        error = str(e)
        raise
    finally:
        elapsed = time.time() - start_time
        # Store tool execution info in session state for parent trace to pick up
        if 'tool_executions' not in st.session_state:
            st.session_state.tool_executions = []
        st.session_state.tool_executions.append({
            "tool": "date",
            "time_seconds": round(elapsed, 2),
            "retrieved_data": {"date": today_str if not error else None},
            "error": error
        })


def getAgent():
    """Creates the ReAct agent with all tools"""
    oneSearch_tool = FunctionTool.from_defaults(fn=getOneSearch, return_direct=False)
    bot_tool = FunctionTool.from_defaults(fn=getKingbot, return_direct=False)
    date_tool = FunctionTool.from_defaults(fn=date, return_direct=False)

    tools = [oneSearch_tool, bot_tool, date_tool]
    llm = OpenAI(model="gpt-4o-mini", temperature=0, api_key=st.secrets.openai.key)
    
    agent = ReActAgent.from_tools(
        tools=tools,
        llm=llm,
        verbose=True,
        system_prompt=react_system_header_str,
    )
    
    return agent