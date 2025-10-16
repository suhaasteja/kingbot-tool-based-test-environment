import time, datetime
import streamlit as st
from sqlalchemy.sql import text
from streamlit.runtime.scriptrunner import get_script_run_ctx
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


def queryBot(user_query, bot, chip=None):
    """
    Langfuse tracing
    
    Captures :
    - User input
    - Chatbot output
    - Tools used
    - Data retrieved (from kingbot/onesearch)
    - Time taken
    - Errors
    """
    current = datetime.datetime.now()
    st.session_state.moment = current.isoformat()
    session_id = st.session_state.session_id
    
    # Clear previous tool executions
    st.session_state.tool_executions = []
    
    st.chat_message("user", avatar=AVATARS["user"]).write(user_query)
    
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner(text="In progress..."):
            answer = ""
            error_msg = None
            start_time = time.time()
            
            # Create trace using span context manager
            with at.langfuse_client.start_as_current_span(
                name="chat_query",
                input={"user_input": user_query}
            ) as trace:
                
                # Set trace metadata
                trace.update_trace(
                    user_id=session_id,
                    session_id=session_id,
                    metadata={
                        "timestamp": current.isoformat(),
                        "chip": chip
                    }
                )
                
                try:
                    # Agent chat happens here
                    handler = bot.chat(user_query)
                    answer = handler.response
                    elapsed_time = time.time() - start_time
                    
                    # Get tool execution data from session state
                    tools_used = st.session_state.tool_executions if hasattr(st.session_state, 'tool_executions') else []
                    
                    # Update trace with output and essential metadata
                    trace.update(
                        output={"chatbot_output": answer},
                        metadata={
                            "time_taken_seconds": round(elapsed_time, 2),
                            "tools_used": [tool["tool"] for tool in tools_used],
                            "tool_details": tools_used,  # Includes retrieved data and timing
                            "status": "success"
                        }
                    )
                    
                except Exception as e:
                    error_msg = str(e)
                    answer = f"Sorry, there was an error answering '{user_query}'"
                    elapsed_time = time.time() - start_time
                    
                    # Update trace with error info
                    trace.update(
                        output={"chatbot_output": answer},
                        metadata={
                            "time_taken_seconds": round(elapsed_time, 2),
                            "error": error_msg,
                            "error_type": type(e).__name__,
                            "status": "error"
                        }
                    )
                
                # Flush to ensure data is sent
                at.langfuse_client.flush()
            
            st.write(str(answer))
            
            if error_msg:
                with st.expander("⚠️ Error Details"):
                    st.error(error_msg)


if __name__ == "__main__":
    # Set up streamlit page
    st.set_page_config(
        page_title="Kingbot - SJSU Library",
        page_icon="🤖",
        initial_sidebar_state="expanded"
    )
    st.markdown(HIDEMENU, unsafe_allow_html=True)

    # Sidebar
    st.sidebar.markdown(cbconfig['side']['title'])
    st.sidebar.markdown(cbconfig['side']['intro'])
    st.sidebar.markdown("\n\n")
    st.sidebar.link_button(cbconfig['side']['policylabel'], cbconfig['side']['policylink'])

    # Main header
    col1, col2, col3 = st.columns([0.25, 0.1, 0.65], vertical_alignment="bottom")
    with col2:
        st.markdown(cbconfig['main']['logo'])
    with col3:
        st.title(cbconfig['main']['title'])
    st.markdown("\n\n")
    st.markdown("\n\n")

    # Chip buttons
    col21, col22, col23 = st.columns(3)
    with col21:
        button1 = st.button(cbconfig['button1']['label'])
    with col22:
        button2 = st.button(cbconfig['button2']['label'])
    with col23:
        button3 = st.button(cbconfig['button3']['label'])

    # Initialize memory (last 5 messages for bot prompt)
    if 'memory' not in st.session_state:
        memory = ChatMemoryBuffer.from_defaults(token_limit=5000)
        st.session_state.memory = memory
    memory = st.session_state.memory

    # Get bot
    if 'mybot' not in st.session_state:
        st.session_state.mybot = at.getAgent()
    bot = st.session_state.mybot

    # Get streamlit session
    if 'session_id' not in st.session_state:
        session_id = get_script_run_ctx().session_id
        st.session_state.session_id = session_id

    if 'reference' not in st.session_state:
        st.session_state.reference = ''

    # Display chat history (last 10 messages)
    max_messages: int = 10
    allmsgs = memory.get()
    msgs = allmsgs[-max_messages:]

    for msg in msgs:
        st.chat_message(ROLES[msg.role], avatar=AVATARS[msg.role]).write(msg.content)

    # Handle chip button clicks
    if button1:
        queryBot(cbconfig['button1']['content'], bot, cbconfig['button1']['chip'])
    if button2:
        queryBot(cbconfig['button2']['content'], bot, cbconfig['button2']['chip'])
    if button3:
        queryBot(cbconfig['button3']['content'], bot, cbconfig['button3']['chip'])

    # Handle chat input
    if user_query := st.chat_input(placeholder="Ask me about the SJSU Library!"):
        queryBot(user_query, bot)