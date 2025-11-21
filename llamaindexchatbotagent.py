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
import asyncio
import nest_asyncio

nest_asyncio.apply()

from llama_index.core.agent.workflow import ToolCallResult, AgentStream


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



async def queryBot(user_query,bot,chip='', ctx=None):
    current = datetime.datetime.now()
    st.session_state.moment = current.isoformat()
    session_id = st.session_state.session_id
    today = current.date()
    now = current.time()
    answer = ''

    st.chat_message("user", avatar=AVATARS["user"]).write(user_query)
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner("Generating response..."):
            placeholder = st.empty()
            full_response = ""
            error = ""
            try:
                handler = bot.run(user_query, ctx=ctx)
                streaming_answer = False
                async for ev in handler.stream_events():
                    if isinstance(ev, ToolCallResult):
                        # Log tool calls if needed
                        pass
                    if isinstance(ev, AgentStream):
                        full_response += ev.delta
                        placeholder.write(full_response)
                        # if "Answer:" in full_response and not streaming_answer:
                        #     streaming_answer = True
                        # if streaming_answer:
                        #     # Display only the part after "Answer:"
                        #     answer_part = full_response.split("Answer:", 1)[-1].strip()
                        #     placeholder.write(answer_part)
                # Final response
                response = await handler
                answer = str(response)
                # Extract final answer if needed
                # if "Answer:" in answer:
                #     answer = answer.split("Answer:", 1)[-1].strip()
                placeholder.write(answer)
            except Exception as e:
                print(e)
                answer = f"Sorry there was an error answering '{user_query}'"
                placeholder.write(answer)
                error = str(e)
        with st.expander("log"):
            if error:
                st.write("Error:", error)
            st.write("Full reasoning:", full_response)

    # Append to chat history
    st.session_state.chat_history.append({'role': 'user', 'content': user_query})
    st.session_state.chat_history.append({'role': 'assistant', 'content': answer})
    # Limit history to last 20 entries
    st.session_state.chat_history = st.session_state.chat_history[-20:]

if __name__ == "__main__":

    # set up streamlit page
    st.set_page_config(page_title="Kingbot - SJSU Library", page_icon="🤖", initial_sidebar_state="expanded")
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

    # get bot
    if 'mybot' not in st.session_state:
        # st.session_state.mybot = at.getAgent(memory)
        st.session_state.mybot = at.getAgent()
    bot = st.session_state.mybot

    # get context
    if 'ctx' not in st.session_state:
        st.session_state.ctx = at.Context(bot)
    ctx = st.session_state.ctx

    # get streamlit session
    if 'session_id' not in st.session_state:
        session_id = get_script_run_ctx().session_id
        st.session_state.session_id = session_id

    if 'reference' not in st.session_state:
        st.session_state.reference = ''

    # chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # display chat history
    for entry in st.session_state.chat_history:
        st.chat_message(entry['role'], avatar=AVATARS[entry['role']]).write(entry['content'])

    # messeges kept in streamlit session for display
    max_messages: int = 10  # Set the limit (K) of messages to keep
    allmsgs = memory.get()
    msgs = allmsgs[-max_messages:]

    # display chat history
    for msg in msgs:
        st.chat_message(ROLES[msg.role],avatar=AVATARS[msg.role]).write(msg.content)

    # chip
    if button1:
        asyncio.run(queryBot(cbconfig['button1']['content'],bot,cbconfig['button1']['chip'], ctx))
    if button2:
        asyncio.run(queryBot(cbconfig['button2']['content'],bot,cbconfig['button2']['chip'], ctx))
    if button3:
        asyncio.run(queryBot(cbconfig['button3']['content'],bot,cbconfig['button3']['chip'], ctx))

    # chat
    if user_query := st.chat_input(placeholder="Ask me about the SJSU Library!"):
        asyncio.run(queryBot(user_query,bot, ctx=ctx))




