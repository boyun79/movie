import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# 1. 페이지 기본 설정
# ==================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일별 박스오피스")


# ==================================================
# 2. 한국 시간 기준으로 '어제' 계산
# ==================================================
# Streamlit Cloud 서버의 시간대가 한국과 다를 수 있기 때문에
# 반드시 한국 시간(Asia/Seoul)을 기준으로 날짜를 계산합니다.

kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()
yesterday = today_kst - timedelta(days=1)

# KOBIS에서 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

st.info(
    f"📅 조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')}"
    " (한국 시간 기준)"
)


# ==================================================
# 3. API 주소
# ==================================================

KOBIS_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

YOUTUBE_API_URL = (
    "https://www.googleapis.com/youtube/v3/search"
)


# ==================================================
# 4. KOBIS 박스오피스 데이터 가져오기
# ==================================================

def get_boxoffice():
    """KOBIS에서 어제의 박스오피스 데이터를 가져옵니다."""

    # Streamlit Cloud Secrets에서 API 키를 가져옵니다.
    try:
        kobis_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return None, (
            "KOBIS_KEY를 찾을 수 없습니다.\n\n"
            "Streamlit Cloud의 앱 설정 → Secrets에서 "
            "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
        )

    params = {
        "key": kobis_key,
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
            "KOBIS API가 올바른 JSON 데이터를 반환하지 않았습니다.\n\n"
            "잠시 후 다시 실행해 주세요."
        )

    # KOBIS는 인증키가 틀려도 HTTP 200을 반환할 수 있습니다.
    # 따라서 faultInfo를 반드시 확인합니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_code = fault_info.get(
            "errorCode",
            "알 수 없음",
        )

        fault_message = fault_info.get(
            "errorMessage",
            "인증키 또는 요청 정보를 확인해 주세요.",
        )

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"- 오류 코드: {fault_code}\n"
            f"- 오류 내용: {fault_message}\n\n"
            "특히 Streamlit Cloud의 Secrets에 등록한 "
            "KOBIS_KEY가 정확한지 확인해 주세요."
        )

    # 정상 응답에서 영화 목록을 가져옵니다.
    try:
        movies = data["boxOfficeResult"]["dailyBoxOfficeList"]

    except (KeyError, TypeError):
        return None, (
            "KOBIS 응답에서 영화 목록을 찾을 수 없습니다.\n\n"
            "API 응답 구조가 변경되었거나 "
            "일시적인 오류일 수 있습니다."
        )

    # 영화 목록이 비어 있는 경우
    if not movies:
        return None, (
            "조회된 영화 목록이 없습니다.\n\n"
            "다음 내용을 확인해 주세요.\n"
            "1. 조회 날짜가 정상인지 확인하세요.\n"
            "2. KOBIS가 해당 날짜의 데이터를 제공하는지 확인하세요.\n"
            "3. KOBIS API 서버 상태를 확인하세요."
        )

    return movies, None


# ==================================================
# 5. YouTube에서 예고편 찾기
# ==================================================

def find_trailer(movie_name):
    """
    영화명을 이용해서 YouTube에서 예고편을 검색합니다.

    검색 결과 중 영화 예고편과 관련성이 높은 영상을 선택합니다.
    """

    # YouTube API 키도 Secrets에서 가져옵니다.
    try:
        youtube_key = st.secrets["YOUTUBE_KEY"]

    except Exception:
        return None, (
            "YOUTUBE_KEY가 설정되어 있지 않습니다.\n\n"
            "Streamlit Cloud의 Secrets에 "
            "YOUTUBE_KEY를 등록해 주세요."
        )

    # 영화명 + 예고편으로 검색합니다.
    params = {
        "key": youtube_key,
        "part": "snippet",
        "q": f"{movie_name} 예고편",
        "type": "video",
        "maxResults": 10,
        "regionCode": "KR",
        "relevanceLanguage": "ko",
        "videoEmbeddable": "true",
    }

    try:
        response = requests.get(
            YOUTUBE_API_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except requests.exceptions.Timeout:
        return None, (
            "YouTube 예고편 검색 시간이 초과되었습니다.\n\n"
            "잠시 후 다시 실행해 주세요."
        )

    except requests.exceptions.RequestException as e:
        return None, (
            "YouTube API에 접속하지 못했습니다.\n\n"
            f"오류 내용: {e}\n\n"
            "YOUTUBE_KEY와 YouTube API 설정을 확인해 주세요."
        )

    except ValueError:
        return None, (
            "YouTube API가 올바른 JSON 데이터를 반환하지 않았습니다."
        )

    # YouTube API에서 오류를 반환한 경우
    if "error" in data:
        error = data["error"]

        message = error.get(
            "message",
            "YouTube API 오류가 발생했습니다.",
        )

        return None, (
            "YouTube API에서 오류를 반환했습니다.\n\n"
            f"오류 내용: {message}\n\n"
            "YouTube Data API v3가 활성화되어 있는지와 "
            "YOUTUBE_KEY가 정확한지 확인해 주세요."
        )

    videos = data.get("items", [])

    if not videos:
        return None, (
            f"'{movie_name}'의 예고편을 찾지 못했습니다.\n\n"
            "YouTube 검색 결과가 없거나 "
            "임베드 가능한 예고편이 없을 수 있습니다."
        )

    # 검색 결과를 살펴보면서 '예고편'이라는 단어가 포함된
    # 영상을 우선적으로 선택합니다.
    selected_video = None

    for video in videos:
        snippet = video.get("snippet", {})

        title = snippet.get("title", "").lower()

        if "예고편" in title or "trailer" in title:
            selected_video = video
            break

    # '예고편'이 포함된 영상이 없으면 첫 번째 검색 결과 사용
    if selected_video is None:
        selected_video = videos[0]

    video_id = selected_video.get("id", {}).get("videoId")

    if not video_id:
        return None, (
            "YouTube 검색 결과에서 영상 ID를 찾지 못했습니다."
        )

    title = selected_video.get(
        "snippet",
        {},
    ).get(
        "title",
        movie_name,
    )

    channel_title = selected_video.get(
        "snippet",
        {},
    ).get(
        "channelTitle",
        "",
    )

    return {
        "video_id": video_id,
        "title": title,
        "channel": channel_title,
    }, None


# ==================================================
# 6. KOBIS API 실행
# ==================================================

movies, error_message = get_boxoffice()


# ==================================================
# 7. KOBIS 오류 처리
# ==================================================

if error_message:
    st.error("박스오피스 데이터를 불러오지 못했습니다.")
    st.warning(error_message)
    st.stop()


# ==================================================
# 8. 영화 데이터를 표에 맞게 변환
# ==================================================

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
        }
    )


