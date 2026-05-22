from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from services.database import get_db, init_db


MOVIE_COLUMNS = {"movieId", "title", "genres"}
RATING_COLUMNS = {"userId", "movieId", "rating", "timestamp"}


def _now():
    return datetime.now(timezone.utc)


def load_movielens_frames(dataset_dir: str | Path, metadata_path: str | Path | None = None):
    dataset_dir = Path(dataset_dir)
    movies_path = dataset_dir / "movies.csv"
    ratings_path = dataset_dir / "ratings.csv"

    if not movies_path.exists() or not ratings_path.exists():
        raise FileNotFoundError("Expected movies.csv and ratings.csv inside the MovieLens directory.")

    movies = pd.read_csv(movies_path)
    ratings = pd.read_csv(ratings_path)

    missing_movies = MOVIE_COLUMNS - set(movies.columns)
    missing_ratings = RATING_COLUMNS - set(ratings.columns)
    if missing_movies:
        raise ValueError(f"movies.csv is missing columns: {sorted(missing_movies)}")
    if missing_ratings:
        raise ValueError(f"ratings.csv is missing columns: {sorted(missing_ratings)}")

    movies = movies[["movieId", "title", "genres"]].copy()
    ratings = ratings[["userId", "movieId", "rating", "timestamp"]].copy()

    movies["movieId"] = movies["movieId"].astype(int)
    ratings["userId"] = ratings["userId"].astype(int)
    ratings["movieId"] = ratings["movieId"].astype(int)
    ratings["rating"] = ratings["rating"].astype(float)

    movies["overview"] = ""
    movies["cast"] = ""
    movies["director"] = ""
    movies["posterUrl"] = ""

    if metadata_path:
        metadata = pd.read_csv(metadata_path)
        keep = ["movieId", "overview", "cast", "director", "posterUrl"]
        available = [col for col in keep if col in metadata.columns]
        if "movieId" in available:
            metadata = metadata[available].copy()
            metadata["movieId"] = metadata["movieId"].astype(int)
            movies = movies.drop(columns=[col for col in available if col != "movieId"], errors="ignore")
            movies = movies.merge(metadata, on="movieId", how="left")

    for col in ["overview", "cast", "director", "posterUrl"]:
        if col not in movies.columns:
            movies[col] = ""
        movies[col] = movies[col].fillna("")

    return movies, ratings


def import_movielens_to_mongo(dataset_dir, metadata_path=None, clear=False):
    init_db()
    db = get_db()
    movies, ratings = load_movielens_frames(dataset_dir, metadata_path)

    if clear:
        db["Movies"].delete_many({})
        db["Ratings"].delete_many({})
        db["WatchHistory"].delete_many({})

    movie_ops = []
    for movie in movies.to_dict("records"):
        movie["updatedAt"] = _now()
        movie_ops.append(movie)
        db["Movies"].update_one({"movieId": int(movie["movieId"])}, {"$set": movie}, upsert=True)

    for rating in ratings.to_dict("records"):
        db["Ratings"].update_one(
            {"userId": int(rating["userId"]), "movieId": int(rating["movieId"])},
            {
                "$set": {
                    "userId": int(rating["userId"]),
                    "movieId": int(rating["movieId"]),
                    "rating": float(rating["rating"]),
                    "timestamp": int(rating["timestamp"]),
                    "updatedAt": _now(),
                }
            },
            upsert=True,
        )

    max_user = int(ratings["userId"].max()) if not ratings.empty else 100000
    max_movie = int(movies["movieId"].max()) if not movies.empty else 200000
    db["Counters"].update_one({"name": "userId"}, {"$max": {"value": max_user}}, upsert=True)
    db["Counters"].update_one({"name": "movieId"}, {"$max": {"value": max_movie}}, upsert=True)

    return {"movies": len(movies), "ratings": len(ratings)}


def main():
    parser = argparse.ArgumentParser(description="Import MovieLens CSV data into local MongoDB.")
    parser.add_argument("--dataset-dir", default="data/ml-latest-small")
    parser.add_argument("--metadata", default=None, help="Optional CSV with movieId, overview, cast, director, posterUrl.")
    parser.add_argument("--clear", action="store_true", help="Clear Movies, Ratings, and WatchHistory first.")
    args = parser.parse_args()
    result = import_movielens_to_mongo(args.dataset_dir, args.metadata, args.clear)
    print(f"Imported {result['movies']} movies and {result['ratings']} ratings.")


if __name__ == "__main__":
    main()
