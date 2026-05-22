from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "movie_recommendation_system")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "admin-setup-2026")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
MODEL_DIR = BASE_DIR / "models"
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
