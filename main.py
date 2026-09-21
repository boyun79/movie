import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# 1. 페이지 설정
# ============================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일별 박스오피스")


# ============================================================
# 2. 한국 시간 기준으로 어제 날짜 계산
# ============================================================
# Streamlit Cloud 서버가 한국 시간이 아닐 수 있기 때문에
# 반드시 한국 시간(Asia/Seoul)을 기준으로 계산합니다.

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
# 4. KOBIS 인증키 가져오기
# ============================================================
# 실제 인증키는 코드에 적지 않습니다.
# Streamlit Cloud의 Secrets에 KOBIS_KEY를 넣어주세요.

try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]

except Exception:
    st.error("KOBIS_KEY를 찾을 수 없습니다.")

    st.info(
        "Streamlit Cloud의 Settings → Secrets에\n\n"
        'KOBIS_KEY = "발급받은_인증키"\n\n'
        "형태로 등록했는지 확인해주세요."
    )

    st.stop()


# ============================================================
# 5. KOBIS 박스오피스 가져오기
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
            "잠시 후 다시 실행해주세요."
        )

    except requests.exceptions.RequestException as e:
        return None, (
            "KOBIS API에 접속하지 못했습니다.\n\n"
            f"오류 내용: {e}\n\n"
            "인터넷 연결 또는 KOBIS API 서버 상태를 확인해주세요."
        )

    except ValueError:
        return None, (
            "KOBIS API가 올바른 JSON 데이터를 반환하지 않았습니다."
        )

    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    # 따라서 faultInfo를 확인해야 합니다.
    if "faultInfo" in data:

        fault_info = data["faultInfo"]

        error_code = fault_info.get(
            "errorCode",
            "알 수 없음",
        )

        error_message = fault_info.get(
            "errorMessage",
            "인증키 또는 요청 정보를 확인해주세요.",
        )

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"오류 코드: {error_code}\n"
            f"오류 내용: {error_message}\n\n"
            "Streamlit Cloud의 Secrets에 등록한 "
            "KOBIS_KEY가 정확한지 확인해주세요."
        )

    try:
        movies = data["boxOfficeResult"]["dailyBoxOfficeList"]

    except (KeyError, TypeError):
        return None, (
            "KOBIS 응답에서 영화 목록을 찾을 수 없습니다.\n\n"
            "API 응답 구조를 확인해주세요."
        )

    if not movies:
        return None, (
            "조회된 영화 목록이 없습니다.\n\n"
            "다음 내용을 확인해주세요.\n\n"
            "1. 조회 날짜가 정상인지 확인\n"
            "2. KOBIS에서 해당 날짜의 데이터가 제공되는지 확인\n"
            "3. KOBIS API 서버 상태 확인"
        )

    return movies, None


# ============================================================
# 6. 영화 상세 정보 가져오기
# ============================================================

def get_movie_info(movie_code):
    """
    영화 코드(movieCd)를 이용해
    KOBIS 영화 상세 정보를 가져옵니다.
    """

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

    except Exception:
        return None

    # 인증키 오류 등의 경우
    if "faultInfo" in data:
        return None

    try:
        return data["movieInfoResult"]["movieInfo"]

    except (KeyError, TypeError):
        return None


# ============================================================
# 7. KOBIS 웹 데이터에서 포스터/줄거리 찾기
# ============================================================

