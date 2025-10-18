# __import__('pysqlite3')
# import sys
# sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import time, datetime
import streamlit as st
from sqlalchemy.sql import text
from streamlit.runtime.scriptrunner import get_script_run_ctx
# from streamlit_feedback import streamlit_feedback
from llama_index.core.memory import ChatMemoryBuffer
import toml
import llamainchatagentool as at


cbconfig = toml.load("cbconfig.toml")
AVATARS = cbconfig['AVATARS']
ROLES = cbconfig['ROLES']


HIDEMENU = """
<style>
.stApp [data-testid="stHeader"] {
    display:none;
}

p img{
    margin-bottom: 0.6rem;
}

[data-testid="stSidebarCollapseButton"] {
    display:none;
}

[data-testid="baseButton-headerNoPadding"] {
    display:none;
}

.stChatInput button{
    display:none;
}

#chat-with-sjsu-library-s-kingbot  a {
    display:none;
}
</style>
"""


from langfuse import get_client, observe

import os
 
# Get keys for your project from the project settings page: https://cloud.langfuse.com
 
os.environ["LANGFUSE_PUBLIC_KEY"] = st.secrets.langfuse["LANGFUSE_PUBLIC_KEY"]
os.environ["LANGFUSE_SECRET_KEY"] = st.secrets.langfuse["LANGFUSE_SECRET_KEY"]
os.environ["LANGFUSE_HOST"] = st.secrets.langfuse["LANGFUSE_HOST"]
 
 
 
langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")
 
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
 
# Initialize LlamaIndex instrumentation
LlamaIndexInstrumentor().instrument()

import asyncio


async def runReActAgent(user_query, agent):
    """Run ReAct Agent with tracing"""
    with langfuse.start_as_current_span(name="ReAct-Agent"):
        try:
            start_time = time.time()
            response = agent.chat(user_query)
            latency = time.time() - start_time
            
            return {
                "response": response.response,
                "latency": latency,
                "status": "success"
            }
        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "latency": 0,
                "status": "error"
            }


async def runFunctionAgent(user_query, agent):
    """Run Function Agent with tracing"""
    with langfuse.start_as_current_span(name="Function-Agent"):
        try:
            start_time = time.time()
            response = await agent.run(user_query)
            latency = time.time() - start_time
            
            return {
                "response": str(response),
                "latency": latency,
                "status": "success"
            }
        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "latency": 0,
                "status": "error"
            }


import time

async def queryBothAgentsSequential(user_query, agents):
    """Query both agents sequentially"""
    current = datetime.datetime.now()
    st.session_state.moment = current.isoformat()
    
    st.chat_message("user", avatar=AVATARS["user"]).write(user_query)
    
    # Run Function Agent
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner(text="Function Agent processing..."):
            start_time = time.time()
            function_result = await runFunctionAgent(user_query, agents['function'])
            function_latency = time.time() - start_time
            
            st.write("**Function Agent:**")
            st.write(function_result['response'])
            st.caption(f"⏱️ Function Latency: {function_latency:.2f}s")
            
    # Run ReAct Agent
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner(text="ReAct Agent processing..."):
            start_time = time.time()
            react_result = await runReActAgent(user_query, agents['react'])
            react_latency = time.time() - start_time
            
            st.write("**ReAct Agent:**")
            st.write(react_result['response'])
            st.caption(f"⏱️ ReAct Latency: {react_latency:.2f}s")
    
    
    # Total comparison
    total_time = react_latency + function_latency
    faster_agent = "ReAct" if react_latency < function_latency else "Function"
    time_diff = abs(react_latency - function_latency)
    
    st.info(f"⚡ Total time: {total_time:.2f}s | {faster_agent} was {time_diff:.2f}s faster")
    
    langfuse.flush()

def queryBothAgents(user_query, agents, chip=''):
    """Wrapper function to run async query"""
    asyncio.run(queryBothAgentsSequential(user_query, agents))


if __name__ == "__main__":

    # set up streamlit page
    st.set_page_config(
        page_title="Kingbot - SJSU Library", 
        page_icon="🤖", 
        initial_sidebar_state="expanded"
    )
    st.markdown(HIDEMENU, unsafe_allow_html=True)

    # side
    st.sidebar.markdown(cbconfig['side']['title'])
    st.sidebar.markdown(cbconfig['side']['intro'])
    st.sidebar.markdown("\n\n")
    st.sidebar.link_button(cbconfig['side']['policylabel'],cbconfig['side']['policylink'])

    # main
    col1, col2, col3 = st.columns([0.25,0.1,0.65],vertical_alignment="bottom")
    with col2:
        st.markdown(cbconfig['main']['logo'])
    with col3:
        st.title(cbconfig['main']['title'])
    st.markdown("\n\n")
    st.markdown("\n\n")

    col21, col22, col23 = st.columns(3)
    with col21:
        button1 = st.button(cbconfig['button1']['label'])
    with col22:
        button2 = st.button(cbconfig['button2']['label'])
    with col23:
        button3 = st.button(cbconfig['button3']['label'])

    # lastest 5 messeges kept in memory for bot prompt
    if 'memory' not in st.session_state:
        memory = ChatMemoryBuffer.from_defaults(token_limit=5000)
        st.session_state.memory = memory
    memory = st.session_state.memory

    # get both agents
    if 'agents' not in st.session_state:
        st.session_state.agents = at.getBothAgents(memory)
    agents = st.session_state.agents

    # get streamlit session
    if 'session_id' not in st.session_state:
        session_id = get_script_run_ctx().session_id
        st.session_state.session_id = session_id

    if 'reference' not in st.session_state:
        st.session_state.reference = ''

    # messeges kept in streamlit session for display
    max_messages: int = 10  # Set the limit (K) of messages to keep
    allmsgs = memory.get()
    msgs = allmsgs[-max_messages:]

    # display chat history
    for msg in msgs:
        st.chat_message(ROLES[msg.role],avatar=AVATARS[msg.role]).write(msg.content)

    # chip
    if button1:
        queryBothAgents(cbconfig['button1']['content'], agents, cbconfig['button1']['chip'])
    if button2:
        queryBothAgents(cbconfig['button2']['content'], agents, cbconfig['button2']['chip'])
    if button3:
        queryBothAgents(cbconfig['button3']['content'], agents, cbconfig['button3']['chip'])

    # chat
    if user_query := st.chat_input(placeholder="Ask me about the SJSU Library!"):
        queryBothAgents(user_query, agents)