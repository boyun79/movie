import streamlit as st
from openai import OpenAI


# ============================================================
# 1. 페이지 기본 설정
# ============================================================

st.set_page_config(
    page_title="AI 정보 선생님",
    page_icon="💬",
    layout="centered",
)


# ============================================================
# 2. 화면 제목
# ============================================================

st.title("💬 AI 정보 선생님")
st.caption("궁금한 것을 편하게 물어보세요.")


# ============================================================
# 3. Gemini API 키 가져오기
# ============================================================
# 실제 API 키는 코드에 적지 않습니다.
# Streamlit의 Secrets에서 GEMINI_API_KEY를 가져옵니다.

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

except Exception:
    st.info(
        "Gemini API 키 설정이 필요합니다. "
        "Streamlit의 Secrets에 GEMINI_API_KEY를 등록해주세요."
    )
    st.stop()


# ============================================================
# 4. Gemini를 OpenAI 라이브러리로 연결
# ============================================================
# OpenAI 라이브러리를 사용하지만,
# base_url을 Gemini의 OpenAI 호환 주소로 설정합니다.

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)


# ============================================================
# 5. AI의 성격 설정
# ============================================================
# 이 문장은 화면에 표시하지 않고 AI에게만 전달합니다.

SYSTEM_MESSAGE = """
너는 중고등학생에게 설명하는 친절한 정보 선생님이야.
어려운 말은 쉬운 말로 바꿔 주고,
반드시 순수 한국어로만 답해.
"""


# ============================================================
# 6. 대화 기록 만들기
# ============================================================
# Streamlit은 화면을 다시 실행할 때마다 코드가 처음부터
# 실행되기 때문에 session_state에 대화 내용을 저장합니다.

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


# ============================================================
# 7. 이전 대화 화면에 표시
# ============================================================

for message in st.session_state.chat_messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ============================================================
# 8. 사용자 입력창
# ============================================================

user_input = st.chat_input(
    "궁금한 것을 입력하세요..."
)


# ============================================================
# 9. 사용자가 메시지를 보냈을 때
# ============================================================

if user_input:

    # --------------------------------------------------------
    # 사용자의 메시지를 대화 기록에 저장
    # --------------------------------------------------------

    st.session_state.chat_messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    # --------------------------------------------------------
    # 사용자의 메시지를 화면에 표시
    # --------------------------------------------------------

    with st.chat_message("user"):
        st.markdown(user_input)

    # --------------------------------------------------------
    # AI에게 보낼 전체 대화 만들기
    # --------------------------------------------------------
    # system 메시지를 먼저 넣고,
    # 그 뒤에 지금까지의 대화를 모두 넣습니다.
    # 그래서 AI가 이전 대화의 내용을 참고할 수 있습니다.

    messages = [
        {
            "role": "system",
            "content": SYSTEM_MESSAGE,
        }
    ]

    messages.extend(
        st.session_state.chat_messages
    )

    # --------------------------------------------------------
    # AI 답변 받기
    # --------------------------------------------------------

    with st.chat_message("assistant"):

        try:
            # Gemini에서 답변을 조금씩 받아옵니다.
            # stream=True이므로 답변이 한꺼번에 나오지 않고
            # 글자가 생성되는 대로 전달됩니다.

            stream = client.chat.completions.create(
                model="gemini-3.5-flash-lite",
                messages=messages,
                stream=True,
            )

            # ------------------------------------------------
            # 스트리밍되는 글자를 하나씩 화면에 표시
            # ------------------------------------------------

            def response_generator():

                for chunk in stream:

                    # 현재 조각에서 글자를 가져옵니다.
                    content = chunk.choices[0].delta.content

                    # 글자가 실제로 있는 경우에만 전달합니다.
                    if content:
                        yield content

            assistant_answer = st.write_stream(
                response_generator()
            )

        except Exception:
            # API 오류가 발생해도 긴 빨간색 오류 화면 대신
            # 짧은 한국어 안내만 보여줍니다.

            assistant_answer = (
                "AI 답변을 가져오지 못했어요. "
                "잠시 후 다시 시도해주세요."
            )

            st.write(assistant_answer)

    # --------------------------------------------------------
    # AI의 답변도 대화 기록에 저장
    # --------------------------------------------------------
    # 다음 질문을 할 때 AI가 이전 답변까지 기억할 수 있도록
    # session_state에 저장합니다.

    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": assistant_answer,
        }
    )
