import streamlit as st
import datetime
import boto3

from langchain_aws import ChatBedrock, ChatBedrockConverse 


def main():
    llm = ChatBedrockConverse(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        temperature=0.1,
        region_name="ap-northeast-1"
    )

    if "conversation" not in st.session_state:
        st.session_state.conversation = None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None

    # セッションIDの初期化（ページリフレッシュまで固定）
    if "sess_id" not in st.session_state:
        st.session_state.sess_id = str(int(datetime.datetime.now().timestamp())) ## session idとして現在時刻(秒単位まで)使用 (秒単位で切るためintで切った後にstrでStringに変換)
    sess_id = st.session_state.sess_id

    # #dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
    # dynamodb = boto3.resource("dynamodb")

    if 'messages' not in st.session_state:
        st.session_state['messages'] = [{"role": "assistant", "content": "初めまして、私はChatBotです。どんなことでも聞いてください。"}]

    if user_input := st.chat_input("質問を入力してください"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            response = llm.invoke(user_input)
            st.markdown(response)
            print(response)

if __name__ == '__main__':
    st.set_page_config(
        page_title="ChatBot",
        page_icon=":books:"
    )

    st.title("Chat Bot :books:")

    main()