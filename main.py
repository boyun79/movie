import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 페이지 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일별 박스오피스")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 계산하기
# --------------------------------------------------
# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 서버의 현재 시간을 그대로 사용하지 않고 한국 시간(KST)을 지정합니다.

kst = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(kst).date()
yesterday = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

st.info(
    f"📅 조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} "
    "(한국 시간 기준)"
)


# --------------------------------------------------
# 3. KOBIS API에서 박스오피스 데이터 가져오기
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


def get_boxoffice():
    """KOBIS API에서 어제의 박스오피스 데이터를 가져옵니다."""

    # Streamlit Cloud의 Secrets에서 API 키를 읽습니다.
    # 실제 API 키를 코드에 직접 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return None, (
            "KOBIS_KEY를 찾을 수 없습니다. "
            "Streamlit Cloud의 앱 설정 → Secrets에 "
            "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
        )

    # API에 전달할 요청값입니다.
    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.Timeout:
        return None, (
            "KOBIS API 요청 시간이 초과되었습니다. "
            "잠시 후 다시 실행해 주세요."
        )

    except requests.exceptions.RequestException as e:
        return None, (
            f"KOBIS API에 접속하지 못했습니다.\n\n"
            f"오류 내용: {e}\n\n"
            "인터넷 연결이나 KOBIS API 서버 상태를 확인해 주세요."
        )

    except ValueError:
        return None, (
            "KOBIS API가 올바른 JSON 데이터를 반환하지 않았습니다. "
            "잠시 후 다시 실행해 주세요."
        )

    # --------------------------------------------------
    # 인증키가 잘못된 경우에도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    # --------------------------------------------------
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_code = fault_info.get("errorCode", "알 수 없음")
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

    # 정상적인 응답인지 확인합니다.
    try:
        movies = data["boxOfficeResult"]["dailyBoxOfficeList"]
    except (KeyError, TypeError):
        return None, (
            "KOBIS 응답에서 영화 목록을 찾을 수 없습니다.\n\n"
            "API 응답 구조가 변경되었거나 일시적인 오류일 수 있습니다."
        )

    # 영화 목록이 비어 있으면 사용자에게 확인할 내용을 알려줍니다.
    if not movies:
        return None, (
            "조회된 영화 목록이 없습니다.\n\n"
            "다음 내용을 확인해 주세요.\n"
            "1. 조회 날짜가 정상인지 확인하세요.\n"
            "2. KOBIS API가 해당 날짜의 데이터를 제공하는지 확인하세요.\n"
            "3. KOBIS API 서버가 정상적으로 응답하는지 확인하세요."
        )

    return movies, None


# --------------------------------------------------
# 4. API 실행
# --------------------------------------------------

movies, error_message = get_boxoffice()


# --------------------------------------------------
# 5. 오류가 발생한 경우 안내 화면 표시
# --------------------------------------------------

if error_message:
    st.error("박스오피스 데이터를 불러오지 못했습니다.")
    st.warning(error_message)

    st.stop()


# --------------------------------------------------
# 6. API 데이터를 표에 사용하기 좋은 형태로 변환
# --------------------------------------------------

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


# 혹시 API 응답은 있었지만 영화 데이터가 없는 경우도 다시 확인합니다.
if df.empty:
    st.error("표시할 영화 데이터가 없습니다.")
    st.info(
        "KOBIS API의 응답은 확인되었지만 영화 목록이 비어 있습니다. "
        "조회 날짜와 KOBIS API 상태를 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 7. 숫자 데이터를 보기 좋게 표시하기 위한 함수
# --------------------------------------------------

def format_number(value):
    """숫자에 천 단위 쉼표를 붙입니다."""
    return f"{value:,}"


# --------------------------------------------------
# 8. 1위 영화 정보
# --------------------------------------------------

first_movie = df.iloc[0]

st.subheader(f"🏆 1위: {first_movie['영화명']}")

# 지표 카드 세 개를 크게 보여줍니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "어제 관객수",
        f"{format_number(first_movie['관객수'])}명",
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{format_number(first_movie['누적관객'])}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{format_number(first_movie['스크린수'])}개",
    )


# --------------------------------------------------
# 9. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("📊 전체 박스오피스")

display_df = df.copy()

# 화면에서 숫자를 읽기 쉽게 천 단위 쉼표를 붙입니다.
display_df["관객수"] = display_df["관객수"].map(format_number)
display_df["누적관객"] = display_df["누적관객"].map(format_number)
display_df["스크린수"] = display_df["스크린수"].map(format_number)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# --------------------------------------------------
# 10. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("🎟️ 관객수 상위 5편")

top5 = (
    df.sort_values("관객수", ascending=False)
    .head(5)
    .copy()
)

# 영화명을 인덱스로 만들어 막대그래프를 그립니다.
chart_data = top5.set_index("영화명")[["관객수"]]

st.bar_chart(chart_data)


# --------------------------------------------------
# 11. 데이터 출처 표시
# --------------------------------------------------

st.caption(
    f"데이터 출처: 영화진흥위원회(KOBIS) | "
    f"조회 기준일: {yesterday.strftime('%Y-%m-%d')}"
)
