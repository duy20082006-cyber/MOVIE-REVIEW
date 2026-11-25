
import streamlit as st
import requests
import pandas as pd

# ==========================================
# 1. CẤU HÌNH TRANG
# ==========================================

st.set_page_config(
    page_title="Movie Review",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_URL = "https://image.tmdb.org/t/p/original"

# ==========================================
# 2. CSS GIAO DIỆN
# ==========================================

st.markdown("""
<style>

.stApp {
    background-color: #101014;
    color: white;
}

h1, h2, h3 {
    color: #F5C518 !important;
}

[data-testid="stSidebar"] {
    background-color: #1E1E26;
}

div.stButton > button {
    background-color: #F5C518;
    color: black;
    border-radius: 8px;
    font-weight: bold;
    border: none;
}

div.stButton > button:hover {
    background-color: #D9A900;
    color: black;
}

.movie-info {
    background-color: #202029;
    padding: 15px;
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. KHỞI TẠO SESSION STATE
# ==========================================

if "reviews" not in st.session_state:
    st.session_state.reviews = []

if "selected_movie_id" not in st.session_state:
    st.session_state.selected_movie_id = None

# ==========================================
# 4. KẾT NỐI TMDB API
# ==========================================

st.sidebar.title("🎬 MOVIE REVIEW")

st.sidebar.markdown("---")

api_key = st.sidebar.text_input(
    "TMDB API Key",
    type="password",
    placeholder="Nhập API Key tại đây"
)

st.sidebar.markdown(
    "[Lấy API Key miễn phí tại TMDB](https://www.themoviedb.org/settings/api)"
)

st.sidebar.markdown("---")

# ==========================================
# 5. HÀM TÌM KIẾM PHIM
# ==========================================

@st.cache_data(ttl=3600)
def search_movies(api_key, keyword):

    url = f"{API_URL}/search/movie"

    params = {
        "api_key": api_key,
        "query": keyword,
        "language": "vi-VN",
        "include_adult": False,
        "page": 1
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    return response.json()


# ==========================================
# 6. HÀM LẤY CHI TIẾT PHIM
# ==========================================

@st.cache_data(ttl=3600)
def get_movie_details(api_key, movie_id):

    url = f"{API_URL}/movie/{movie_id}"

    params = {
        "api_key": api_key,
        "language": "vi-VN",
        "append_to_response": "credits,videos"
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    return response.json()


# ==========================================
# 7. HÀM LẤY THÔNG TIN ĐẠO DIỄN
# ==========================================

def get_director(movie):

    crew = movie.get("credits", {}).get("crew", [])

    directors = [
        person["name"]
        for person in crew
        if person.get("job") == "Director"
    ]

    return ", ".join(directors) if directors else "Chưa cập nhật"


# ==========================================
# 8. HÀM LẤY DIỄN VIÊN
# ==========================================

def get_cast(movie):

    cast = movie.get("credits", {}).get("cast", [])

    return cast[:10]


# ==========================================
# 9. HÀM LẤY TRAILER
# ==========================================

def get_trailer(movie):

    videos = movie.get("videos", {}).get("results", [])

    for video in videos:

        if (
            video.get("site") == "YouTube"
            and video.get("type") == "Trailer"
            and video.get("official") is True
        ):
            return video.get("key")

    for video in videos:

        if (
            video.get("site") == "YouTube"
            and video.get("type") == "Trailer"
        ):
            return video.get("key")

    return None


# ==========================================
# 10. SIDEBAR MENU
# ==========================================

menu = st.sidebar.radio(
    "MENU",
    [
        "🏠 Trang chủ",
        "🔍 Tìm kiếm phim",
        "⭐ Đánh giá phim",
        "📊 Thống kê"
    ]
)

st.sidebar.markdown("---")

st.sidebar.caption(
    "MOVIE REVIEW - Discover, Watch & Review"
)

# ==========================================
# 11. TRANG CHỦ
# ==========================================

if menu == "🏠 Trang chủ":

    st.title("🎬 MOVIE REVIEW")

    st.subheader("Khám phá thế giới điện ảnh")

    st.write(
        "Tìm kiếm hàng triệu bộ phim, khám phá thông tin "
        "và chia sẻ cảm nhận điện ảnh của bạn."
    )

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "💬 Tổng lượt đánh giá",
        len(st.session_state.reviews)
    )

    if st.session_state.reviews:

        df = pd.DataFrame(st.session_state.reviews)

        average = df["score"].mean()

        col2.metric(
            "⭐ Điểm review trung bình",
            f"{average:.1f}/10"
        )

        col3.metric(
            "🎥 Số phim được review",
            df["movie_id"].nunique()
        )

    else:

        col2.metric("⭐ Điểm review trung bình", "Chưa có")
        col3.metric("🎥 Số phim được review", 0)

    st.markdown("---")

    st.header("🔥 BẮT ĐẦU KHÁM PHÁ")

    st.write(
        "Sử dụng chức năng Tìm kiếm phim để tra cứu "
        "bộ phim mà bạn yêu thích."
    )

    if st.button("🔍 KHÁM PHÁ PHIM NGAY"):

        st.session_state.go_search = True
        st.rerun()

    st.markdown("---")

    st.subheader("✨ Những tính năng nổi bật")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.write("🔍 **Tìm kiếm phim**")
        st.caption("Tra cứu phim theo tên.")

    with c2:
        st.write("⭐ **Đánh giá phim**")
        st.caption("Chấm điểm và viết nhận xét.")

    with c3:
        st.write("📊 **Thống kê**")
        st.caption("Theo dõi dữ liệu đánh giá.")

# ==========================================
# 12. TÌM KIẾM PHIM
# ==========================================

elif menu == "🔍 Tìm kiếm phim":

    st.title("🔍 TÌM KIẾM PHIM")

    st.write(
        "Nhập tên phim để hệ thống tự động tìm kiếm "
        "thông tin từ cơ sở dữ liệu TMDB."
    )

    if not api_key:

        st.warning(
            "Vui lòng nhập TMDB API Key ở thanh Sidebar "
            "để sử dụng chức năng tìm kiếm."
        )

    else:

        keyword = st.text_input(
            "Tên bộ phim",
            placeholder="Ví dụ: Interstellar, Avatar, Titanic..."
        )

        if len(keyword.strip()) >= 2:

            try:

                with st.spinner("🔍 Đang tìm kiếm phim..."):

                    data = search_movies(
                        api_key,
                        keyword.strip()
                    )

                results = data.get("results", [])

                if not results:

                    st.warning(
                        "Không tìm thấy bộ phim phù hợp!"
                    )

                else:

                    st.success(
                        f"Tìm thấy {len(results)} kết quả."
                    )

                    st.markdown("---")

                    # Chọn phim từ danh sách kết quả

                    selected = st.selectbox(
                        "🎬 Chọn bộ phim bạn muốn xem chi tiết",

                        results,

                        format_func=lambda movie: (
                            f"{movie.get('title', 'Unknown')} "
                            f"({movie.get('release_date', '')[:4] or 'Chưa rõ năm'})"
                        ),

                        index=0
                    )

                    # Lấy thông tin chi tiết

                    movie_id = selected["id"]

                    st.session_state.selected_movie_id = movie_id

                    with st.spinner("Đang tải thông tin chi tiết..."):

                        movie = get_movie_details(
                            api_key,
                            movie_id
                        )

                    # ==================================
                    # THÔNG TIN CHI TIẾT PHIM
                    # ==================================

                    st.markdown("---")

                    st.header(
                        f"🎬 {movie.get('title', 'Unknown')}"
                    )

                    if movie.get("original_title"):

                        st.caption(
                            f"Tên gốc: {movie['original_title']}"
                        )

                    col1, col2 = st.columns([1, 2])

                    with col1:

                        poster = movie.get("poster_path")

                        if poster:

                            st.image(
                                IMAGE_URL + poster,
                                use_container_width=True
                            )

                        else:

                            st.info("Phim chưa có poster.")

                    with col2:

                        st.subheader("📌 THÔNG TIN PHIM")

                        st.write(
                            f"⭐ Điểm TMDB: "
                            f"{movie.get('vote_average', 0):.1f}/10"
                        )

                        st.write(
                            f"👥 Số lượt bình chọn: "
                            f"{movie.get('vote_count', 0):,}"
                        )

                        st.write(
                            f"📅 Ngày phát hành: "
                            f"{movie.get('release_date') or 'Chưa cập nhật'}"
                        )

                        st.write(
                            f"⏱️ Thời lượng: "
                            f"{movie.get('runtime') or 'Chưa cập nhật'} phút"
                        )

                        genres = [
                            g["name"]
                            for g in movie.get("genres", [])
                        ]

                        st.write(
                            f"🎭 Thể loại: "
                            f"{', '.join(genres) if genres else 'Chưa cập nhật'}"
                        )

                        st.write(
                            f"🎬 Đạo diễn: {get_director(movie)}"
                        )

                        countries = [
                            c["name"]
                            for c in movie.get(
                                "production_countries", []
                            )
                        ]

                        st.write(
                            f"🌍 Quốc gia: "
                            f"{', '.join(countries) if countries else 'Chưa cập nhật'}"
                        )

                        languages = [
                            lang["english_name"]
                            for lang in movie.get(
                                "spoken_languages", []
                            )
                        ]

                        st.write(
                            f"🗣️ Ngôn ngữ: "
                            f"{', '.join(languages) if languages else 'Chưa cập nhật'}"
                        )

                        companies = [
                            company["name"]
                            for company in movie.get(
                                "production_companies", []
                            )
                        ]

                        st.write(
                            f"🏢 Hãng sản xuất: "
                            f"{', '.join(companies) if companies else 'Chưa cập nhật'}"
                        )

                    # ==================================
                    # NỘI DUNG PHIM
                    # ==================================

                    st.markdown("---")

                    st.subheader("📖 NỘI DUNG PHIM")

                    overview = movie.get("overview")

                    if overview:

                        st.write(overview)

                    else:

                        st.info(
                            "Chưa có nội dung mô tả bằng tiếng Việt."
                        )

                    # ==================================
                    # ẢNH BACKDROP
                    # ==================================

                    backdrop = movie.get("backdrop_path")

                    if backdrop:

                        st.markdown("---")

                        st.subheader("🖼️ HÌNH ẢNH PHIM")

                        st.image(
                            BACKDROP_URL + backdrop,
                            use_container_width=True
                        )

                    # ==================================
                    # DANH SÁCH DIỄN VIÊN
                    # ==================================

                    st.markdown("---")

                    st.subheader("🎭 DÀN DIỄN VIÊN")

                    cast = get_cast(movie)

                    if cast:

                        cast_cols = st.columns(5)

                        for i, actor in enumerate(cast):

                            with cast_cols[i % 5]:

                                if actor.get("profile_path"):

                                    st.image(
                                        IMAGE_URL + actor["profile_path"],
                                        use_container_width=True
                                    )

                                st.write(
                                    f"**{actor.get('name', 'Unknown')}**"
                                )

                                st.caption(
                                    actor.get(
                                        "character",
                                        "Chưa cập nhật"
                                    )
                                )

                    else:

                        st.info("Chưa có thông tin diễn viên.")

                    # ==================================
                    # TRAILER
                    # ==================================

                    st.markdown("---")

                    st.subheader("▶️ TRAILER PHIM")

                    trailer = get_trailer(movie)

                    if trailer:

                        st.video(
                            f"https://www.youtube.com/watch?v={trailer}"
                        )

                    else:

                        st.info(
                            "Chưa tìm thấy trailer chính thức."
                        )

                    # ==================================
                    # REVIEW NHANH
                    # ==================================

                    st.markdown("---")

                    st.subheader("⭐ ĐÁNH GIÁ BỘ PHIM NÀY")

                    if st.button(
                        "VIẾT ĐÁNH GIÁ PHIM",
                        use_container_width=True
                    ):

                        st.session_state.review_movie_id = movie_id
                        st.session_state.review_movie_name = movie.get("title")
                        st.session_state.open_review = True

                        st.rerun()

            except requests.exceptions.HTTPError as e:

                st.error(
                    f"API trả về lỗi: {e}. "
                    "Hãy kiểm tra API Key hoặc thử lại."
                )

            except requests.exceptions.RequestException:

                st.error(
                    "Không thể kết nối máy chủ. "
                    "Vui lòng kiểm tra Internet."
                )

            except Exception as e:

                st.error(f"Có lỗi xảy ra: {e}")

        elif keyword:

            st.info("Vui lòng nhập ít nhất 2 ký tự.")

        else:

            st.info(
                "Ví dụ: Nhập Avatar, Titanic, Inception, "
                "Interstellar hoặc tên phim bất kỳ."
            )

# ==========================================
# 13. ĐÁNH GIÁ PHIM
# ==========================================

elif menu == "⭐ Đánh giá phim":

    st.title("⭐ ĐÁNH GIÁ PHIM")

    if "open_review" in st.session_state and st.session_state.open_review:

        movie_name = st.session_state.review_movie_name
        movie_id = st.session_state.review_movie_id

        st.info(f"Bạn đang đánh giá phim: {movie_name}")

        reviewer = st.text_input(
            "Tên người đánh giá",
            placeholder="Nhập tên của bạn"
        )

        score = st.slider(
            "Điểm đánh giá",
            1,
            10,
            8
        )

        comment = st.text_area(
            "Nhận xét của bạn",
            placeholder="Chia sẻ cảm nhận về bộ phim...",
            height=150
        )

        if st.button(
            "📩 GỬI ĐÁNH GIÁ",
            use_container_width=True
        ):

            if not reviewer.strip() or not comment.strip():

                st.warning(
                    "Vui lòng nhập đầy đủ thông tin!"
                )

            else:

                st.session_state.reviews.append({
                    "reviewer": reviewer.strip(),
                    "movie_id": movie_id,
                    "movie": movie_name,
                    "score": score,
                    "comment": comment.strip()
                })

                st.session_state.open_review = False

                st.success(
                    "Đánh giá đã được gửi thành công!"
                )

                st.rerun()

    else:

        st.info(
            "Để đánh giá phim, hãy vào mục Tìm kiếm phim, "
            "chọn một bộ phim và nhấn Viết đánh giá phim."
        )

    st.markdown("---")

    st.subheader("💬 TẤT CẢ ĐÁNH GIÁ")

    if st.session_state.reviews:

        for review in reversed(st.session_state.reviews):

            with st.container(border=True):

                st.write(
                    f"🎬 **{review['movie']}**"
                )

                st.write(
                    f"👤 Người đánh giá: {review['reviewer']}"
                )

                st.write(
                    f"⭐ Điểm: {review['score']}/10"
                )

                st.write(review["comment"])

    else:

        st.info("Chưa có đánh giá nào.")

# ==========================================
# 14. THỐNG KÊ
# ==========================================

elif menu == "📊 Thống kê":

    st.title("📊 THỐNG KÊ ĐÁNH GIÁ")

    if st.session_state.reviews:

        df = pd.DataFrame(
            st.session_state.reviews
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Tổng lượt review",
            len(df)
        )

        col2.metric(
            "Điểm trung bình",
            f"{df['score'].mean():.2f}/10"
        )

        col3.metric(
            "Số phim được review",
            df["movie_id"].nunique()
        )

        st.markdown("---")

        st.subheader("⭐ ĐIỂM ĐÁNH GIÁ THEO PHIM")

        chart = (
            df.groupby("movie")["score"]
            .mean()
            .sort_values(ascending=False)
        )

        st.bar_chart(chart)

        st.markdown("---")

        st.subheader("📋 BẢNG DỮ LIỆU REVIEW")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "📥 TẢI DỮ LIỆU CSV",
            data=df.to_csv(
                index=False
            ).encode("utf-8-sig"),
            file_name="movie_reviews.csv",
            mime="text/csv"
        )

    else:

        st.info(
            "Chưa có dữ liệu để thống kê."
        )

# ==========================================
# 15. FOOTER
# ==========================================

st.markdown("---")

st.markdown(
    """
    <div style="text-align:center; color:gray;">
        🎬 MOVIE REVIEW <br>
        Discover - Watch - Review <br>
        Powered by TMDB API
    </div>
    """,
    unsafe_allow_html=True
)
