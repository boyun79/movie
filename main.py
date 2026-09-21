```python
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# 1. 페이지 기본 설정
# ============================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일별 박스오피스")


# ============================================================
# 2. 한국 시간 기준으로 '어제' 계산
# ============================================================
# Streamlit Cloud 서버가 한국 시간이 아닐 수 있습니다.
# 따라서 서버의 시간을 그대로 사용하지 않고
# 한국 시간(Asia/Seoul)을 기준으로 날짜를 계산합니다.

kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()
yesterday = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식
# 예: 20260920
target_date = yesterday.strftime("%Y%m%d")

st.info(
    f"📅 조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} "
    "(한국 시간 기준)"
)


# ============================================================
# 3. KOBIS API 주소
# ============================================================

BOXOFFICE_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

MOVIE_INFO_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "movie/searchMovieInfo.json"
)


# ============================================================
# 4. Secrets에서 KOBIS 인증키 가져오기
# ============================================================
# 실제 인증키를 코드에 적지 않습니다.
# Streamlit Cloud의 Secrets에서 KOBIS_KEY를 읽습니다.

try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]

except Exception:
    st.error("KOBIS_KEY를 찾을 수 없습니다.")

    st.info(
        "Streamlit Cloud의 앱 설정 → Secrets에서 "
        "다음과 같이 등록했는지 확인해 주세요.\n\n"
        "KOBIS_KEY = \"발급받은_인증키\""
    )

    st.stop()


# ============================================================
# 5. KOBIS 일별 박스오피스 가져오기
# ============================================================

def get_boxoffice():
    """KOBIS에서 어제의 박스오피스 데이터를 가져옵니다."""

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

    except requests.exceptions.Timeout:
        return None, (
            "KOBIS API 요청 시간이 초과되었습니다.\n\n"
            "잠시 후 다시 실행해 주세요."
        )

    except requests.exceptions.RequestException as e:
        return None, (
            "KOBIS API에 접속하지 못했습니다.\n\n"
            f"오류 내용: {e}\n\n"
            "인터넷 연결이나 KOBIS API 서버 상태를 확인해 주세요."
        )

    except ValueError:
        return None, (
            "KOBIS API가 올바른 JSON 데이터를 반환하지 않았습니다."
        )

    # --------------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo를 반드시 확인합니다.
    # --------------------------------------------------------

    if "faultInfo" in data:

        fault_info = data["faultInfo"]

        error_code = fault_info.get(
            "errorCode",
            "알 수 없음",
        )

        error_message = fault_info.get(
            "errorMessage",
            "인증키 또는 요청 정보를 확인해 주세요.",
        )

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"- 오류 코드: {error_code}\n"
            f"- 오류 내용: {error_message}\n\n"
            "Streamlit Cloud의 Secrets에 등록한 "
            "KOBIS_KEY가 정확한지 확인해 주세요."
        )

    try:
        movies = data["boxOfficeResult"]["dailyBoxOfficeList"]

    except (KeyError, TypeError):
        return None, (
            "KOBIS 응답에서 영화 목록을 찾을 수 없습니다.\n\n"
            "API 응답 구조가 변경되었거나 "
            "일시적인 오류일 수 있습니다."
        )

    if not movies:
        return None, (
            "조회된 영화 목록이 없습니다.\n\n"
            "다음 내용을 확인해 주세요.\n\n"
            "1. 조회 날짜가 정상인지 확인하세요.\n"
            "2. KOBIS가 해당 날짜의 데이터를 제공하는지 확인하세요.\n"
            "3. KOBIS API 서버 상태를 확인하세요."
        )

    return movies, None


# ============================================================
# 6. 영화 상세 정보 가져오기
# ============================================================

def get_movie_info(movie_cd):
    """
    영화 코드(movieCd)를 이용해 KOBIS 영화 상세 정보를 가져옵니다.

    여기서 장르, 감독, 배우, 영화 줄거리 등을 가져옵니다.
    """

    params = {
        "key": KOBIS_KEY,
        "movieCd": movie_cd,
    }

    try:
        response = requests.get(
            MOVIE_INFO_API_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except Exception:
        return None

    # 영화 상세 정보가 정상적으로 있는지 확인합니다.
    try:
        movie_info = data["movieInfoResult"]["movieInfo"]

    except (KeyError, TypeError):
        return None

    return movie_info


# ============================================================
# 7. 포스터와 줄거리 가져오기
# ============================================================

def get_kobis_movie_card(movie_cd):
    """
    KOBIS 영화 페이지에서 사용하는 영화 정보를 찾아
    포스터와 줄거리 정보를 가져옵니다.

    공개된 KOBIS 영화 데이터에서 사용하는
    thumbUrl / synop 정보를 활용합니다.
    """

    # KOBIS 영화 검색 페이지에서 영화 코드를 검색합니다.
    search_url = (
        "https://kobis.or.kr/kobis/business/main/"
        "searchMainRealTicket.do"
    )

    params = {
        "movieCd": movie_cd,
    }

    try:
        response = requests.get(
            search_url,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

    except Exception:
        return None

    # 이 페이지가 JSON 형태의 데이터를 반환하는 경우
    # JSON으로 변환합니다.
    try:
        data = response.json()

    except ValueError:
        return None

    # 응답이 리스트 형태인지 확인합니다.
    if not isinstance(data, list):
        return None

    for movie in data:

        if movie.get("movieCd") == movie_cd:

            return {
                "poster": movie.get("thumbUrl"),
                "synopsis": movie.get("synop"),
                "genre": movie.get("genre"),
                "movie_name": movie.get("movieNm"),
            }

    return None


# ============================================================
# 8. 박스오피스 API 실행
# ============================================================

movies, error_message = get_boxoffice()


if error_message:

    st.error("박스오피스 데이터를 불러오지 못했습니다.")

    st.warning(error_message)

    st.stop()


# ============================================================
# 9. 박스오피스 데이터를 표 형태로 변환
# ============================================================

rows = []

for movie in movies:

    rows.append(
        {
            "순위": int(movie.get("rank", 0)),
            "영화명": movie.get("movieNm", ""),
            "개봉일": movie.get("openDt", "") or "-",
            "관객수": int(movie.get("audiCnt", 0)),
            "누적관객": int(movie.get("audiAcc", 0)),
            "스크린수": int(movie.get("scrnCnt", 0)),
            "movieCd": movie.get("movieCd", ""),
        }
    )


df = pd.DataFrame(rows)


# ============================================================
# 10. 영화 목록이 비어 있는 경우
# ============================================================

if df.empty:

    st.error("표시할 영화 데이터가 없습니다.")

    st.info(
        "KOBIS API의 응답은 확인되었지만 영화 목록이 비어 있습니다.\n\n"
        "조회 날짜와 KOBIS API 상태를 확인해 주세요."
    )

    st.stop()


# ============================================================
# 11. 숫자 표시 함수
# ============================================================

def format_number(value):
    """숫자를 123,456 형태로 표시합니다."""
    return f"{value:,}"


# ============================================================
# 12. 관객수가 가장 많은 영화 찾기
# ============================================================
# KOBIS의 순위(rank)가 아니라
# 실제 해당 날짜 관객수(audiCnt)를 기준으로 찾습니다.

top_movie = (
    df.sort_values(
        "관객수",
        ascending=False,
    )
    .iloc[0]
)

top_movie_name = top_movie["영화명"]
top_movie_cd = top_movie["movieCd"]


# ============================================================
# 13. 1위 영화의 상세 정보 가져오기
# ============================================================

movie_info = get_movie_info(top_movie_cd)

movie_card = get_kobis_movie_card(top_movie_cd)


# ============================================================
# 14. 영화 정보 기본값
# ============================================================

poster_url = None
synopsis = None
genre = None

if movie_card:

    poster_url = movie_card.get("poster")
    synopsis = movie_card.get("synopsis")
    genre = movie_card.get("genre")


# 영화 상세 API에서 장르 정보가 있다면 보완합니다.
if not genre and movie_info:

    genres = movie_info.get("genres", [])

    if genres:

        genre_names = []

        for item in genres:

            genre_name = item.get("genreNm")

            if genre_name:
                genre_names.append(genre_name)

        if genre_names:
            genre = " · ".join(genre_names)


# 줄거리가 없으면 안내 문구를 표시합니다.
if not synopsis:

    synopsis = (
        "이 영화의 줄거리 정보를 KOBIS에서 가져오지 못했습니다. "
        "영화 정보가 아직 등록되지 않았거나 제공되지 않을 수 있습니다."
    )


# ============================================================
# 15. 포스터 URL 보정
# ============================================================
# KOBIS 데이터의 thumbUrl이 상대주소(/common/...)인 경우
# 실제 KOBIS 주소를 붙여 완전한 URL로 만들어 줍니다.

if poster_url:

    if poster_url.startswith("/"):

        poster_url = (
            "https://www.kobis.or.kr"
            + poster_url
        )


# ============================================================
# 16. 오늘의 TOP 영화 카드
# ============================================================

st.divider()

st.subheader(
    f"🏆 어제 가장 많은 관객이 본 영화"
)


# 포스터와 영화 정보를 나란히 배치합니다.
poster_col, info_col = st.columns(
    [1, 2],
    gap="large",
)


# ------------------------------------------------------------
# 왼쪽: 포스터
# ------------------------------------------------------------

with poster_col:

    if poster_url:

        st.image(
            poster_url,
            use_container_width=True,
        )

    else:

        st.info(
            "포스터 이미지를 불러오지 못했습니다."
        )


# ------------------------------------------------------------
# 오른쪽: 영화 정보
# ------------------------------------------------------------

with info_col:

    st.markdown(
        f"# {top_movie_name}"
    )

    st.markdown(
        f"### 🏆 어제 관객수 {format_number(top_movie['관객수'])}명"
    )

    if genre:

        st.write(
            f"🎭 **장르:** {genre}"
        )

    st.write(
        f"📅 **개봉일:** {top_movie['개봉일']}"
    )

    st.markdown("### 📖 영화 줄거리")

    st.write(synopsis)


# ============================================================
# 17. 1위 영화 핵심 지표
# ============================================================

st.subheader("📌 오늘의 1위 영화 기록")

metric1, metric2, metric3 = st.columns(3)


with metric1:

    st.metric(
        "어제 관객수",
        f"{format_number(top_movie['관객수'])}명",
    )


with metric2:

    st.metric(
        "누적 관객수",
        f"{format_number(top_movie['누적관객'])}명",
    )


with metric3:

    st.metric(
        "스크린수",
        f"{format_number(top_movie['스크린수'])}개",
    )


# ============================================================
# 18. 전체 박스오피스 표
# ============================================================

st.divider()

st.subheader("📊 전체 박스오피스")

display_df = df.drop(
    columns=["movieCd"]
).copy()

display_df["관객수"] = display_df["관객수"].map(
    format_number
)

display_df["누적관객"] = display_df["누적관객"].map(
    format_number
)

display_df["스크린수"] = display_df["스크린수"].map(
    format_number
)


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 19. 관객수 TOP 5 그래프
# ============================================================

st.subheader("🎟️ 관객수 상위 5편")

top5 = (
    df.sort_values(
        "관객수",
        ascending=False,
    )
    .head(5)
    .copy()
)

chart_data = top5.set_index(
    "영화명"
)[["관객수"]]

st.bar_chart(chart_data)


# ============================================================
# 20. 데이터 출처
# ============================================================

st.divider()

st.caption(
    f"데이터 출처: 영화진흥위원회(KOBIS) | "
    f"조회 기준일: {yesterday.strftime('%Y-%m-%d')}"
)
```
