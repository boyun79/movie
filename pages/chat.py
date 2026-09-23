import streamlit as st
import requests
import json
from openai import OpenAI
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# 1. 페이지 설정
# ============================================================

st.set_page_config(
    page_title="영화 속 인물과 대화",
    page_icon="🎬",
    layout="wide",
)


# ============================================================
# 2. 기본 설정
# ============================================================

KOBIS_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 사용자가 요청한 모델 이름을 그대로 사용합니다.
GEMINI_MODEL = "gemini-3.5-flash-lite"


# ============================================================
# 3. API 키 가져오기
# ============================================================
# 실제 API 키는 코드에 적지 않습니다.
# Streamlit Cloud의 Secrets에서 가져옵니다.

try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

except Exception:
    st.info(
        "API 키 설정을 확인해주세요. "
        "Streamlit Secrets에 KOBIS_KEY와 GEMINI_API_KEY가 필요합니다."
    )
    st.stop()


# ============================================================
# 4. Gemini 연결
# ============================================================

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL,
)


# ============================================================
# 5. 한국 시간 기준으로 어제 날짜 계산
# ============================================================

kst = ZoneInfo("Asia/Seoul")

today = datetime.now(kst).date()

yesterday = today - timedelta(days=1)

target_date = yesterday.strftime("%Y%m%d")


# ============================================================
# 6. KOBIS 박스오피스 가져오기
# ============================================================

