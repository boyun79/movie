import streamlit as st
import requests
import html
from openai import OpenAI
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 기본 페이지 설정
# =========================================================

st.set_page_config(
    page_title="영화 속 인물과 대화",
    page_icon="🎬",
    layout="wide",
)


# =========================================================
# API 주소
# =========================================================

BOXOFFICE_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

MOVIE_INFO_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "movie/searchMovieInfo.json"
)

GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)

GEMINI_MODEL = "gemini-3.5-flash-lite"


# =========================================================
# Streamlit Secrets에서 API 키 가져오기
# =========================================================

try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

except Exception:
    st.info(
        "KOBIS_KEY와 GEMINI_API_KEY를 "
        "Streamlit Secrets에 등록해주세요."
    )
    st.stop()


# =========================================================
# Gemini 연결
# =========================================================

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL,
)


# =========================================================
# 한국 시간 기준으로 어제 날짜 계산
# =========================================================

kst = ZoneInfo("Asia/Seoul")

today = datetime.now(kst).date()

yesterday = today - timedelta(days=1)

target_date = yesterday.strftime("%Y%m%d")


# =========================================================
# 어제 박스오피스 가져오기
# =========================================================

@st.cache_data(ttl=600)
def get_boxoffice():

    params = {
        "key": KOBIS_KEY,
        "targetDt": target_date,
    }

    try:

        response = requests.get(
            BOXOFFICE_API_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except Exception:
        return []

    # KOBIS API 오류
    if "faultInfo" in data:
        return []

    try:

        return data["boxOfficeResult"]["dailyBoxOfficeList"]

    except (KeyError, TypeError):
        return []


# =========================================================
# 영화 상세 정보 가져오기
# =========================================================

@st.cache_data(ttl=3600)
def get_movie_info(movie_code):

    params = {
        "key": KOBIS_KEY,
        "movieCd": movie_code,
    }

    try:

        response = requests.get(
            MOVIE_INFO_API_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if "faultInfo" in data:
            return None

        return data["movieInfoResult"]["movieInfo"]

    except Exception:
        return None


# =========================================================
# 박스오피스 데이터 가져오기
# =========================================================

movies = get_boxoffice()


if not movies:

    st.info(
        "어제 박스오피스 정보를 가져오지 못했어요. "
        "KOBIS API 키와 Streamlit Secrets 설정을 확인하거나 "
        "잠시 후 다시 시도해주세요."
    )

    st.stop()


# =========================================================
# 영화 데이터 정리
# =========================================================

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


# =========================================================
# 페이지 제목
# =========================================================

st.title("🎬 영화 속 인물과 대화")

st.caption(
    f"{yesterday.strftime('%Y년 %m월 %d일')} "
    "박스오피스의 영화 속 인물을 만나보세요."
)


# =========================================================
# 영화 선택
# =========================================================

movie_labels = []

for movie in movie_data:

    movie_labels.append(
        f"{movie['rank']}위  ·  {movie['title']}"
    )


selected_movie_label = st.selectbox(
    "🎞️ 먼저 영화를 선택하세요",
    movie_labels,
)


selected_movie_index = movie_labels.index(
    selected_movie_label
)

selected_movie = movie_data[selected_movie_index]

movie_title = selected_movie["title"]

movie_code = selected_movie["movieCd"]


# =========================================================
# 선택한 영화의 상세 정보 가져오기
# =========================================================

movie_info = get_movie_info(movie_code)


if not movie_info:

    st.info(
        "이 영화의 상세정보를 가져오지 못했어요. "
        "잠시 후 다시 시도하거나 다른 영화를 선택해보세요."
    )

    st.stop()


# =========================================================
# 영화 장르 가져오기
# =========================================================

genres = movie_info.get("genres", [])

genre_names = []

for genre in genres:

    genre_name = genre.get("genreNm", "")

    if genre_name:
        genre_names.append(genre_name)


genre_text = " · ".join(genre_names)


# =========================================================
# KOBIS에 등록된 실제 등장인물 가져오기
# =========================================================

actors = movie_info.get("actors", [])

characters = []


for actor in actors:

    cast_name = actor.get("cast", "")

    actor_name = actor.get("peopleNm", "")

    # 배역 이름이 있는 경우만 사용
    if cast_name:

        characters.append(
            {
                "name": cast_name,
                "actor": actor_name,
            }
        )


# =========================================================
# 중복 캐릭터 제거
# =========================================================

unique_characters = []

seen_names = set()


for character in characters:

    name = character["name"]

    if name not in seen_names:

        seen_names.add(name)

        unique_characters.append(character)


characters = unique_characters


# =========================================================
# 등장인물이 없는 경우
# =========================================================

if not characters:

    st.info(
        "KOBIS에 등록된 이 영화의 배역 정보가 없습니다. "
        "다른 영화를 선택해보세요."
    )

    st.stop()


# =========================================================
# 등장인물 선택
# =========================================================

st.markdown(
    f"### 🎭 {movie_title}의 등장인물"
)

st.caption(
    "영화에 등록된 실제 배역 중에서 선택하세요."
)


character_labels = []


for character in characters:

    actor_name = character["actor"]

    if actor_name:

        character_labels.append(
            f"{character['name']}  ·  {actor_name}"
        )

    else:

        character_labels.append(
            character["name"]
        )


selected_character_label = st.selectbox(
    "대화할 인물을 선택하세요",
    character_labels,
)


selected_character_index = character_labels.index(
    selected_character_label
)


selected_character = characters[selected_character_index]

character_name = selected_character["name"]

actor_name = selected_character["actor"]


# =========================================================
# 영화 장르에 따른 화면 테마
# =========================================================

def get_theme(genres):

    genre_text_lower = " ".join(genres)


    # SF
    if any(
        word in genre_text_lower
        for word in ["SF", "에스에프", "과학"]
    ):

        return {
            "background": "#050816",
            "panel": "#0B1026",
            "panel2": "#111936",
            "accent": "#6EA8FE",
            "accent2": "#9B8AFB",
            "text": "#F5F7FF",
            "muted": "#AAB5D6",
            "emoji": "🚀",
            "pattern": (
                "radial-gradient("
                "circle at 20% 20%, "
                "rgba(110,168,254,.18) 0 2px, "
                "transparent 3px)"
            ),
        }


    # 판타지 / 모험
    if any(
        word in genre_text_lower
        for word in ["판타지", "모험"]
    ):

        return {
            "background": "#100B20",
            "panel": "#1B1230",
            "panel2": "#271A3D",
            "accent": "#D8A7FF",
            "accent2": "#8F7AEA",
            "text": "#FFF8FF",
            "muted": "#C7B9D9",
            "emoji": "✨",
            "pattern": (
                "radial-gradient("
                "circle at 15% 20%, "
                "rgba(216,167,255,.2) 0 2px, "
                "transparent 3px)"
            ),
        }


    # 액션 / 범죄 / 스릴러
    if any(
        word in genre_text_lower
        for word in ["액션", "범죄", "스릴러"]
    ):

        return {
            "background": "#120808",
            "panel": "#211010",
            "panel2": "#321515",
            "accent": "#FF6B5E",
            "accent2": "#FFB36B",
            "text": "#FFF7F5",
            "muted": "#D5B9B5",
            "emoji": "🔥",
            "pattern": (
                "linear-gradient("
                "135deg, "
                "rgba(255,107,94,.08) 25%, "
                "transparent 25% 50%, "
                "rgba(255,107,94,.08) 50% 75%, "
                "transparent 75%)"
            ),
        }


    # 드라마 / 멜로 / 로맨스
    if any(
        word in genre_text_lower
        for word in ["드라마", "멜로", "로맨스"]
    ):

        return {
            "background": "#180E18",
            "panel": "#261426",
            "panel2": "#351C32",
            "accent": "#F28CB8",
            "accent2": "#D9A7FF",
            "text": "#FFF7FC",
            "muted": "#D7B9CC",
            "emoji": "🌙",
            "pattern": (
                "radial-gradient("
                "circle at 80% 15%, "
                "rgba(242,140,184,.16) 0 100px, "
                "transparent 101px)"
            ),
        }


    # 애니메이션
    if any(
        word in genre_text_lower
        for word in ["애니메이션"]
    ):

        return {
            "background": "#07151A",
            "panel": "#0C242B",
            "panel2": "#12343C",
            "accent": "#57D6C7",
            "accent2": "#F5C86B",
            "text": "#F5FFFD",
            "muted": "#B4D8D4",
            "emoji": "🌈",
            "pattern": (
                "radial-gradient("
                "circle at 10% 10%, "
                "rgba(87,214,199,.15) 0 60px, "
                "transparent 61px)"
            ),
        }


    # 기본 테마
    return {
        "background": "#0E1117",
        "panel": "#171B24",
        "panel2": "#222936",
        "accent": "#8EA7FF",
        "accent2": "#B9C4FF",
        "text": "#F5F7FF",
        "muted": "#B0B7C5",
        "emoji": "🎬",
        "pattern": (
            "radial-gradient("
            "circle at 20% 20%, "
            "rgba(142,167,255,.13) 0 2px, "
            "transparent 3px)"
        ),
    }


# =========================================================
# 테마 적용
# =========================================================

theme = get_theme(genre_names)

background = theme["background"]

panel = theme["panel"]

panel2 = theme["panel2"]

accent = theme["accent"]

accent2 = theme["accent2"]

text_color = theme["text"]

muted = theme["muted"]

emoji = theme["emoji"]


# =========================================================
# 전체 화면 CSS
# =========================================================

st.markdown(
    f"""
    <style>

    .stApp {{
        background:
            {theme["pattern"]},
            {background};

        background-size:
            180px 180px,
            auto;

        color:
            {text_color};
    }}


    .block-container {{
        max-width:
            1050px;

        padding-top:
            2rem;

        padding-bottom:
            5rem;
    }}


    .stApp p,
    .stApp label,
    .stApp span {{
        color:
            {text_color};
    }}


    .movie-world {{
        background:
            linear-gradient(
                135deg,
                {panel},
                {panel2}
            );

        border:
            1px solid {accent};

        border-radius:
            28px;

        padding:
            38px;

        margin:
            10px 0 30px 0;

        box-shadow:
            0 20px 60px rgba(0,0,0,.35);

        position:
            relative;

        overflow:
            hidden;
    }}


    .movie-world::after {{
        content:
            "";

        position:
            absolute;

        width:
            240px;

        height:
            240px;

        right:
            -80px;

        top:
            -100px;

        border-radius:
            50%;

        background:
            {accent};

        opacity:
            .08;
    }}


    .world-rank {{
        color:
            {accent};

        font-size:
            14px;

        font-weight:
            700;

        letter-spacing:
            1px;
    }}


    .world-title {{
        color:
            {text_color};

        font-size:
            42px;

        font-weight:
            900;

        margin-top:
            8px;
    }}


    .world-subtitle {{
        color:
            {muted};

        font-size:
            16px;

        margin-top:
            10px;
    }}


    div[data-baseweb="select"] > div {{
        background:
            {panel2};

        border:
            1px solid {accent};

        color:
            {text_color};

        border-radius:
            14px;
    }}


    div[data-testid="stChatMessage"] {{
        background:
            {panel};

        border:
            1px solid rgba(255,255,255,.08);

        border-radius:
            18px;

        margin-bottom:
            12px;

        padding:
            8px;
    }}


    div[data-testid="stChatInput"] {{
        border:
            1px solid {accent};

        border-radius:
            18px;

        background:
            {panel};
    }}


    div[data-testid="stChatInput"] textarea {{
        background:
            {panel};

        color:
            {text_color};
    }}


    hr {{
        border-color:
            rgba(255,255,255,.12);
    }}


    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 영화 세계관 헤더
# =========================================================

safe_movie_title = html.escape(movie_title)

safe_character_name = html.escape(character_name)


st.markdown(
    f"""
    <div class="movie-world">

        <div class="world-rank">
            {emoji}
            BOX OFFICE #{selected_movie["rank"]}
        </div>

        <div class="world-title">
            {safe_movie_title}
        </div>

        <div class="world-subtitle">
            이 영화의 세계관 속에서
            {safe_character_name}와 대화해보세요.
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 현재 캐릭터 정보
# =========================================================

actor_text = ""

if actor_name:

    actor_text = (
        f"배우: {html.escape(actor_name)}"
    )


st.markdown(
    f"""
    <div style="
        background: {panel2};
        border-left: 5px solid {accent};
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 20px;
    ">

        <div style="
            color: {accent};
            font-size: 13px;
            font-weight: 700;
        ">
            🎭 CURRENT CHARACTER
        </div>

        <div style="
            color: {text_color};
            font-size: 27px;
            font-weight: 800;
            margin-top: 5px;
        ">
            {safe_character_name}
        </div>

        <div style="
            color: {muted};
            font-size: 14px;
            margin-top: 5px;
        ">
            {actor_text}
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 등장인물별 대화 기록 저장 공간
# =========================================================

# 영화 코드 + 등장인물 이름을 조합해서
# 각각의 캐릭터에게 별도의 대화방을 만들어줍니다.

if "chat_histories" not in st.session_state:

    st.session_state.chat_histories = {}


character_key = (
    f"{movie_code}|{character_name}"
)


# 해당 캐릭터의 대화 기록이 없으면
# 빈 대화방을 만들어줍니다.

if character_key not in st.session_state.chat_histories:

    st.session_state.chat_histories[character_key] = []


# 현재 캐릭터의 대화 기록을 가져옵니다.

character_messages = (
    st.session_state.chat_histories[character_key]
)


# =========================================================
# 대화 관리
# =========================================================

with st.expander("🗑️ 대화 관리"):

    st.write(
        "현재 선택한 등장인물과의 대화만 삭제할 수 있어요."
    )

    st.caption(
        "영화를 바꾸거나 다른 등장인물을 선택해도 "
        "기존 대화는 자동으로 삭제되지 않습니다."
    )

    delete_button = st.button(
        "🗑️ 이 등장인물과의 대화 지우기",
        key=f"delete_{character_key}",
        use_container_width=True,
    )


# =========================================================
# 대화 삭제
# =========================================================

if delete_button:

    st.session_state.chat_histories[character_key] = []

    st.success(
        "이 등장인물과의 대화를 지웠어요."
    )

    st.rerun()


# =========================================================
# 캐릭터의 시스템 메시지
# =========================================================

character_system_message = f"""
너는 영화 "{movie_title}"의 등장인물
"{character_name}"을 바탕으로 한 대화형 캐릭터야.

이 캐릭터의 영화 속 성격과 말투,
가치관과 행동 방식을 최대한 자연스럽게 반영해.

영화에 등록된 배역 정보:

캐릭터 이름:
{character_name}

배우:
{actor_name}

사용자와 대화할 때는 단순히 영화 해설자처럼 말하지 말고
가능한 한 "{character_name}"의 관점에서 이야기해.

다만 영화에 실제로 등장하지 않은 내용을
공식 설정인 것처럼 확정해서 말하지 마.

중고등학생에게 이야기한다고 생각하고
어려운 말은 쉬운 말로 바꿔 설명해.

반드시 순수 한국어로만 답해.

이전 대화의 내용을 기억해서
자연스럽게 대화를 이어가.

캐릭터의 성격은 유지하되
사용자의 질문에 도움이 되는 답을 해.
"""


# =========================================================
# 기존 대화 화면에 표시
# =========================================================

for message in character_messages:

    with st.chat_message(message["role"]):

        st.markdown(
            message["content"]
        )


# =========================================================
# 사용자 입력
# =========================================================

user_input = st.chat_input(
    f"{character_name}에게 말을 걸어보세요..."
)


# =========================================================
# 사용자가 메시지를 입력한 경우
# =========================================================

if user_input:

    # -----------------------------------------------------
    # 사용자 메시지를 현재 캐릭터의 대화 기록에 저장
    # -----------------------------------------------------

    character_messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )


    # -----------------------------------------------------
    # 사용자 메시지 화면에 표시
    # -----------------------------------------------------

    with st.chat_message("user"):

        st.markdown(
            user_input
        )


    # -----------------------------------------------------
    # Gemini에게 보낼 전체 대화 만들기
    # -----------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": character_system_message,
        }
    ]


    messages.extend(
        character_messages
    )


    # -----------------------------------------------------
    # Gemini 답변
    # -----------------------------------------------------

    with st.chat_message("assistant"):

        try:

            stream = client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=messages,
                stream=True,
            )


            # -------------------------------------------------
            # 스트리밍 답변을 한 글자씩 자연스럽게 표시
            # -------------------------------------------------

            def generate_response():

                for chunk in stream:

                    if not chunk.choices:
                        continue

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


    # -----------------------------------------------------
    # AI 답변도 현재 캐릭터의 대화 기록에 저장
    # -----------------------------------------------------

    character_messages.append(
        {
            "role": "assistant",
            "content": assistant_answer,
        }
    )


# =========================================================
# 페이지 하단 안내
# =========================================================

st.markdown(
    f"""
    <div style="
        text-align: center;
        color: {muted};
        padding-top: 30px;
        font-size: 13px;
    ">

        {emoji}
        {movie_title}의 세계에서
        {character_name}와 이야기를 나누고 있습니다.

    </div>
    """,
    unsafe_allow_html=True,
)
