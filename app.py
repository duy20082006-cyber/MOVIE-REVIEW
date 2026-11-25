import streamlit as st
import requests
import sqlite3
import pandas as pd
import re
import html
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote

# ============================================================
# MOVIE REVIEW - CINEMA DARK
# Data: StreamX keyless API (Cinemeta, IMDb suggestion, TVmaze, AniList)
# IMPORTANT: enrich=0 is used to avoid Wikidata/Wikipedia enrichment.
# Storage: SQLite
# ============================================================

st.set_page_config(
    page_title="Movie Review | Cinema Community",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "movie_reviews.db"
API_BASE = "https://api.streamx.qzz.io"
HEADERS = {
    "User-Agent": "MovieReviewCommunity/1.0 (Streamlit educational project)",
    "Accept": "application/json"
}

# -------------------- CSS --------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');
.stApp {background:#0D1420;color:#F4F6FA;font-family:'Be Vietnam Pro',sans-serif;}
[data-testid="stSidebar"] {background:#151E2C;border-right:1px solid #2D3A4E;}
.block-container {max-width:1280px;padding-top:1.7rem;padding-bottom:3rem;}
h1,h2,h3,h4,h5,h6 {color:#F2D38A !important;}
p, label, li, span {color:inherit;}
[data-testid="stMarkdownContainer"] p {color:#E3EAF4;}
[data-testid="stCaptionContainer"], .stCaption, small {color:#B9C6D8 !important;}
.stTextInput label, .stTextArea label, .stSelectbox label, .stSlider label {color:#F0DDAE !important;font-weight:600;}
[data-testid="stWidgetLabel"] p {color:#F0DDAE !important;}
.hero {background:linear-gradient(115deg,#1B2A40,#3A3028);border:1px solid #4C5360;border-radius:20px;padding:30px;margin-bottom:22px;}
.hero h1 {font-size:38px;margin:0;color:#F2D38A !important;}
.hero p {margin:8px 0 0;color:#D4DCE8;line-height:1.8;}
.section {font-size:22px;font-weight:800;color:#EBC978;margin:22px 0 12px;}
div[data-testid="stMetric"] {background:#182334;border:1px solid #334258;border-radius:15px;padding:16px;}
div[data-testid="stMetricValue"] {color:#EBC978;}
div[data-testid="stForm"] {background:#172233;border:1px solid #344258;border-radius:15px;padding:18px;}
/* Buttons: champagne primary with dark text; dark secondary with bright text */
.stButton > button[kind="primary"], .stFormSubmitButton > button {
    background:#EBC978 !important;
    color:#172233 !important;
    border:1px solid #F4DFA8 !important;
    border-radius:10px;
    font-weight:800;
    min-height:42px;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover {
    background:#F5DEA5 !important;
    color:#111827 !important;
    border-color:#FFF0C7 !important;
}
.stButton > button[kind="secondary"] {
    background:#223149 !important;
    color:#F4F7FC !important;
    border:1px solid #53647D !important;
    border-radius:10px;
    font-weight:700;
    min-height:42px;
}
.stButton > button[kind="secondary"]:hover {
    background:#30445F !important;
    color:#FFFFFF !important;
    border-color:#EBC978 !important;
}
.stTextInput input,.stTextArea textarea {background:#1A2638 !important;color:#FFFFFF !important;border:1px solid #65758D;border-radius:9px;}
.stTextInput input::placeholder,.stTextArea textarea::placeholder {color:#AAB8CA !important;opacity:1;}
.stSelectbox div[data-baseweb="select"] > div {background:#1A2638;color:#FFFFFF;border-color:#65758D;}
.stSlider [data-testid="stTickBar"] {color:#DCE5F1;}
[data-testid="stMetricLabel"] {color:#C8D4E3 !important;}
[data-testid="stMetricValue"] {color:#F2D38A !important;}
[data-testid="stAlert"] p {color:#263244 !important;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-color:#344258;border-radius:14px;background:#141E2C;}
a {color:#F2D38A !important;}
.muted {font-size:12px;color:#C0CCDA;}
[data-testid="stPlotlyChart"] {background:#111C2A;border:1px solid #34445B;border-radius:14px;padding:8px;}
[data-testid="stPlotlyChart"] * {font-family:'Be Vietnam Pro',sans-serif;}

.poster-placeholder {height:260px;background:linear-gradient(145deg,#1b2a40,#3a3028);border:1px solid #46536a;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:56px;}
</style>
""", unsafe_allow_html=True)

# -------------------- HTTP --------------------
@st.cache_data(ttl=900, show_spinner=False)
def api_get(path, params=None):
    url = API_BASE.rstrip("/") + "/" + path.lstrip("/")
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.json()

def first(dct, *keys, default=None):
    if not isinstance(dct, dict):
        return default
    for key in keys:
        value = dct.get(key)
        if value not in (None, "", [], {}):
            return value
    return default

def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", str(value))
    return html.unescape(re.sub(r"\s+", " ", value)).strip()

def listify(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return [value]

def normalize_search_item(item, default_type="movie", source="StreamX"):
    """Normalize IMDb/Cinemeta/AniList-like results to one app schema."""
    if not isinstance(item, dict):
        return None

    nested = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    data = {**item, **nested}

    imdb_id = first(data, "imdb_id", "imdbId", "imdb", "id")
    media_type = first(data, "type", "media_type", "mediaType", default=default_type)
    media_type = str(media_type).lower()
    if media_type in ("tv", "show", "series", "tvseries"):
        media_type = "series"
    elif media_type in ("anime",):
        media_type = "anime"
    else:
        media_type = "movie"

    title = first(data, "title", "name", "original_title", "originalTitle", default="Chưa có tên")
    year = first(data, "year", "release_year", "releaseYear", "released")
    if isinstance(year, str) and len(year) >= 4:
        year = year[:4]
    poster = first(data, "poster", "poster_url", "posterUrl", "image", "coverImage", "cover")
    background = first(data, "background", "backdrop", "backdrop_url", "backgroundUrl")
    if isinstance(poster, dict):
        poster = first(poster, "url", "large", "medium")
    if isinstance(background, dict):
        background = first(background, "url", "large", "medium")

    if isinstance(imdb_id, str) and not imdb_id.startswith("tt"):
        # IMDb search results can wrap the ID in a nested object.
        imdb_id = first(data, "imdbID", "tconst", default=imdb_id)

    return {
        "id": str(imdb_id or first(data, "slug", "id", default=f"{media_type}:{title}:{year}")),
        "imdb_id": str(imdb_id) if imdb_id else None,
        "type": media_type,
        "source": source,
        "title": str(title),
        "year": str(year) if year else "Chưa rõ",
        "poster": poster,
        "background": background,
        "overview": clean_text(first(data, "description", "overview", "plot", "summary", default="")),
        "rating": first(data, "imdbRating", "rating", "imdb_rating", "score", "averageScore"),
        "genres": listify(first(data, "genres", "genre", default=[])),
        "raw": data
    }

def unwrap_results(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("results", "metas", "items", "shows", "data", "titles"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for subkey in ("results", "metas", "items"):
                if isinstance(value.get(subkey), list):
                    return value[subkey]
    # Some endpoints return a single object
    if any(k in payload for k in ("title", "name", "imdb_id", "imdbId")):
        return [payload]
    return []

# -------------------- DATABASE --------------------
def db_connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    with db_connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_id TEXT NOT NULL,
                movie_name TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                reviewer TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 10),
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # Migrate older databases without deleting existing reviews.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()]
        migrations = {
            "source": "ALTER TABLE reviews ADD COLUMN source TEXT NOT NULL DEFAULT ''",
            "movie_name": "ALTER TABLE reviews ADD COLUMN movie_name TEXT NOT NULL DEFAULT ''"
        }
        for col, sql in migrations.items():
            if col not in cols:
                conn.execute(sql)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_movie ON reviews(movie_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(created_at)")

        # Hồ sơ hiển thị đơn giản (chưa phải hệ thống đăng nhập bảo mật).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                username TEXT PRIMARY KEY,
                bio TEXT NOT NULL DEFAULT '',
                favorite_genres TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL
            )
        """)

        # Watchlist: mỗi người dùng có danh sách riêng.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                movie_id TEXT NOT NULL,
                movie_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Muốn xem',
                created_at TEXT NOT NULL,
                UNIQUE(username, movie_id)
            )
        """)

        # Lưu danh mục phim đã tìm thấy để dùng cho gợi ý.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movie_catalog (
                movie_id TEXT PRIMARY KEY,
                movie_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()

init_db()

def save_review(movie_id, movie_name, source, reviewer, score, comment):
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO reviews(movie_id,movie_name,source,reviewer,score,comment,created_at)
            VALUES(?,?,?,?,?,?,?)
        """, (str(movie_id), movie_name, source, reviewer, int(score), comment, created))
        conn.commit()

def load_reviews(movie_id=None, limit=5000):
    with db_connect() as conn:
        if movie_id:
            return pd.read_sql_query(
                "SELECT * FROM reviews WHERE movie_id=? ORDER BY id DESC LIMIT ?",
                conn, params=(str(movie_id), limit)
            )
        return pd.read_sql_query(
            "SELECT * FROM reviews ORDER BY id DESC LIMIT ?",
            conn, params=(limit,)
        )


def save_profile(username, bio, favorite_genres):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO profiles(username,bio,favorite_genres,updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(username) DO UPDATE SET
                bio=excluded.bio,
                favorite_genres=excluded.favorite_genres,
                updated_at=excluded.updated_at
        """, (username, bio, json.dumps(favorite_genres, ensure_ascii=False), now))
        conn.commit()

def load_profile(username):
    with db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE username=?", (username,)
        ).fetchone()
    if not row:
        return {"bio": "", "favorite_genres": []}
    try:
        genres = json.loads(row["favorite_genres"] or "[]")
    except Exception:
        genres = []
    return {"bio": row["bio"], "favorite_genres": genres}

def save_movie_catalog(movies):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db_connect() as conn:
        for movie in movies:
            movie_id = str(movie.get("imdb_id") or movie.get("id"))
            conn.execute("""
                INSERT INTO movie_catalog(movie_id,movie_json,updated_at)
                VALUES(?,?,?)
                ON CONFLICT(movie_id) DO UPDATE SET
                    movie_json=excluded.movie_json,
                    updated_at=excluded.updated_at
            """, (movie_id, json.dumps(movie, ensure_ascii=False), now))
        conn.commit()

def add_to_watchlist(username, movie, status="Muốn xem"):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    movie_id = str(movie.get("imdb_id") or movie.get("id"))
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO watchlist(username,movie_id,movie_json,status,created_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(username,movie_id) DO UPDATE SET
                movie_json=excluded.movie_json,
                status=excluded.status
        """, (username, movie_id, json.dumps(movie, ensure_ascii=False), status, now))
        conn.commit()

def load_watchlist(username):
    with db_connect() as conn:
        rows = conn.execute("""
            SELECT * FROM watchlist WHERE username=?
            ORDER BY id DESC
        """, (username,)).fetchall()
    output = []
    for row in rows:
        try:
            movie = json.loads(row["movie_json"])
            movie["_watchlist_id"] = row["id"]
            movie["_watch_status"] = row["status"]
            output.append(movie)
        except Exception:
            continue
    return output

def update_watch_status(item_id, status):
    with db_connect() as conn:
        conn.execute("UPDATE watchlist SET status=? WHERE id=?", (status, item_id))
        conn.commit()

def remove_from_watchlist(item_id):
    with db_connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE id=?", (item_id,))
        conn.commit()

def get_recommendations(username, limit=20):
    """Gợi ý đơn giản từ thể loại yêu thích và phim đã chấm điểm cao."""
    profile = load_profile(username)
    preferred = set(profile["favorite_genres"])

    reviews = load_reviews(limit=5000)
    if not reviews.empty:
        mine = reviews[reviews["reviewer"].astype(str).str.casefold() == username.casefold()]
        # Tên phim/điểm được dùng để ưu tiên hồ sơ; thể loại lấy từ catalog nếu có.
        liked_ids = set(mine[mine["score"] >= 8]["movie_id"].astype(str))
    else:
        liked_ids = set()

    watch_items = load_watchlist(username)
    excluded = {
        str(item.get("imdb_id") or item.get("id"))
        for item in watch_items
    }
    candidates = []
    with db_connect() as conn:
        rows = conn.execute("SELECT movie_id,movie_json FROM movie_catalog").fetchall()

    for row in rows:
        try:
            movie = json.loads(row["movie_json"])
        except Exception:
            continue
        movie_id = str(movie.get("imdb_id") or movie.get("id"))
        if movie_id in excluded:
            continue
        genres = movie.get("genres") or []
        if genres and isinstance(genres[0], dict):
            genres = [g.get("name", "") for g in genres]
        genre_set = {str(g).casefold() for g in genres}
        overlap = len({g.casefold() for g in preferred} & genre_set)
        rating = movie.get("rating")
        try:
            rating_score = float(rating) if rating is not None else 0
        except (TypeError, ValueError):
            rating_score = 0
        score = overlap * 3 + (1 if rating_score >= 7 else 0)
        if score > 0:
            candidates.append((score, movie))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [movie for _, movie in candidates[:limit]]

# -------------------- SEARCH --------------------
@st.cache_data(ttl=600, show_spinner=False)
def search_movies(query, category):
    found = []
    errors = []

    # IMDb suggestion endpoint: broad title coverage and poster suggestions.
    try:
        payload = api_get("imdb/search", {"q": query})
        for raw in unwrap_results(payload):
            item = normalize_search_item(raw, "movie", "IMDb suggestion")
            if item:
                found.append(item)
    except Exception as exc:
        errors.append(f"IMDb search: {exc}")

    # Cinemeta search: movie and series catalogues.
    types = ["movie", "series"] if category == "Tất cả" else (
        ["movie"] if category == "Phim điện ảnh" else ["series"]
    )
    if category == "Anime":
        types = []
    for media_type in types:
        try:
            payload = api_get("search", {"q": query, "type": media_type})
            for raw in unwrap_results(payload):
                item = normalize_search_item(raw, media_type, "Cinemeta")
                if item:
                    found.append(item)
        except Exception as exc:
            errors.append(f"Cinemeta {media_type}: {exc}")

    # AniList-backed anime endpoint.
    if category in ("Tất cả", "Anime"):
        try:
            payload = api_get("anime/search", {"q": query})
            for raw in unwrap_results(payload):
                item = normalize_search_item(raw, "anime", "AniList")
                if item:
                    item["type"] = "anime"
                    found.append(item)
        except Exception as exc:
            errors.append(f"AniList: {exc}")

    # De-duplicate by stable IMDb id, otherwise normalized title/year/type.
    unique = {}
    for item in found:
        key = item["imdb_id"] or f'{item["type"]}:{item["title"].casefold()}:{item["year"]}'
        if key not in unique:
            unique[key] = item
        else:
            old = unique[key]
            for field in ("poster", "background", "overview", "rating", "imdb_id"):
                if not old.get(field) and item.get(field):
                    old[field] = item[field]

    return list(unique.values())[:40], errors

# -------------------- DETAILS --------------------
@st.cache_data(ttl=1800, show_spinner=False)
def get_details(movie):
    imdb_id = movie.get("imdb_id")
    media_type = movie.get("type", "movie")
    if not imdb_id or not str(imdb_id).startswith("tt"):
        return movie

    api_type = "series" if media_type in ("series", "anime") else "movie"
    payload = api_get(f"meta/{api_type}/{quote(str(imdb_id), safe='')}", {"enrich": "0"})

    meta = payload.get("meta", payload) if isinstance(payload, dict) else {}
    result = dict(movie)
    result["raw_detail"] = meta

    result["title"] = first(meta, "name", "title", default=movie["title"])
    result["overview"] = clean_text(first(meta, "description", "plot", "overview", "summary", default=movie.get("overview")))
    result["year"] = str(first(meta, "year", "releaseInfo", default=movie.get("year", "Chưa rõ")))
    result["poster"] = first(meta, "poster", default=movie.get("poster"))
    result["background"] = first(meta, "background", "backdrop", default=movie.get("background"))
    result["rating"] = first(meta, "imdbRating", "rating", default=movie.get("rating"))
    result["genres"] = listify(first(meta, "genres", default=movie.get("genres", [])))
    result["runtime"] = first(meta, "runtime", "runtimeMinutes")
    result["released"] = first(meta, "released", "releaseInfo", "release_date")
    result["director"] = first(meta, "director", "directors")
    result["cast"] = listify(first(meta, "cast", "actors", default=[]))
    result["writer"] = first(meta, "writer", "writers")
    result["country"] = first(meta, "country", "countries")
    result["videos"] = listify(first(meta, "videos", "trailers", default=[]))
    result["episodes"] = listify(first(meta, "videos", "episodes", default=[]))
    result["imdb_url"] = f"https://www.imdb.com/title/{imdb_id}/"
    return result

# -------------------- NAVIGATION STATE --------------------
for key, default in {
    "page": "Trang chủ",
    "previous_page": "Tìm kiếm phim",
    "selected_movie": None,
    "search_results": [],
    "last_query": "",
    "username": "Khach",
    "search_category": "Tất cả"
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

def select_movie(movie):
    # Lưu trang hiện tại để nút quay lại trở về đúng nơi người dùng vừa xem.
    current_page = st.session_state.get("page", "Tìm kiếm phim")
    if current_page != "Chi tiết phim":
        st.session_state.previous_page = current_page

    st.session_state.selected_movie = movie
    st.session_state.page = "Chi tiết phim"

def go_search():
    st.session_state.page = "Tìm kiếm phim"

def back_from_detail():
    previous = st.session_state.get("previous_page", "Tìm kiếm phim")
    if previous == "Chi tiết phim":
        previous = "Tìm kiếm phim"
    st.session_state.page = previous

def navigate(page_name):
    st.session_state.page = page_name

# -------------------- SIDEBAR --------------------
st.sidebar.markdown("## 🎬 MOVIE REVIEW")
st.sidebar.caption("Cinema Community")
st.sidebar.markdown("### TÀI KHOẢN")
st.sidebar.text_input("Tên hiển thị", key="username", help="Tên này dùng để gắn review, hồ sơ và watchlist. Đây chưa phải đăng nhập có mật khẩu.")
st.sidebar.markdown("### ĐIỀU HƯỚNG")
for page_name, page_icon in [
    ("Trang chủ", "🏠"),
    ("Tìm kiếm phim", "🔎"),
    ("Watchlist", "♡"),
    ("Gợi ý phim", "✨"),
    ("Hồ sơ cá nhân", "👤"),
    ("Chi tiết phim", "🎬"),
    ("Cộng đồng review", "💬")
]:
    st.sidebar.button(
        f"{page_icon}  {page_name}",
        key=f"nav_{page_name}",
        use_container_width=True,
        type="primary" if st.session_state.page == page_name else "secondary",
        on_click=navigate,
        args=(page_name,)
    )
st.sidebar.divider()
st.sidebar.markdown("### Nguồn dữ liệu")
st.sidebar.caption("StreamX · Cinemeta · IMDb suggestion · TVmaze · AniList")
st.sidebar.caption("Không cần API key")
st.sidebar.markdown("### Lưu ý")
st.sidebar.caption("Tên hiển thị chưa phải tài khoản bảo mật. Không dùng thông tin cá nhân nhạy cảm.")
st.sidebar.caption("Nguồn dữ liệu có thể thiếu poster hoặc thông tin ở một số phim.")

def render_dark_bar_chart(title, labels, values, colors, max_value=None, value_suffix=""):
    """Biểu đồ SVG tích hợp, không cần thư viện biểu đồ bên ngoài."""
    labels = [str(x) for x in labels]
    values = [float(v) for v in values]
    if not values:
        st.info("Chưa có dữ liệu để hiển thị biểu đồ.")
        return

    width, height = 1000, 360
    left, right, top, bottom = 62, 24, 34, 92
    plot_w, plot_h = width - left - right, height - top - bottom
    max_v = max(max_value if max_value is not None else max(values), 1)
    slot = plot_w / len(values)
    bar_w = min(58, slot * 0.62)

    parts = [
        '<div style="background:#111C2A;border:1px solid #344258;border-radius:14px;padding:10px 12px;overflow:hidden">',
        f'<div style="color:#F2D38A;font-weight:700;padding:5px 8px 10px">{html.escape(title)}</div>',
        f'<svg viewBox="0 0 {width} {height}" role="img" style="width:100%;height:auto;display:block;font-family:Arial,sans-serif">'
    ]

    for tick in range(6):
        val = max_v * tick / 5
        y = top + plot_h - (val / max_v) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#344258" stroke-width="1"/>')
        parts.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" fill="#D8E2EF" font-size="12">{val:g}</text>')

    for i, (label, value, color) in enumerate(zip(labels, values, colors)):
        xc = left + slot * (i + 0.5)
        bar_h = (value / max_v) * plot_h
        y = top + plot_h - bar_h
        x = xc - bar_w / 2
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(0,bar_h):.1f}" rx="6" fill="{color}" stroke="#F5E5B8" stroke-width="0.7"/>')
        parts.append(f'<text x="{xc:.1f}" y="{max(top+16,y-9):.1f}" text-anchor="middle" fill="#FFFFFF" font-size="13" font-weight="700">{value:g}{value_suffix}</text>')
        safe_label = html.escape(label[:24])
        ly = top + plot_h + 18
        parts.append(f'<text x="{xc:.1f}" y="{ly}" text-anchor="end" transform="rotate(-28 {xc:.1f} {ly})" fill="#E1E9F3" font-size="12">{safe_label}</text>')

    parts.append("</svg></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# -------------------- HOME --------------------
def render_hero():
    st.markdown("""
    <div class="hero">
      <div style="letter-spacing:2px;font-size:12px;font-weight:800;color:#EBC978">CINEMA COMMUNITY</div>
      <h1>Khám phá thế giới điện ảnh</h1>
      <p>Tìm kiếm phim, khám phá thông tin và chia sẻ đánh giá cùng cộng đồng yêu điện ảnh.</p>
    </div>
    """, unsafe_allow_html=True)

def render_movie_grid(movies, key_prefix="movie"):
    if not movies:
        st.info("Không tìm thấy phim phù hợp.")
        return
    cols_per_row = 5
    for start in range(0, len(movies), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, movie in zip(cols, movies[start:start+cols_per_row]):
            with col:
                with st.container(border=True):
                    poster = movie.get("poster")
                    if poster:
                        st.image(poster, use_container_width=True)
                    else:
                        st.markdown('<div class="poster-placeholder">🎬</div>', unsafe_allow_html=True)
                    title = movie.get("title", "Chưa có tên")
                    st.markdown(f"**{title[:55]}**")
                    st.caption(f'{movie.get("year","")} · {movie.get("type","").upper()}')
                    if st.button("Xem chi tiết", key=f"{key_prefix}_{movie['id']}_{start}", use_container_width=True):
                        select_movie(movie)
                        st.rerun()

if st.session_state.page == "Trang chủ":
    render_hero()
    st.markdown("### 🔎 Tìm phim nhanh")
    with st.form("home_search_form"):
        home_query = st.text_input("Nhập tên phim", placeholder="Ví dụ: Parasite, Mai, Squid Game, Naruto...")
        home_category = st.selectbox("Thể loại nội dung", ["Tất cả", "Phim điện ảnh", "Phim truyền hình", "Anime"])
        submitted = st.form_submit_button("Tìm kiếm")
    if submitted:
        if len(home_query.strip()) < 2:
            st.warning("Vui lòng nhập ít nhất 2 ký tự.")
        else:
            st.session_state.last_query = home_query.strip()
            st.session_state.search_category = home_category
            st.session_state.page = "Tìm kiếm phim"
            st.rerun()

    st.markdown("### ⭐ Khám phá phim")
    st.caption("Bạn có thể tìm phim theo tên ở ô tìm kiếm phía trên.")
    st.markdown("""
    <div class="muted">Movie Review sử dụng các nguồn dữ liệu công khai không yêu cầu API key. Dữ liệu và ảnh phụ thuộc vào khả năng cung cấp của từng nguồn.</div>
    """, unsafe_allow_html=True)

# -------------------- SEARCH PAGE --------------------
elif st.session_state.page == "Tìm kiếm phim":
    render_hero()
    st.markdown("### 🔎 Tìm kiếm phim")
    with st.form("search_form"):
        c1, c2 = st.columns([3, 1])
        with c1:
            query = st.text_input("Tên phim", value=st.session_state.last_query, placeholder="Nhập tên phim...")
        with c2:
            category = st.selectbox(
                "Danh mục",
                ["Tất cả", "Phim điện ảnh", "Phim truyền hình", "Anime"],
                index=["Tất cả", "Phim điện ảnh", "Phim truyền hình", "Anime"].index(
                    st.session_state.get("search_category", "Tất cả")
                )
            )
        do_search = st.form_submit_button("Tìm kiếm phim", use_container_width=True)

    if do_search:
        if len(query.strip()) < 2:
            st.warning("Nhập ít nhất 2 ký tự để tìm kiếm.")
        else:
            st.session_state.last_query = query.strip()
            st.session_state.search_category = category
            with st.spinner("Đang tìm kiếm từ các nguồn dữ liệu..."):
                results, errors = search_movies(query.strip(), category)
            st.session_state.search_results = results
            st.session_state.search_errors = errors
            if results:
                save_movie_catalog(results)

    results = st.session_state.search_results
    if st.session_state.last_query:
        st.markdown(f"### Kết quả cho: **{st.session_state.last_query}**")
    if results:
        st.caption(f"Tìm thấy {len(results)} kết quả")
        render_movie_grid(results, "search")
    elif st.session_state.last_query:
        st.info("Chưa có kết quả. Thử tên phim tiếng Anh hoặc tên gốc.")
    for err in st.session_state.get("search_errors", [])[:3]:
        st.caption(f"Nguồn tạm thời không phản hồi: {err}")

# -------------------- DETAIL PAGE --------------------
elif st.session_state.page == "Chi tiết phim":
    movie = st.session_state.selected_movie
    if not movie:
        st.info("Bạn chưa chọn phim. Hãy tìm kiếm và nhấn 'Xem chi tiết'.")
        if st.button("Đi đến tìm kiếm"):
            go_search()
            st.rerun()
    else:
        previous_page = st.session_state.get("previous_page", "Tìm kiếm phim")
        back_label = {
            "Trang chủ": "← Quay lại trang chủ",
            "Tìm kiếm phim": "← Quay lại kết quả tìm kiếm",
            "Cộng đồng review": "← Quay lại cộng đồng review"
        }.get(previous_page, "← Quay lại")

        if st.button(back_label, key="detail_back", use_container_width=False):
            back_from_detail()
            st.rerun()

        with st.spinner("Đang tải thông tin chi tiết..."):
            try:
                detail = get_details(movie)
            except Exception as exc:
                detail = movie
                st.warning(f"Không tải được toàn bộ thông tin chi tiết: {exc}")

        st.markdown(f"# {detail.get('title', movie['title'])}")
        watch_items = load_watchlist(st.session_state.username.strip() or "Khach")
        current_movie_key = str(movie.get("imdb_id") or movie.get("id"))
        already_saved = any(
            str(item.get("imdb_id") or item.get("id")) == current_movie_key
            for item in watch_items
        )
        if already_saved:
            st.success("Phim này đã có trong Watchlist của bạn.")
        elif st.button("♡ Thêm vào Watchlist", key="add_watchlist_detail", type="primary"):
            add_to_watchlist(st.session_state.username.strip() or "Khach", movie)
            st.success("Đã thêm phim vào Watchlist!")
            st.rerun()
        if detail.get("background"):
            st.image(detail["background"], use_container_width=True)

        left, right = st.columns([1, 2])
        with left:
            if detail.get("poster"):
                st.image(detail["poster"], use_container_width=True)
            else:
                st.markdown('<div class="poster-placeholder">🎬</div>', unsafe_allow_html=True)
                st.caption("Nguồn dữ liệu chưa cung cấp poster cho phim này.")
        with right:
            st.caption(f"Nguồn: {movie.get('source','StreamX')} · Loại: {movie.get('type','').upper()}")
            st.markdown(f"**Năm:** {detail.get('year','Chưa cập nhật')}")
            st.markdown(f"**Ngày phát hành:** {detail.get('released') or 'Chưa cập nhật'}")
            genres = detail.get("genres") or []
            if genres and isinstance(genres[0], dict):
                genres = [g.get("name", "") for g in genres]
            st.markdown(f"**Thể loại:** {', '.join(map(str, genres)) if genres else 'Chưa cập nhật'}")
            st.markdown(f"**Thời lượng:** {detail.get('runtime') or 'Chưa cập nhật'}")
            st.markdown(f"**Điểm tham khảo:** {detail.get('rating') or 'Chưa có dữ liệu'}")
            if detail.get("imdb_url"):
                st.markdown(f"[Xem trên IMDb]({detail['imdb_url']})")
            st.markdown("### Nội dung phim")
            st.write(detail.get("overview") or "Nguồn dữ liệu chưa có mô tả cho phim này.")

        st.markdown("### 🎭 Diễn viên")
        cast = detail.get("cast") or []
        if cast:
            cast_cols = st.columns(5)
            for i, person in enumerate(cast[:20]):
                with cast_cols[i % 5]:
                    if isinstance(person, dict):
                        pname = first(person, "name", "title", default="Chưa rõ")
                        character = first(person, "character", "role", default="")
                        pimage = first(person, "photo", "image", "avatar")
                        if pimage:
                            st.image(pimage, use_container_width=True)
                        st.markdown(f"**{pname}**")
                        if character:
                            st.caption(str(character))
                    else:
                        st.write(str(person))
        else:
            st.caption("Chưa có danh sách diễn viên từ nguồn dữ liệu.")

        videos = detail.get("videos") or []
        trailer_url = None
        for video in videos:
            if isinstance(video, dict):
                trailer_url = first(video, "trailer", "url", "link", "youtube")
                if trailer_url:
                    break
        st.markdown("### 🎞️ Trailer")
        if trailer_url:
            if "youtube.com" in trailer_url or "youtu.be" in trailer_url:
                st.video(trailer_url)
            else:
                st.markdown(f"[Mở trailer]({trailer_url})")
        else:
            st.caption("Chưa có trailer trong dữ liệu nguồn.")

        # Reviews
        movie_id = str(movie.get("imdb_id") or movie["id"])
        st.markdown("### ⭐ Đánh giá cộng đồng")
        reviews = load_reviews(movie_id)
        if not reviews.empty:
            avg = reviews["score"].mean()
            m1, m2, m3 = st.columns(3)
            m1.metric("Điểm trung bình", f"{avg:.1f}/10")
            m2.metric("Số lượt đánh giá", len(reviews))
            m3.metric("Điểm cao nhất", f"{reviews['score'].max()}/10")
            for _, row in reviews.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row['reviewer']}** · ⭐ {row['score']}/10")
                    st.write(row["comment"])
                    st.caption(row["created_at"])
        else:
            st.info("Phim này chưa có đánh giá. Hãy là người đầu tiên review!")

        with st.form("review_form", clear_on_submit=True):
            st.markdown("#### Viết đánh giá của bạn")
            reviewer = st.text_input("Tên hiển thị", placeholder="Ví dụ: Duy")
            score = st.slider("Bạn chấm phim bao nhiêu điểm?", 1, 10, 8)
            comment = st.text_area("Nhận xét", placeholder="Chia sẻ cảm nhận của bạn...")
            send = st.form_submit_button("Gửi đánh giá")
        if send:
            if not reviewer.strip() or not comment.strip():
                st.error("Vui lòng nhập tên và nội dung đánh giá.")
            else:
                try:
                    save_review(movie_id, detail.get("title", movie["title"]), movie.get("source", "StreamX"),
                                reviewer.strip(), score, comment.strip())
                    st.success("Đánh giá đã được lưu!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Không thể lưu đánh giá: {exc}")



# -------------------- WATCHLIST PAGE --------------------
elif st.session_state.page == "Watchlist":
    render_hero()
    username = st.session_state.username.strip() or "Khach"
    st.markdown("### ♡ Watchlist của bạn")
    items = load_watchlist(username)
    if not items:
        st.info("Watchlist đang trống. Hãy mở một bộ phim và chọn 'Thêm vào Watchlist'.")
    else:
        st.caption(f"{len(items)} phim trong danh sách của {username}")
        status_filter = st.selectbox(
            "Lọc trạng thái", ["Tất cả", "Muốn xem", "Đang xem", "Đã xem"],
            key="watchlist_filter"
        )
        shown = items if status_filter == "Tất cả" else [
            item for item in items if item.get("_watch_status") == status_filter
        ]
        for idx in range(0, len(shown), 4):
            cols = st.columns(4)
            for col, item in zip(cols, shown[idx:idx+4]):
                with col:
                    with st.container(border=True):
                        if item.get("poster"):
                            st.image(item["poster"], use_container_width=True)
                        else:
                            st.markdown('<div class="poster-placeholder">🎬</div>', unsafe_allow_html=True)
                        st.markdown(f"**{item.get('title','Chưa rõ')}**")
                        st.caption(f"{item.get('year','')} · {item.get('_watch_status','Muốn xem')}")
                        with st.popover("Quản lý"):
                            new_status = st.selectbox(
                                "Trạng thái",
                                ["Muốn xem", "Đang xem", "Đã xem"],
                                index=["Muốn xem", "Đang xem", "Đã xem"].index(item.get("_watch_status", "Muốn xem")),
                                key=f"watch_status_{item['_watchlist_id']}"
                            )
                            if st.button("Lưu trạng thái", key=f"save_watch_{item['_watchlist_id']}"):
                                update_watch_status(item["_watchlist_id"], new_status)
                                st.rerun()
                            if st.button("Xóa khỏi Watchlist", key=f"remove_watch_{item['_watchlist_id']}"):
                                remove_from_watchlist(item["_watchlist_id"])
                                st.rerun()
                        if st.button("Xem chi tiết", key=f"watch_detail_{item['_watchlist_id']}", use_container_width=True):
                            select_movie(item)
                            st.rerun()

# -------------------- RECOMMENDATIONS PAGE --------------------
elif st.session_state.page == "Gợi ý phim":
    render_hero()
    username = st.session_state.username.strip() or "Khach"
    st.markdown("### ✨ Gợi ý phim dành cho bạn")
    profile = load_profile(username)
    if not profile["favorite_genres"]:
        st.info("Hãy chọn thể loại yêu thích trong Hồ sơ cá nhân để nhận gợi ý phù hợp hơn.")
    recommendations = get_recommendations(username)
    if recommendations:
        st.caption("Gợi ý dựa trên thể loại yêu thích và dữ liệu phim đã được tìm kiếm trong ứng dụng.")
        render_movie_grid(recommendations, "recommend")
    else:
        st.info("Chưa đủ dữ liệu để gợi ý. Hãy chọn thể loại yêu thích và tìm kiếm thêm phim.")

# -------------------- PROFILE PAGE --------------------
elif st.session_state.page == "Hồ sơ cá nhân":
    render_hero()
    username = st.session_state.username.strip() or "Khach"
    st.markdown("### 👤 Hồ sơ cá nhân")
    profile = load_profile(username)
    with st.form("profile_form"):
        st.text_input("Tên hiển thị", value=username, disabled=True)
        bio = st.text_area("Giới thiệu", value=profile["bio"], placeholder="Một chút về gu điện ảnh của bạn...")
        genres = st.multiselect(
            "Thể loại yêu thích",
            ["Action", "Adventure", "Animation", "Comedy", "Crime", "Drama",
             "Fantasy", "Horror", "Mystery", "Romance", "Sci-Fi", "Thriller"],
            default=profile["favorite_genres"]
        )
        save_profile_button = st.form_submit_button("Lưu hồ sơ")
    if save_profile_button:
        save_profile(username, bio.strip(), genres)
        st.success("Đã lưu hồ sơ!")
        st.rerun()

    my_reviews = load_reviews(limit=5000)
    if not my_reviews.empty:
        my_reviews = my_reviews[
            my_reviews["reviewer"].astype(str).str.casefold() == username.casefold()
        ]
    else:
        my_reviews = pd.DataFrame()
    watch_items = load_watchlist(username)
    p1, p2, p3 = st.columns(3)
    p1.metric("Lượt đánh giá", len(my_reviews))
    p2.metric("Phim trong Watchlist", len(watch_items))
    p3.metric(
        "Điểm trung bình đã chấm",
        f"{my_reviews['score'].mean():.1f}/10" if not my_reviews.empty else "—"
    )
    st.markdown("#### 📝 Review gần đây")
    if my_reviews.empty:
        st.caption("Bạn chưa có đánh giá nào với tên hiển thị này.")
    else:
        for _, row in my_reviews.head(10).iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['movie_name']}** · ⭐ {row['score']}/10")
                st.write(row["comment"])
                st.caption(row["created_at"])

# -------------------- COMMUNITY PAGE --------------------
elif st.session_state.page == "Cộng đồng review":
    render_hero()
    st.markdown("### 💬 Đánh giá từ cộng đồng")
    all_reviews = load_reviews(limit=5000)
    if all_reviews.empty:
        st.info("Chưa có đánh giá nào. Hãy tìm một bộ phim và viết review đầu tiên!")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng đánh giá", len(all_reviews))
        c2.metric("Số phim được review", all_reviews["movie_id"].nunique())
        c3.metric("Điểm trung bình", f"{all_reviews['score'].mean():.1f}/10")

        movie_options = ["Tất cả phim"] + sorted(all_reviews["movie_name"].dropna().unique().tolist())
        selected_name = st.selectbox("Lọc theo phim", movie_options)
        filtered = all_reviews if selected_name == "Tất cả phim" else all_reviews[all_reviews["movie_name"] == selected_name]

        # Màu theo thang điểm: thấp -> đỏ, trung bình -> cam,
        # tốt -> xanh ngọc, xuất sắc -> vàng champagne.
        def score_color(value):
            if value <= 4:
                return "#D97777"
            if value <= 6:
                return "#E7A85B"
            if value <= 8:
                return "#4DB6AC"
            return "#EBC978"

        st.markdown("#### 📊 Phân phối điểm đánh giá")
        score_counts = (
            filtered["score"].value_counts().sort_index()
            .reindex(range(1, 11), fill_value=0)
        )
        score_labels = [f"{score}/10" for score in score_counts.index]
        score_values = score_counts.values.tolist()
        score_colors = [score_color(int(score)) for score in score_counts.index]

        render_dark_bar_chart(
            "Số lượt đánh giá theo mức điểm",
            score_labels, score_values, score_colors,
            max_value=max(score_values + [1])
        )

        st.markdown("#### 👥 Điểm đánh giá theo từng lượt")
        review_chart = filtered.reset_index(drop=True).copy()
        review_labels = [
            f"{str(row['reviewer'])[:14]} · Lượt {i+1}"
            for i, row in review_chart.iterrows()
        ]
        review_values = review_chart["score"].astype(int).tolist()
        review_colors = [score_color(v) for v in review_values]

        render_dark_bar_chart(
            "Điểm của từng lượt đánh giá",
            review_labels, review_values, review_colors,
            max_value=10, value_suffix="/10"
        )

        for _, row in filtered.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['movie_name']}** · ⭐ {row['score']}/10")
                st.write(f"{row['reviewer']}: {row['comment']}")
                st.caption(row["created_at"])

        csv_data = filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Xuất review CSV", csv_data, "movie_reviews.csv", "text/csv")

# -------------------- FOOTER --------------------
st.markdown("""
<div class="muted" style="text-align:center;padding:28px 0 8px">
Movie Review · Cinema Community<br>
Metadata by StreamX and its upstream providers. Images and metadata belong to their respective owners.
</div>
""", unsafe_allow_html=True)