def get_poster_data(movie_code):
    """
    KOBIS에서 사용하는 영화 데이터에서
    포스터와 줄거리 정보를 가져옵니다.

    이 부분은 포스터를 가져오지 못하더라도
    앱 전체가 중단되지 않도록 안전하게 처리합니다.
    """

    url = (
        "https://www.kobis.or.kr/kobis/business/main/"
        "searchMainDailyBoxOffice.do"
    )

    params = {
        "startDate": target_date,
        "endDate": target_date,
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except Exception:
        return None

    if not isinstance(data, list):
        return None

    for movie in data:

        if movie.get("movieCd") == movie_code:

            return {
                "poster": movie.get("thumbUrl"),
                "synopsis": movie.get("synop"),
            }

    return None


# ============================================================
# 8. 박스오피스 API 실행
# ============================================================

movies, error_message = get_boxoffice()


# ============================================================
# 9. 박스오피스 오류 처리
# ============================================================

if error_message:

    st.error("박스오피스 데이터를 불러오지 못했습니다.")

    st.warning(error_message)

    st.stop()


# ============================================================
# 10. 데이터프레임 만들기
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
# 11. 영화 목록이 없는 경우
# ============================================================

if df.empty:

    st.error("표시할 영화 데이터가 없습니다.")

    st.info(
        "KOBIS 응답은 확인되었지만 영화 목록이 비어 있습니다.\n\n"
        "조회 날짜와 KOBIS API 상태를 확인해주세요."
    )

    st.stop()


# ============================================================
# 12. 숫자 표시 함수
# ============================================================

def format_number(value):
    """숫자에 천 단위 쉼표를 붙입니다."""
    return f"{value:,}"


# ============================================================
# 13. 관객수가 가장 많은 영화 찾기
# ============================================================
# KOBIS 순위가 아니라 실제 관객수를 기준으로 찾습니다.

top_movie = (
    df.sort_values(
        "관객수",
        ascending=False,
    )
    .iloc[0]
)

top_movie_name = top_movie["영화명"]
top_movie_code = top_movie["movieCd"]


# ============================================================
# 14. 1위 영화 상세 정보 가져오기
# ============================================================

movie_info = get_movie_info(top_movie_code)

poster_data = get_poster_data(top_movie_code)


# ============================================================
# 15. 영화 정보 준비
# ============================================================

genre = ""
synopsis = ""
poster_url = ""


# 영화 상세 API에서 장르 가져오기
if movie_info:

    genres = movie_info.get("genres", [])

    if genres:

        genre_names = []

        for genre_item in genres:

            genre_name = genre_item.get("genreNm")

            if genre_name:
                genre_names.append(genre_name)

        genre = " · ".join(genre_names)


# 포스터와 줄거리 가져오기
if poster_data:

    poster_url = poster_data.get("poster") or ""

    synopsis = poster_data.get("synopsis") or ""


# ============================================================
# 16. 포스터 주소가 상대주소인 경우 보정
# ============================================================

if poster_url.startswith("/"):

    poster_url = (
        "https://www.kobis.or.kr"
        + poster_url
    )


# ============================================================
# 17. 줄거리가 없는 경우
# ============================================================

if not synopsis:

    synopsis = (
        "이 영화의 줄거리 정보가 현재 KOBIS에서 "
        "제공되지 않습니다."
    )


# ============================================================
# 18. 1위 영화 포스터 카드
# ============================================================

st.divider()

st.subheader("🏆 어제 관객수 1위")


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

    if genre:

        st.write(
            f"🎭 **장르:** {genre}"
        )

    st.write(
        f"📅 **개봉일:** {top_movie['개봉일']}"
    )

    st.write(
        f"👥 **어제 관객수:** "
        f"{format_number(top_movie['관객수'])}명"
    )

    st.write(
        f"👥 **누적 관객수:** "
        f"{format_number(top_movie['누적관객'])}명"
    )

    st.write(
        f"🖥️ **스크린수:** "
        f"{format_number(top_movie['스크린수'])}개"
    )

    st.markdown("### 📖 줄거리")

    st.write(synopsis)


# ============================================================
# 19. 전체 박스오피스
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
# 20. 관객수 TOP 5 그래프
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
# 21. 데이터 출처
# ============================================================

st.divider()

st.caption(
    f"데이터 출처: 영화진흥위원회(KOBIS) | "
    f"조회 기준일: {yesterday.strftime('%Y-%m-%d')}"
)
