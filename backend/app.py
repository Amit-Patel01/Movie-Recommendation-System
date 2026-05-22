from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from flask import Flask, has_request_context, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from config import ADMIN_INVITE_CODE, FRONTEND_ORIGIN, JWT_SECRET_KEY, TMDB_API_KEY
from ml.recommender import HybridRecommender
from services.database import get_db, get_next_sequence, init_db

import os
# Clear proxy environment variables to allow direct outbound connections
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(var, None)


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False
CORS(
    app,
    origins=[
        FRONTEND_ORIGIN,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        r"https://.*\.devtunnels\.ms",
    ],
    supports_credentials=True,
)
jwt = JWTManager(app)

db = init_db()
recommender = HybridRecommender(db)


TMDB_GENRE_MAP = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Children",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Musical",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "Drama",
    53: "Thriller",
    10752: "War",
    37: "Western"
}


def get_tmdb_api_key():
    setting = db["Settings"].find_one({"key": "tmdb_api_key"})
    saved_key = (setting or {}).get("value")
    return (saved_key or TMDB_API_KEY or "").strip()


def has_tmdb_api_key():
    return bool(get_tmdb_api_key())


def empty_watch_providers():
    return {"link": "", "flatrate": [], "rent": [], "buy": []}


def tmdb_genres_from_ids(genre_ids):
    genres = [TMDB_GENRE_MAP.get(gid) for gid in genre_ids or [] if gid in TMDB_GENRE_MAP]
    return "|".join(genres) if genres else "Drama"


def tmdb_poster_url(poster_path):
    return f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""


def tmdb_movie_payload(movie_data, movie_type=None):
    tmdb_id = movie_data.get("id")
    payload = {
        "tmdbId": tmdb_id,
        "movieId": tmdb_id,
        "title": movie_data.get("title") or movie_data.get("name") or "Untitled Movie",
        "genres": tmdb_genres_from_ids(movie_data.get("genre_ids")),
        "overview": movie_data.get("overview", ""),
        "posterUrl": tmdb_poster_url(movie_data.get("poster_path")),
        "release_date": movie_data.get("release_date", ""),
        "isLive": True,
    }
    if movie_type:
        payload["type"] = movie_type
    return payload


def fetch_tmdb_movie_list(endpoint, query_params=None, page=1, limit=40, movie_type=None):
    movies = []
    total_results = 0
    current_page = max(int(page), 1)
    max_items = max(1, min(int(limit), 100))

    while len(movies) < max_items:
        params = dict(query_params or {})
        params["page"] = current_page
        data = fetch_from_tmdb(endpoint, params)
        if not data or "results" not in data:
            return None

        total_results = data.get("total_results", total_results)
        movies.extend(tmdb_movie_payload(movie, movie_type) for movie in data.get("results", []))

        if current_page >= int(data.get("total_pages") or current_page):
            break
        current_page += 1

    return {"movies": movies[:max_items], "total": total_results}


def fetch_watch_providers_from_tmdb(tmdb_id):
    res = fetch_from_tmdb(f"/movie/{tmdb_id}/watch/providers")
    if not res or "results" not in res:
        return None
    results = res["results"]
    region_data = None
    if "IN" in results:
        region_data = results["IN"]
    elif "US" in results:
        region_data = results["US"]
    else:
        for r in results.values():
            region_data = r
            break
            
    if not region_data:
        return None
        
    return {
        "link": region_data.get("link", ""),
        "flatrate": region_data.get("flatrate", []),
        "rent": region_data.get("rent", []),
        "buy": region_data.get("buy", [])
    }


def fetch_from_tmdb(endpoint, query_params=None):
    api_key = get_tmdb_api_key()
    if not api_key:
        return None
    
    import urllib.parse
    import urllib.request
    import json
    
    lang = "en-US"
    try:
        if has_request_context():
            lang = request.args.get("language") or request.headers.get("Accept-Language", "en-US").split(",")[0]
            if len(lang) == 2:
                if lang == "hi": lang = "hi-IN"
                elif lang == "en": lang = "en-US"
                elif lang == "es": lang = "es-ES"
                elif lang == "fr": lang = "fr-FR"
                elif lang == "de": lang = "de-DE"
                elif lang == "ja": lang = "ja-JP"
                elif lang == "ko": lang = "ko-KR"
                elif lang == "zh": lang = "zh-CN"
                elif lang == "pt": lang = "pt-BR"
                elif lang == "it": lang = "it-IT"
                elif lang == "ru": lang = "ru-RU"
                else: lang = f"{lang}-{lang.upper()}"
    except Exception:
        pass

    params = {"api_key": api_key, "language": lang}
    if query_params:
        params.update(query_params)
        
    url = f"https://api.tmdb.org/3{endpoint}?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CineMind/1.0"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching from TMDB {endpoint}: {e}")
        return None


