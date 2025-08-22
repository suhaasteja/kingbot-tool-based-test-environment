import time, datetime
import streamlit as st
from sqlalchemy.sql import text
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit_feedback import streamlit_feedback
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


@st.cache_resource(ttl="1d")
def getDSConnection():
    return st.connection("mysqldb",autocommit=True)


def saveFB(feedback, ts):
    try:
        conn = getDSConnection()
        score = ''
        comment = ''
        timest = ts.replace('T', ' ')
        if feedback['score']:
            thumbs = (feedback['score']).strip()
            score = {"👍": "good", "👎": "bad"}[thumbs]
        if feedback['text']:
            comment = (feedback['text']).strip()
        with conn.session as s:
            params = {'fb':comment, 'timest':timest}
            clause = "UPDATE chathistory SET {0}=:fb WHERE timest=:timest".format(score)
            s.execute(text(clause), params)
            s.commit()
    except Exception as e:
        st.error(e)


def queryBot(user_query,bot,chip=''):
    current = datetime.datetime.now()
    st.session_state.moment = current.isoformat()
    session_id = st.session_state.session_id
    today = current.date()
    now = current.time()
    answer = ''

    st.chat_message("user", avatar=AVATARS["user"]).write(user_query)
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner(text="In progress..."):
            response = bot.chat(user_query)
            answer = response.response
            st.write(answer)

        # Save QA to database
        try:
            conn = getDSConnection()
            reference = ''
            with conn.session as s:
                query = user_query
                if chip:
                    query = user_query + ' - ' + chip
                if st.session_state.reference:
                    reference = st.session_state.reference
                s.execute(
                    text('INSERT INTO chathistory VALUES (:ts, :today, :time, :sid, :q, :a, :fb, :gd, :bd, :rf);'),
                    params=dict(ts=current, today=today, time=now, sid=session_id, q=query, a=answer, fb='', gd='', bd='', rf=''))
                s.commit()
        except Exception as e:
            st.error(e)


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
        st.session_state.mybot = at.getAngent(memory)
    bot = st.session_state.mybot

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
        queryBot(cbconfig['button1']['content'],bot,cbconfig['button1']['chip'])
    if button2:
        queryBot(cbconfig['button2']['content'],bot,cbconfig['button2']['chip'])
    if button3:
        queryBot(cbconfig['button3']['content'],bot,cbconfig['button3']['chip'])

    # chat
    if user_query := st.chat_input(placeholder="Ask me about the SJSU Library!"):
        queryBot(user_query,bot)

    # feedback, works outside user_query section
    feedback_kwargs = {
        "feedback_type": "thumbs",
        "optional_text_label": "Optional. Please provide extra information",
        "on_submit": saveFB,
    }

    if 'moment' in st.session_state:
        currents = st.session_state.moment
        streamlit_feedback(
            **feedback_kwargs, args=(currents,), key=currents,
        )




