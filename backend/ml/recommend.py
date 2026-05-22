from __future__ import annotations

import argparse

from ml.recommender import HybridRecommender
from services.database import get_db, init_db


def main():
    parser = argparse.ArgumentParser(description="Generate hybrid recommendations for a user.")
    parser.add_argument("user_id", type=int)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    init_db()
    recommender = HybridRecommender(get_db())
    recommendations = recommender.recommend(args.user_id, args.top_n)
    for index, movie in enumerate(recommendations, start=1):
        print(
            f"{index}. {movie['title']} "
            f"(movieId={movie['movieId']}, predicted={movie['predictedRating']}, score={movie['hybridScore']})"
        )


if __name__ == "__main__":
    main()