def utc_now():
    return datetime.now(timezone.utc)


def clean(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


def error(message, status=400):
    return jsonify({"message": message}), status


def current_user():
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return db["Users"].find_one({"userId": user_id})


def require_same_user_or_admin(user_id):
    user = current_user()
    if not user:
        return False
    return user.get("role") == "admin" or int(user.get("userId")) == int(user_id)


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("role") != "admin":
            return error("Admin access required.", 403)
        return fn(*args, **kwargs)

    return wrapper


def public_user(user):
    return clean(
        {
            "id": user.get("_id"),
            "userId": user.get("userId"),
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role", "user"),
            "favorites": user.get("favorites", []),
            "createdAt": user.get("createdAt"),
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "movie-recommendation-backend"})


@app.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    invite_code = data.get("inviteCode") or ""

    if not name or not email or not password:
        return error("Name, email, and password are required.")
    if len(password) < 6:
        return error("Password must be at least 6 characters.")
    if db["Users"].find_one({"email": email}):
        return error("Email already registered.", 409)

    role = "admin" if invite_code and invite_code == ADMIN_INVITE_CODE else "user"
    user = {
        "userId": get_next_sequence("userId", 100000),
        "name": name,
        "email": email,
        "passwordHash": generate_password_hash(password),
        "role": role,
        "favorites": [],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }
    db["Users"].insert_one(user)
    token = create_access_token(identity=str(user["userId"]))
    return jsonify({"token": token, "user": public_user(user)}), 201


@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = db["Users"].find_one({"email": email})
    if not user or not check_password_hash(user.get("passwordHash", ""), password):
        return error("Invalid email or password.", 401)
    token = create_access_token(identity=str(user["userId"]))
    return jsonify({"token": token, "user": public_user(user)})


@app.get("/profile")
@jwt_required()
def profile():
    user = current_user()
    if not user:
        return error("User not found.", 404)
    rating_count = db["Ratings"].count_documents({"userId": user["userId"]})
    watch_count = db["WatchHistory"].count_documents({"userId": user["userId"]})
    return jsonify({"user": public_user(user), "stats": {"ratings": rating_count, "watchHistory": watch_count}})


@app.get("/movies")
def list_movies():
    search = (request.args.get("search") or "").strip()
    limit = min(int(request.args.get("limit", 40)), 100)
    page = max(int(request.args.get("page", 1)), 1)

    if not has_tmdb_api_key():
        return error("TMDB API key is required to load movies.", 503)

    if search:
        tmdb_data = fetch_tmdb_movie_list("/search/movie", {"query": search}, page=page, limit=limit)
    else:
        tmdb_data = fetch_tmdb_movie_list("/movie/popular", page=page, limit=limit)

    if not tmdb_data:
        return error("Could not fetch movies from TMDB.", 502)

    return jsonify({"movies": clean(tmdb_data["movies"]), "total": tmdb_data["total"], "page": page, "limit": limit})


@app.get("/movies/providers")
def get_movie_providers():
    tmdb_id = request.args.get("tmdbId")
    movie_id = request.args.get("movieId")
    
    # Try to resolve tmdbId from movieId if tmdbId is not provided
    if not tmdb_id and movie_id:
        try:
            m = db["Movies"].find_one({"movieId": int(movie_id)})
            if m and "tmdbId" in m:
                tmdb_id = m["tmdbId"]
        except Exception:
            pass
            
    if tmdb_id:
        try:
            tmdb_id = int(tmdb_id)
        except ValueError:
            return error("Invalid tmdbId.")
            
    # Try fetching from TMDB if tmdb_id is available
    if tmdb_id:
        providers = fetch_watch_providers_from_tmdb(tmdb_id)
        return jsonify({"providers": providers or empty_watch_providers()})

    return jsonify({"providers": empty_watch_providers()})


@app.get("/movies/<int:movie_id>")
def get_movie(movie_id):
    movie = ensure_movie_cached(movie_id)
    if not movie:
        return error("Movie not found.", 404)
    return jsonify({"movie": clean(movie)})


@app.post("/rate_movie")
@jwt_required()
def rate_movie():
    user = current_user()
    data = request.get_json(silent=True) or {}
    movie_id = data.get("movieId")
    rating = data.get("rating")
    if not user:
        return error("User not found.", 404)
    if movie_id is None or rating is None:
        return error("movieId and rating are required.")
    try:
        movie_id = int(movie_id)
        rating = float(rating)
    except (TypeError, ValueError):
        return error("movieId must be an integer and rating must be numeric.")
    if rating < 0.5 or rating > 5:
        return error("Rating must be between 0.5 and 5.")
    if not ensure_movie_cached(movie_id):
        return error("Movie not found.", 404)

    db["Ratings"].update_one(
        {"userId": int(user["userId"]), "movieId": movie_id},
        {
            "$set": {
                "userId": int(user["userId"]),
                "movieId": movie_id,
                "rating": rating,
                "timestamp": int(utc_now().timestamp()),
                "updatedAt": utc_now(),
            }
        },
        upsert=True,
    )
    return jsonify({"message": "Rating saved.", "predictedRating": recommender.predict_rating(int(user["userId"]), movie_id)})


@app.post("/watch_history")
@jwt_required()
def add_watch_history():
    user = current_user()
    data = request.get_json(silent=True) or {}
    if not user:
        return error("User not found.", 404)
    try:
        movie_id = int(data.get("movieId"))
    except (TypeError, ValueError):
        return error("movieId is required.")
    if not ensure_movie_cached(movie_id):
        return error("Movie not found.", 404)
    db["WatchHistory"].insert_one({"userId": int(user["userId"]), "movieId": movie_id, "timestamp": utc_now()})
    return jsonify({"message": "Watch history updated."})


@app.get("/watch_history/<int:user_id>")
@jwt_required()
def get_watch_history(user_id):
    if not require_same_user_or_admin(user_id):
        return error("You cannot view this watch history.", 403)
    history = list(db["WatchHistory"].find({"userId": int(user_id)}).sort("timestamp", -1).limit(100))
    movie_ids = [item["movieId"] for item in history]
    for mid in movie_ids:
        ensure_movie_cached(mid)
    movies = {
        movie["movieId"]: movie
        for movie in db["Movies"].find(
            {"$or": [{"movieId": {"$in": movie_ids}, "tmdbId": {"$exists": True}}, {"tmdbId": {"$in": movie_ids}}]}
        )
    }
    enriched = []
    for item in history:
        movie = movies.get(item["movieId"], {})
        enriched.append({**clean(item), "movie": clean(movie)})
    return jsonify({"history": enriched})


@app.post("/favorite_movie")
@jwt_required()
def favorite_movie():
    user = current_user()
    data = request.get_json(silent=True) or {}
    if not user:
        return error("User not found.", 404)
    try:
        movie_id = int(data.get("movieId"))
    except (TypeError, ValueError):
        return error("movieId is required.")
    action = data.get("action", "add")
    if action == "remove":
        db["Users"].update_one({"userId": int(user["userId"])}, {"$pull": {"favorites": movie_id}})
    else:
        if not ensure_movie_cached(movie_id):
            return error("Movie not found.", 404)
        db["Users"].update_one({"userId": int(user["userId"])}, {"$addToSet": {"favorites": movie_id}})
    updated = db["Users"].find_one({"userId": int(user["userId"])})
    return jsonify({"message": "Favorites updated.", "favorites": updated.get("favorites", [])})


@app.get("/favorites/<int:user_id>")
@jwt_required()
def get_favorites(user_id):
    if not require_same_user_or_admin(user_id):
        return error("You cannot view these favorites.", 403)
    user = db["Users"].find_one({"userId": int(user_id)})
    favorite_ids = user.get("favorites", []) if user else []
    for fid in favorite_ids:
        ensure_movie_cached(fid)
    movies = list(
        db["Movies"].find(
            {"$or": [{"movieId": {"$in": favorite_ids}, "tmdbId": {"$exists": True}}, {"tmdbId": {"$in": favorite_ids}}]}
        )
    )
    return jsonify({"favorites": clean(movies)})


@app.get("/recommend/<int:user_id>")
@jwt_required()
def recommend(user_id):
    if not require_same_user_or_admin(user_id):
        return error("You cannot request recommendations for this user.", 403)
    top_n = max(1, min(int(request.args.get("top_n", 12)), 50))
    mood = request.args.get("mood", "").strip()

    if not has_tmdb_api_key():
        return error("TMDB API key is required to load recommendations.", 503)

    user_doc = db["Users"].find_one({"userId": int(user_id)})
    fav_movie_ids = user_doc.get("favorites", []) if user_doc else []
    ratings_cursor = db["Ratings"].find({"userId": int(user_id), "rating": {"$gte": 3.5}}).sort("timestamp", -1)
    rated_movie_ids = [r["movieId"] for r in ratings_cursor]

    combined_ids = []
    for movie_id in reversed(fav_movie_ids):
        if movie_id not in combined_ids:
            combined_ids.append(movie_id)
    for movie_id in rated_movie_ids:
        if movie_id not in combined_ids:
            combined_ids.append(movie_id)

    tmdb_map = {}
    if combined_ids:
        for movie in db["Movies"].find({"$or": [{"movieId": {"$in": combined_ids}}, {"tmdbId": {"$in": combined_ids}}]}):
            tmdb_id = movie.get("tmdbId") or movie.get("movieId")
            if tmdb_id:
                tmdb_map[movie.get("movieId")] = tmdb_id
                tmdb_map[tmdb_id] = tmdb_id

    source_tmdb_ids = [tmdb_map.get(mid, mid) for mid in combined_ids]
    recommendations = []
    seen_tmdb_ids = set(source_tmdb_ids)

    for source_tmdb_id in source_tmdb_ids[:3]:
        res = fetch_from_tmdb(f"/movie/{source_tmdb_id}/recommendations")
        if res and "results" in res:
            for movie_data in res["results"]:
                tid = movie_data.get("id")
                if tid and tid not in seen_tmdb_ids:
                    seen_tmdb_ids.add(tid)
                    item = tmdb_movie_payload(movie_data)
                    item["predictedRating"] = round(3.5 + (0.5 / (len(recommendations) + 1)), 2)
                    item["hybridScore"] = 0.8
                    recommendations.append(item)
                if len(recommendations) >= top_n * 2:
                    break

    if not recommendations:
        tmdb_data = fetch_tmdb_movie_list("/movie/popular", page=1, limit=max(top_n * 2, 20))
        if not tmdb_data:
            return error("Could not fetch recommendations from TMDB.", 502)
        recommendations = tmdb_data["movies"]
        for index, item in enumerate(recommendations):
            item["predictedRating"] = round(4.0 - min(index, 10) * 0.03, 2)
            item["hybridScore"] = round(0.7 - min(index, 10) * 0.01, 4)
            item["reason"] = "Popular on TMDB right now"

    if mood:
        mood_lower = mood.lower().strip()
        mood_genre_map = {
            "happy": ["comedy", "adventure", "children", "animation", "fantasy"],
            "sad": ["drama", "romance"],
            "adventurous": ["action", "adventure", "sci-fi", "fantasy", "thriller"],
            "thoughtful": ["mystery", "sci-fi", "crime", "documentary", "drama"],
            "thrilled": ["thriller", "horror", "action", "mystery"],
            "romantic": ["romance", "comedy", "drama"],
        }
        target_genres = mood_genre_map.get(mood_lower, [])
        if target_genres:
            filtered = []
            for item in recommendations:
                genres_list = [g.strip().lower() for g in item.get("genres", "").split("|") if g.strip()]
                match_count = sum(1 for genre in genres_list if genre in target_genres)
                if match_count > 0:
                    item["hybridScore"] = item.get("hybridScore", 0.7) + 0.2 * (match_count / len(target_genres))
                    item["reason"] = f"Matches your {mood_lower} mood"
                    filtered.append(item)
            if filtered:
                recommendations = filtered

    recommendations.sort(key=lambda item: (item.get("hybridScore", 0), item.get("predictedRating", 0)), reverse=True)
    return jsonify({"recommendations": clean(recommendations[:top_n])})


@app.get("/movies/<int:movie_id>/explain")
@jwt_required()
def explain_movie(movie_id):
    user = current_user()
    if not user:
        return error("User not found.", 404)
    explanation = recommender.explain_recommendation(user["userId"], movie_id)
    return jsonify({"explanation": explanation})


def import_movie_from_tmdb_id(tmdb_id):
    details = fetch_from_tmdb(f"/movie/{tmdb_id}")
    if not details:
        return None
    
    credits = fetch_from_tmdb(f"/movie/{tmdb_id}/credits") or {}
    
    genres_list = [g.get("name") for g in details.get("genres", []) if g.get("name")]
    # Map TMDB genre names to the labels already used in the UI.
    mapped_genres = []
    for g in genres_list:
        if g == "Science Fiction":
            mapped_genres.append("Sci-Fi")
        elif g == "Family":
            mapped_genres.append("Children")
        else:
            mapped_genres.append(g)
    genres_str = "|".join(mapped_genres) if mapped_genres else "Drama"
    
    director = ""
    crew = credits.get("crew", [])
    directors = [member.get("name") for member in crew if member.get("job") == "Director"]
    if directors:
        director = ", ".join(directors)
        
    cast_list = credits.get("cast", [])
    top_cast = [member.get("name") for member in cast_list[:5] if member.get("name")]
    cast_str = ", ".join(top_cast)
    
    poster_path = details.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
    
    return {
        "tmdbId": int(tmdb_id),
        "title": details.get("title", "Untitled Movie"),
        "genres": genres_str,
        "overview": details.get("overview", ""),
        "cast": cast_str,
        "director": director,
        "posterUrl": poster_url,
        "release_date": details.get("release_date", "")
    }


def ensure_movie_cached(movie_id):
    try:
        movie_id = int(movie_id)
    except (TypeError, ValueError):
        return None

    movie = db["Movies"].find_one({"tmdbId": movie_id}) or db["Movies"].find_one(
        {"movieId": movie_id, "tmdbId": {"$exists": True}}
    )
    if movie:
        return movie

    movie_info = import_movie_from_tmdb_id(movie_id)
    if movie_info:
        movie = {
            "movieId": movie_id,
            "tmdbId": movie_id,
            "title": movie_info["title"],
            "genres": movie_info["genres"],
            "overview": movie_info["overview"],
            "cast": movie_info.get("cast", ""),
            "director": movie_info.get("director", ""),
            "posterUrl": movie_info["posterUrl"],
            "release_date": movie_info.get("release_date", ""),
            "createdAt": utc_now(),
            "updatedAt": utc_now()
        }
        db["Movies"].replace_one({"movieId": movie_id}, movie, upsert=True)
        return movie

    return None


@app.get("/movies/live")
def get_live_movies():
    if not has_tmdb_api_key():
        return error("TMDB API key is required to load live movies.", 503)

    now_playing = fetch_tmdb_movie_list("/movie/now_playing", page=1, limit=40, movie_type="now_playing")
    upcoming = fetch_tmdb_movie_list("/movie/upcoming", page=1, limit=40, movie_type="upcoming")

    if not now_playing and not upcoming:
        return error("Could not fetch live movies from TMDB.", 502)

    movies = []
    if now_playing:
        movies.extend(now_playing["movies"])
    if upcoming:
        movies.extend(upcoming["movies"])

    return jsonify({"movies": clean(movies)})


@app.post("/movies/import")
@jwt_required()
def import_movie():
    user = current_user()
    if not user:
        return error("User not found.", 404)
        
    data = request.get_json(silent=True) or {}
    tmdb_id = data.get("tmdbId")
    if not tmdb_id:
        return error("tmdbId is required.")
        
    try:
        tmdb_id = int(tmdb_id)
    except (TypeError, ValueError):
        return error("tmdbId must be an integer.")
        
    existing = db["Movies"].find_one({"tmdbId": tmdb_id})
    if existing:
        return jsonify({"movieId": existing["movieId"], "message": "Movie already imported."})
        
    movie_info = import_movie_from_tmdb_id(tmdb_id)
    
    if not movie_info:
        return error("Movie details not found on TMDB.", 404)
            
    movie_id = tmdb_id
    
    payload = {
        "movieId": movie_id,
        "tmdbId": movie_info["tmdbId"],
        "title": movie_info["title"],
        "genres": movie_info["genres"],
        "overview": movie_info["overview"],
        "cast": movie_info["cast"],
        "director": movie_info["director"],
        "posterUrl": movie_info["posterUrl"],
        "createdAt": utc_now(),
        "updatedAt": utc_now()
    }
    
    db["Movies"].replace_one({"movieId": movie_id}, payload, upsert=True)
    return jsonify({"movieId": movie_id, "message": "Movie imported successfully.", "movie": clean(payload)}), 201


@app.get("/admin/tmdb_key")
@jwt_required()
def get_tmdb_key_status():
    user = current_user()
    if not user:
        return error("User not found.", 404)
    val = get_tmdb_api_key()
    if val:
        masked = val[:4] + "*" * (len(val) - 8) + val[-4:] if len(val) > 8 else "****"
        return jsonify({"configured": True, "maskedKey": masked})
    return jsonify({"configured": False})


@app.post("/admin/tmdb_key")
@jwt_required()
def set_tmdb_key():
    user = current_user()
    if not user:
        return error("User not found.", 404)
    if user.get("role") != "admin":
        return error("Admin access required.", 403)
        
    data = request.get_json(silent=True) or {}
    key_value = data.get("apiKey", "").strip()
    
    if not key_value:
        db["Settings"].delete_one({"key": "tmdb_api_key"})
        message = "Saved TMDB API key removed successfully."
        if TMDB_API_KEY:
            message += " The environment TMDB_API_KEY is still active."
        return jsonify({"message": message})
        
    db["Settings"].update_one(
        {"key": "tmdb_api_key"},
        {"$set": {"value": key_value, "updatedAt": utc_now()}},
        upsert=True
    )
    return jsonify({"message": "TMDB API key configured successfully."})


@app.post("/admin/movies")
@admin_required
def admin_add_movie():
    return error("Manual local movie catalog is disabled. Import movies from TMDB instead.", 410)


@app.put("/admin/movies/<int:movie_id>")
@admin_required
def admin_update_movie(movie_id):
    return error("Manual local movie catalog is disabled. Refresh the movie from TMDB instead.", 410)


@app.delete("/admin/movies/<int:movie_id>")
@admin_required
def admin_delete_movie(movie_id):
    db["Movies"].delete_one({"movieId": int(movie_id)})
    db["Ratings"].delete_many({"movieId": int(movie_id)})
    db["WatchHistory"].delete_many({"movieId": int(movie_id)})
    db["Users"].update_many({}, {"$pull": {"favorites": int(movie_id)}})
    return jsonify({"message": "Movie deleted."})


@app.get("/admin/users")
@admin_required
def admin_users():
    users = list(db["Users"].find({}).sort("createdAt", -1))
    return jsonify({"users": [public_user(user) for user in users]})


@app.patch("/admin/users/<int:user_id>")
@admin_required
def admin_update_user(user_id):
    data = request.get_json(silent=True) or {}
    updates = {}
    if data.get("role") in {"user", "admin"}:
        updates["role"] = data["role"]
    if data.get("name"):
        updates["name"] = data["name"].strip()
    if not updates:
        return error("No valid fields to update.")
    updates["updatedAt"] = utc_now()
    db["Users"].update_one({"userId": int(user_id)}, {"$set": updates})
    user = db["Users"].find_one({"userId": int(user_id)})
    if not user:
        return error("User not found.", 404)
    return jsonify({"message": "User updated.", "user": public_user(user)})


@app.delete("/admin/users/<int:user_id>")
@admin_required
def admin_delete_user(user_id):
    db["Users"].delete_one({"userId": int(user_id)})
    db["Ratings"].delete_many({"userId": int(user_id)})
    db["WatchHistory"].delete_many({"userId": int(user_id)})
    return jsonify({"message": "User deleted."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