@st.cache_data(ttl=600)
def get_boxoffice():

    params = {
        "key": KOBIS_KEY,
        "targetDt": target_date,
    }

    try:

        response = requests.get(
            KOBIS_API_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except Exception:
        return None

    # KOBIS API 자체 오류
    if "faultInfo" in data:
        return None

    try:

        movie_list = (
            data["boxOfficeResult"]
            ["dailyBoxOfficeList"]
        )

    except (KeyError, TypeError):
        return None

    return movie_list


# ============================================================
# 7. 박스오피스 실행
# ============================================================

movies = get_boxoffice()


if not movies:

    st.info(
        "어제 박스오피스 정보를 가져오지 못했어요. "
        "잠시 후 다시 시도해주세요."
    )

    st.stop()


# ============================================================
# 8. 영화 목록 정리
# ============================================================

movie_data = []

for movie in movies:

    movie_data.append(
        {
            "rank": int(movie.get("rank", 0)),
            "title": movie.get("movieNm", ""),
            "movieCd": movie.get("movieCd", ""),
            "audience": int(movie.get("audiCnt", 0)),
        }
    )


# ============================================================
# 9. 화면 제목
# ============================================================

st.title("🎬 영화 속 인물과 대화")

st.caption(
    f"{yesterday.strftime('%Y년 %m월 %d일')} "
    "박스오피스에 있는 영화의 인물과 이야기해보세요."
)


# ============================================================
# 10. 영화 선택
# ============================================================
# 먼저 박스오피스에 있는 모든 영화를 보여줍니다.
#
# 예:
# 1위 스파이더맨
# 2위 오디세이
# 3위 ...
#
# 사용자가 영화를 하나 선택하면
# 그 영화의 등장인물을 보여줍니다.

movie_labels = []

for movie in movie_data:

    label = (
        f"{movie['rank']}위  ·  "
        f"{movie['title']}"
    )

    movie_labels.append(label)


selected_movie_label = st.selectbox(
    "🎞️ 먼저 영화를 선택하세요",
    movie_labels,
    key="movie_selector",
)


# 선택한 영화의 위치 찾기
selected_movie_index = movie_labels.index(
    selected_movie_label
)

selected_movie = movie_data[
    selected_movie_index
]

selected_movie_title = selected_movie["title"]


# ============================================================
# 11. 선택한 영화 표시
# ============================================================

st.markdown(
    f"### 🎞️ {selected_movie_title}"
)

st.caption(
    f"박스오피스 {selected_movie['rank']}위 · "
    f"어제 관객 {selected_movie['audience']:,}명"
)


# ============================================================
# 12. 선택한 영화의 등장인물 찾기
# ============================================================
# 영화 하나를 선택할 때마다 그 영화의 주요 등장인물을
# Gemini에게 물어봅니다.
#
# 너무 많은 인물을 만들지 않고
# 대표적인 인물을 최대 6명까지 보여줍니다.

@st.cache_data(ttl=3600)
def get_characters(movie_title):

    prompt = f"""
영화 "{movie_title}"에 실제로 등장하는
대표적인 주요 등장인물을 찾아줘.

중고등학생이 영화 속 캐릭터와 대화할 수 있도록
유명하고 중요한 등장인물을 최대 6명까지 골라줘.

배우 이름이 아니라 캐릭터 이름을 써줘.

실제로 존재하지 않는 인물을 만들어내면 안 돼.
확실하지 않은 인물은 넣지 마.

반드시 다음 JSON 형식만 출력해.

[
    {{
        "name": "캐릭터 이름",
        "role": "캐릭터를 아주 짧게 설명"
    }}
]

설명이나 마크다운은 JSON 밖에 쓰지 마.
"""

    try:

        response = client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "영화 등장인물 정보를 정확하게 "
                        "정리하는 도우미야."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        result = response.choices[0].message.content

        # JSON 부분만 추출합니다.
        start = result.find("[")
        end = result.rfind("]")

        if start == -1 or end == -1:
            return []

        json_text = result[
            start:end + 1
        ]

        characters = json.loads(
            json_text
        )

        if not isinstance(characters, list):
            return []

        return characters[:6]

    except Exception:

        return []


characters = get_characters(
    selected_movie_title
)


# ============================================================
# 13. 등장인물 선택
# ============================================================

if not characters:

    st.info(
        "이 영화의 주요 등장인물 정보를 준비하지 못했어요. "
        "다른 영화를 선택해보세요."
    )

    st.stop()


character_options = []

for character in characters:

    name = character.get(
        "name",
        "이름 없음",
    )

    role = character.get(
        "role",
        "",
    )

    character_options.append(
        f"{name}  ·  {role}"
    )


selected_character_label = st.selectbox(
    "🎭 대화할 등장인물을 선택하세요",
    character_options,
    key=f"character_{selected_movie_title}",
)


selected_character_index = character_options.index(
    selected_character_label
)

selected_character = characters[
    selected_character_index
]

character_name = selected_character.get(
    "name",
    "",
)

character_role = selected_character.get(
    "role",
    "",
)


# ============================================================
# 14. 영화 컨셉 만들기
# ============================================================
# 선택한 영화의 분위기를 분석해서
# 채팅 화면의 배경색과 강조색을 정합니다.
#
# 예:
# SF 영화 → 어두운 미래적인 분위기
# 판타지 → 신비로운 분위기
# 모험 → 모험 영화 같은 분위기
#
# 화면에는 이 요청 내용 자체를 보여주지 않습니다.

@st.cache_data(ttl=3600)
def get_movie_theme(movie_title):

    prompt = f"""
영화 "{movie_title}"의 전체적인 시각적 분위기를 분석해서
채팅 화면용 테마를 만들어줘.

영화의 장르와 분위기에 어울리는
배경색과 강조색을 골라줘.

반드시 JSON만 출력해.

{{
    "emoji": "대표 이모지 1개",
    "background": "#HEX색상",
    "accent": "#HEX색상",
    "text": "#HEX색상",
    "description": "영화 분위기를 한 문장으로 설명"
}}
"""

    try:

        response = client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        result = response.choices[0].message.content

        start = result.find("{")
        end = result.rfind("}")

        if start == -1 or end == -1:

            raise ValueError()

        theme = json.loads(
            result[start:end + 1]
        )

        return theme

    except Exception:

        # 테마를 가져오지 못해도
        # 채팅 기능 자체는 작동하도록 기본 테마를 사용합니다.

        return {
            "emoji": "🎬",
            "background": "#182033",
            "accent": "#7C83FD",
            "text": "#FFFFFF",
            "description": "영화 속 세계로 들어가 대화해보세요.",
        }


theme = get_movie_theme(
    selected_movie_title
)


# ============================================================
# 15. 테마 값 가져오기
# ============================================================

theme_emoji = theme.get(
    "emoji",
    "🎬",
)

theme_background = theme.get(
    "background",
    "#182033",
)

theme_accent = theme.get(
    "accent",
    "#7C83FD",
)

theme_text = theme.get(
    "text",
    "#FFFFFF",
)

theme_description = theme.get(
    "description",
    "영화 속 세계로 들어가 대화해보세요.",
)


# ============================================================
# 16. 영화 컨셉 화면
# ============================================================
# 이전 코드에서 HTML이 그대로 보였던 부분을
# st.html()로 변경했습니다.

st.html(
    f"""
    <div style="
        background: linear-gradient(
            135deg,
            {theme_background},
            #111827
        );
        border: 2px solid {theme_accent};
        border-radius: 24px;
        padding: 30px;
        margin-top: 20px;
        margin-bottom: 25px;
        color: {theme_text};
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    ">

        <div style="
            font-size: 36px;
            font-weight: 800;
            margin-bottom: 8px;
        ">
            {theme_emoji} {selected_movie_title}
        </div>

        <div style="
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 10px;
        ">
            🎭 {character_name}
        </div>

        <div style="
            font-size: 15px;
            opacity: 0.85;
        ">
            {theme_description}
        </div>

    </div>
    """
)


# ============================================================
# 17. 현재 캐릭터가 바뀌었는지 확인
# ============================================================
# 영화나 캐릭터를 바꾸면 이전 캐릭터와의 대화가
# 새로운 캐릭터에게 섞이지 않도록 합니다.

current_character_key = (
    f"{selected_movie_title}|{character_name}"
)


if (
    "current_character_key"
    not in st.session_state
):

    st.session_state.current_character_key = (
        current_character_key
    )

    st.session_state.character_messages = []


elif (
    st.session_state.current_character_key
    != current_character_key
):

    st.session_state.current_character_key = (
        current_character_key
    )

    st.session_state.character_messages = []


# ============================================================
# 18. 캐릭터 성격 설정
# ============================================================
# 이 내용은 화면에 표시하지 않습니다.
#
# 선택한 영화와 캐릭터를 바탕으로
# AI가 영화 속 인물처럼 대화하도록 합니다.

CHARACTER_SYSTEM_MESSAGE = f"""
너는 영화 "{selected_movie_title}"에 등장하는
"{character_name}"을 바탕으로 만든 대화형 캐릭터야.

이 캐릭터의 영화 속 성격과 말투,
가치관과 행동 방식을 최대한 자연스럽게 반영해.

캐릭터 설명:
{character_role}

사용자가 질문하면 단순한 영화 설명자가 아니라
"{character_name}"이라면 어떻게 생각하고
어떻게 말할지를 중심으로 대답해.

영화에 실제로 나오지 않은 내용을
공식 영화 설정인 것처럼 거짓으로 단정하지 마.

중고등학생과 대화한다고 생각하고
어려운 말은 쉽게 설명해.

반드시 순수 한국어로만 답해.

이전 대화의 내용을 기억하고
자연스럽게 이어서 대화해.

캐릭터의 성격을 유지하되
사용자의 질문에 도움이 되는 답을 해.
"""


# ============================================================
# 19. 이전 대화 표시
# ============================================================

for message in st.session_state.character_messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


# ============================================================
# 20. 채팅 입력
# ============================================================

user_input = st.chat_input(
    f"{character_name}에게 말을 걸어보세요..."
)


# ============================================================
# 21. 사용자 메시지가 들어왔을 때
# ============================================================

if user_input:

    # 사용자 메시지 저장
    st.session_state.character_messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    # 사용자 메시지 표시
    with st.chat_message("user"):

        st.markdown(
            user_input
        )

    # AI에게 전달할 전체 대화
    messages = [
        {
            "role": "system",
            "content": CHARACTER_SYSTEM_MESSAGE,
        }
    ]

    messages.extend(
        st.session_state.character_messages
    )

    # ========================================================
    # 22. AI 답변 스트리밍
    # ========================================================

    with st.chat_message("assistant"):

        try:

            stream = client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=messages,
                stream=True,
            )

            def generate_response():

                for chunk in stream:

                    content = (
                        chunk.choices[0]
                        .delta
                        .content
                    )

                    if content:
                        yield content

            assistant_answer = st.write_stream(
                generate_response()
            )

        except Exception:

            assistant_answer = (
                "지금은 대답을 가져오지 못했어요. "
                "잠시 후 다시 이야기해 주세요."
            )

            st.write(
                assistant_answer
            )

    # AI 답변 저장
    st.session_state.character_messages.append(
        {
            "role": "assistant",
            "content": assistant_answer,
        }
    )


# ============================================================
# 23. 하단 안내
# ============================================================

st.divider()

st.caption(
    "🎬 다른 영화를 선택하면 그 영화의 등장인물과 "
    "새로운 분위기의 채팅을 시작할 수 있어요."
)
