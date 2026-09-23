import streamlit as st
import requests
from openai import OpenAI
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json


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

GEMINI_MODEL = "gemini-3.5-flash-lite"


# ============================================================
# 3. Secrets에서 API 키 가져오기
# ============================================================
# API 키를 코드에 직접 적지 않습니다.
#
# Streamlit Cloud의 Secrets에 다음과 같이 등록합니다.
#
# KOBIS_KEY = "KOBIS 인증키"
# GEMINI_API_KEY = "Gemini 인증키"
#
# 두 키 모두 코드에는 실제 값이 들어가지 않습니다.

try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

except Exception:
    st.info(
        "API 키 설정을 확인해주세요."
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
# 5. 한국 시간 기준 어제 날짜 구하기
# ============================================================

kst = ZoneInfo("Asia/Seoul")

today = datetime.now(kst).date()

yesterday = today - timedelta(days=1)

target_date = yesterday.strftime("%Y%m%d")


# ============================================================
# 6. KOBIS에서 어제 박스오피스 가져오기
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

    # KOBIS가 API 오류를 반환했는지 확인
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
# 7. 박스오피스 가져오기
# ============================================================

movies = get_boxoffice()


if not movies:

    st.info(
        "오늘은 영화 정보를 불러오지 못했어요. 잠시 후 다시 시도해주세요."
    )

    st.stop()


# ============================================================
# 8. 영화 목록 정리
# ============================================================

movie_data = []

for movie in movies:

    movie_data.append(
        {
            "rank": movie.get("rank", ""),
            "title": movie.get("movieNm", ""),
            "movieCd": movie.get("movieCd", ""),
            "audience": movie.get("audiCnt", "0"),
        }
    )


# ============================================================
# 9. 주요 영화 수 결정
# ============================================================
# 너무 많은 영화를 한꺼번에 분석하면 AI가 느려질 수 있기 때문에
# 상위 10편까지만 캐릭터 후보를 만듭니다.

movie_data = movie_data[:10]


# ============================================================
# 10. 영화 제목만 뽑기
# ============================================================

movie_titles = [
    movie["title"]
    for movie in movie_data
]


# ============================================================
# 11. 영화별 주요 등장인물 찾기
# ============================================================
# KOBIS에는 배우 정보는 있지만
# '이 배우가 어떤 주인공 역할을 맡았는지'가
# 항상 직접적으로 제공되는 것은 아닙니다.
#
# 그래서 영화 제목을 Gemini에게 전달해
# 주요 등장인물을 찾아오도록 합니다.
#
# 결과는 JSON으로 받습니다.

@st.cache_data(ttl=3600)
def find_movie_characters(movie_titles):

    title_text = "\n".join(
        [
            f"{index + 1}. {title}"
            for index, title in enumerate(movie_titles)
        ]
    )

    prompt = f"""
다음은 현재 박스오피스에 있는 영화 목록이다.

{title_text}

각 영화에서 관객이 가장 대표적으로 알고 있는
주요 등장인물 1~2명을 찾아라.

반드시 실제 영화에 등장하는 인물이어야 한다.
배우 이름이 아니라 캐릭터 이름을 사용한다.

영화에 실제 주요 등장인물이 확실하지 않다면
억지로 만들지 말고 빈 목록을 사용한다.

반드시 아래 JSON 형식으로만 답한다.

[
  {{
    "movie": "영화 제목",
    "characters": [
      "인물 이름",
      "인물 이름"
    ]
  }}
]

설명이나 마크다운은 절대 넣지 않는다.
"""

    try:

        response = client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "영화 정보를 정확하게 정리하는 "
                        "한국어 정보 도우미다."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        result = response.choices[0].message.content

        # 혹시 AI가 JSON 앞뒤에 불필요한 문자를 넣었을 때
        # JSON 부분만 찾아냅니다.

        start = result.find("[")

        end = result.rfind("]")

        if start == -1 or end == -1:

            return {}

        json_text = result[start:end + 1]

        parsed = json.loads(json_text)

        character_data = {}

        for item in parsed:

            movie_name = item.get("movie", "")

            characters = item.get(
                "characters",
                [],
            )

            if movie_name and characters:

                character_data[movie_name] = characters

        return character_data

    except Exception:

        return {}


# ============================================================
# 12. 등장인물 정보 가져오기
# ============================================================

character_data = find_movie_characters(
    movie_titles
)


# ============================================================
# 13. 캐릭터 선택 목록 만들기
# ============================================================

character_options = []

for movie in movie_data:

    movie_title = movie["title"]

    characters = character_data.get(
        movie_title,
        [],
    )

    for character in characters:

        character_options.append(
            {
                "character": character,
                "movie": movie_title,
                "rank": movie["rank"],
            }
        )


# ============================================================
# 14. 기본 화면
# ============================================================

st.title("🎬 영화 속 인물과 대화")

st.caption(
    f"{yesterday.strftime('%Y년 %m월 %d일')} "
    "박스오피스 영화의 주요 인물과 이야기해보세요."
)


# ============================================================
# 15. 캐릭터가 없는 경우
# ============================================================

if not character_options:

    st.info(
        "현재 영화의 등장인물 정보를 준비하지 못했어요. "
        "잠시 후 다시 시도해주세요."
    )

    st.stop()


# ============================================================
# 16. 캐릭터 이름 목록 만들기
# ============================================================

character_labels = []

for item in character_options:

    label = (
        f"{item['character']} "
        f"· {item['movie']}"
    )

    character_labels.append(label)


# ============================================================
# 17. 캐릭터 선택
# ============================================================

selected_label = st.selectbox(
    "🎭 대화할 인물을 선택하세요",
    character_labels,
)


# 선택한 캐릭터 찾기
selected_index = character_labels.index(
    selected_label
)

selected_character = character_options[
    selected_index
]

character_name = selected_character[
    "character"
]

movie_name = selected_character[
    "movie"
]


# ============================================================
# 18. 선택한 캐릭터의 영화 컨셉 만들기
# ============================================================
# 캐릭터와 영화의 분위기에 맞는 화면을 만들기 위해
# 영화 제목을 바탕으로 색상과 분위기를 결정합니다.

@st.cache_data(ttl=3600)
def make_character_theme(
    movie_name,
    character_name,
):

    prompt = f"""
영화 "{movie_name}"의 캐릭터 "{character_name}"를 위한
채팅 화면 테마를 만들어라.

다음 JSON 형식으로만 답한다.

{{
  "emoji": "어울리는 이모지 1개",
  "background": "HEX 색상",
  "accent": "HEX 색상",
  "description": "영화와 캐릭터의 분위기를 짧게 설명"
}}

HEX 색상은 실제 화면에서 사용하기 좋은 색상으로 한다.
설명은 한국어로 한다.
JSON 외의 글은 쓰지 않는다.
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

            return {
                "emoji": "🎬",
                "background": "#111827",
                "accent": "#60A5FA",
                "description": "영화 속 인물의 분위기",
            }

        return json.loads(
            result[start:end + 1]
        )

    except Exception:

        return {
            "emoji": "🎬",
            "background": "#111827",
            "accent": "#60A5FA",
            "description": "영화 속 인물의 분위기",
        }


theme = make_character_theme(
    movie_name,
    character_name,
)


# ============================================================
# 19. 채팅 화면 디자인
# ============================================================

background = theme.get(
    "background",
    "#111827",
)

accent = theme.get(
    "accent",
    "#60A5FA",
)

emoji = theme.get(
    "emoji",
    "🎬",
)

description = theme.get(
    "description",
    "",
)


st.markdown(
    f"""
    <style>

    .character-header {{
        background: linear-gradient(
            135deg,
            {background},
            #111827
        );

        border: 1px solid {accent};

        border-radius: 20px;

        padding: 25px;

        margin-bottom: 20px;

        color: white;
    }}

    .character-name {{
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 5px;
    }}

    .movie-name {{
        font-size: 17px;
        opacity: 0.85;
    }}

    .character-description {{
        margin-top: 15px;
        opacity: 0.9;
    }}

    </style>

    <div class="character-header">

        <div class="character-name">
            {emoji} {character_name}
        </div>

        <div class="movie-name">
            🎬 {movie_name}
        </div>

        <div class="character-description">
            {description}
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 20. 현재 선택된 캐릭터 기억하기
# ============================================================
# 캐릭터를 바꾸면 이전 캐릭터의 대화가 섞이지 않도록
# 캐릭터별로 대화 기록을 따로 저장합니다.

if "selected_character" not in st.session_state:

    st.session_state.selected_character = (
        character_name
    )

    st.session_state.character_messages = []


# 캐릭터가 변경된 경우
if (
    st.session_state.selected_character
    != character_name
):

    st.session_state.selected_character = (
        character_name
    )

    st.session_state.character_messages = []


# ============================================================
# 21. 캐릭터의 성격 설정
# ============================================================
# 이 내용은 사용자 화면에 표시되지 않습니다.
#
# AI는 기본적으로 영화 속 캐릭터처럼 말하지만,
# 실제 인물이 아니라 영화 속 캐릭터를 바탕으로 한
# 대화형 역할이라는 점을 유지합니다.

CHARACTER_SYSTEM_MESSAGE = f"""
너는 영화 "{movie_name}"에 등장하는
"{character_name}"을 바탕으로 만든 대화형 캐릭터야.

너의 역할은 "{character_name}"의 영화 속 성격,
말투, 가치관, 행동 방식, 경험을 최대한 자연스럽게
반영해서 대화하는 것이다.

사용자가 질문하면 단순히 영화 줄거리만 설명하지 말고
"{character_name}"이라면 어떻게 생각하고 말할지를 중심으로 답한다.

다만 영화에 실제로 나오지 않은 새로운 사실을
영화의 공식 설정인 것처럼 단정하지 않는다.

너는 중고등학생에게 이야기하는 친절한 캐릭터다.
어려운 말은 쉬운 말로 바꿔 설명한다.

반드시 순수 한국어로만 답한다.
영어 문장이나 외국어 문장을 사용하지 않는다.

캐릭터의 이름이나 영화 제목처럼 고유명사가 필요한 경우에는
한국어로 널리 쓰이는 표기를 사용한다.

사용자가 이전에 한 말을 기억하고
앞뒤 대화가 자연스럽게 이어지도록 답한다.
"""


# ============================================================
# 22. 이전 채팅 화면에 표시
# ============================================================

for message in st.session_state.character_messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


# ============================================================
# 23. 사용자 입력
# ============================================================

user_input = st.chat_input(
    f"{character_name}에게 말을 걸어보세요..."
)


# ============================================================
# 24. 사용자가 메시지를 보냈을 때
# ============================================================

if user_input:

    # --------------------------------------------------------
    # 사용자의 말을 저장
    # --------------------------------------------------------

    st.session_state.character_messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    # --------------------------------------------------------
    # 사용자 메시지 표시
    # --------------------------------------------------------

    with st.chat_message("user"):

        st.markdown(user_input)

    # --------------------------------------------------------
    # Gemini에게 보낼 전체 대화 만들기
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": CHARACTER_SYSTEM_MESSAGE,
        }
    ]

    messages.extend(
        st.session_state.character_messages
    )

    # --------------------------------------------------------
    # 캐릭터의 답변
    # --------------------------------------------------------

    with st.chat_message("assistant"):

        try:

            stream = client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=messages,
                stream=True,
            )

            # ------------------------------------------------
            # AI 답변을 실시간으로 보여주는 함수
            # ------------------------------------------------

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

            # API 오류가 나도
            # Streamlit의 긴 빨간 오류 화면을 보여주지 않습니다.

            assistant_answer = (
                "지금은 대답을 가져오지 못했어요. "
                "잠시 후 다시 이야기해 주세요."
            )

            st.write(
                assistant_answer
            )

    # --------------------------------------------------------
    # AI 답변 저장
    # --------------------------------------------------------

    st.session_state.character_messages.append(
        {
            "role": "assistant",
            "content": assistant_answer,
        }
    )


# ============================================================
# 25. 하단 안내
# ============================================================

st.caption(
    "💡 캐릭터를 바꾸면 새로운 인물과 처음부터 대화할 수 있어요."
)