df = pd.DataFrame(rows)


# 혹시 영화 목록이 비어 있는 경우
if df.empty:
    st.error("표시할 영화 데이터가 없습니다.")

    st.info(
        "KOBIS API의 응답은 확인되었지만 영화 목록이 비어 있습니다.\n\n"
        "조회 날짜와 KOBIS API 상태를 확인해 주세요."
    )

    st.stop()


# ==================================================
# 9. 숫자 표시용 함수
# ==================================================

def format_number(value):
    """숫자에 천 단위 쉼표를 붙입니다."""
    return f"{value:,}"


# ==================================================
# 10. 그 날 관객수가 가장 많은 영화 찾기
# ==================================================

# KOBIS의 rank가 아니라 실제 관객수(audiCnt)를 기준으로
# 가장 많은 관객을 기록한 영화를 찾습니다.

top_movie = df.sort_values(
    "관객수",
    ascending=False,
).iloc[0]


top_movie_name = top_movie["영화명"]


# ==================================================
# 11. 1위 영화 정보
# ==================================================

st.subheader(
    f"🏆 어제 가장 많은 관객이 본 영화: {top_movie_name}"
)


# 큰 지표 카드 세 개
col1, col2, col3 = st.columns(3)


with col1:
    st.metric(
        "어제 관객수",
        f"{format_number(top_movie['관객수'])}명",
    )


with col2:
    st.metric(
        "누적 관객수",
        f"{format_number(top_movie['누적관객'])}명",
    )


with col3:
    st.metric(
        "스크린수",
        f"{format_number(top_movie['스크린수'])}개",
    )


# ==================================================
# 12. 전체 박스오피스 표
# ==================================================

st.subheader("📊 전체 박스오피스")


display_df = df.copy()

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


# ==================================================
# 13. 관객수 상위 5편 그래프
# ==================================================

st.subheader("🎟️ 관객수 상위 5편")


top5 = (
    df.sort_values(
        "관객수",
        ascending=False,
    )
    .head(5)
    .copy()
)


chart_data = top5.set_index("영화명")[["관객수"]]


st.bar_chart(chart_data)


# ==================================================
# 14. 1위 영화 예고편
# ==================================================

st.divider()

st.subheader(
    f"🎬 {top_movie_name} 예고편"
)

st.caption(
    "YouTube 검색 결과를 이용해 예고편을 표시합니다."
)


# YouTube에서 예고편 검색
trailer, trailer_error = find_trailer(
    top_movie_name
)


# 예고편을 찾았을 때
if trailer:

    st.video(
        f"https://www.youtube.com/watch?v={trailer['video_id']}"
    )

    st.caption(
        f"영상: {trailer['title']}"
        + (
            f" · 채널: {trailer['channel']}"
            if trailer["channel"]
            else ""
        )
    )


# 예고편 검색에 실패했을 때
else:

    st.warning(
        "영화 예고편을 자동으로 불러오지 못했습니다."
    )

    st.info(trailer_error)

    st.markdown(
        f"💡 YouTube에서 **{top_movie_name} 예고편**을 "
        "직접 검색해 볼 수 있습니다."
    )


# ==================================================
# 15. 데이터 출처
# ==================================================

st.divider()

st.caption(
    f"데이터 출처: 영화진흥위원회(KOBIS) | "
    f"조회 기준일: {yesterday.strftime('%Y-%m-%d')}"
)
