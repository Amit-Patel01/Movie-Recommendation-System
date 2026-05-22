from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from config import MODEL_DIR
from ml.data_loader import load_movielens_frames
from services.database import get_db, init_db


def _content_text(row):
    return " ".join(
        [
            str(row.get("genres", "")).replace("|", " "),
            str(row.get("overview", "")),
            str(row.get("cast", "")),
            str(row.get("director", "")),
        ]
    ).strip()


def load_from_mongo():
    init_db()
    db = get_db()
    movies = pd.DataFrame(list(db["Movies"].find({}, {"_id": 0})))
    ratings = pd.DataFrame(list(db["Ratings"].find({}, {"_id": 0})))
    if movies.empty or ratings.empty:
        raise ValueError("MongoDB does not have enough Movies/Ratings data. Import MovieLens first.")
    return movies, ratings


def train_svd(ratings):
    from surprise import Dataset, Reader, SVD, accuracy
    from surprise.model_selection import train_test_split

    reader = Reader(rating_scale=(0.5, 5.0))
    data = Dataset.load_from_df(ratings[["userId", "movieId", "rating"]], reader)
    trainset, testset = train_test_split(data, test_size=0.2, random_state=42)
    model = SVD(n_factors=80, n_epochs=30, lr_all=0.005, reg_all=0.04, random_state=42)
    model.fit(trainset)
    predictions = model.test(testset)
    rmse = accuracy.rmse(predictions, verbose=False)
    full_trainset = data.build_full_trainset()
    model.fit(full_trainset)
    return model, rmse


def train_content_model(movies):
    movies = movies.copy()
    for column in ["genres", "overview", "cast", "director"]:
        if column not in movies.columns:
            movies[column] = ""
        movies[column] = movies[column].fillna("")
    movies["contentText"] = movies.apply(_content_text, axis=1)

    vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
    matrix = vectorizer.fit_transform(movies["contentText"])
    return {
        "vectorizer": vectorizer,
        "matrix": matrix,
        "movie_ids": movies["movieId"].astype(int).tolist(),
    }


def train(source="mongo", dataset_dir=None, metadata=None, model_dir=MODEL_DIR):
    if source == "mongo":
        movies, ratings = load_from_mongo()
    else:
        movies, ratings = load_movielens_frames(dataset_dir, metadata)

    ratings = ratings.rename(columns={"ratings": "rating"})
    ratings = ratings[["userId", "movieId", "rating"]].dropna()
    ratings["userId"] = ratings["userId"].astype(int)
    ratings["movieId"] = ratings["movieId"].astype(int)
    ratings["rating"] = ratings["rating"].astype(float)

    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    rmse = 0.0
    try:
        svd_model, rmse = train_svd(ratings)
        with open(model_dir / "svd_model.pkl", "wb") as file:
            pickle.dump(svd_model, file)
        print("SVD collaborative model trained successfully.")
    except Exception as e:
        print(f"Skipping SVD training (scikit-surprise might not be installed or compiled): {e}")

    content_model = train_content_model(movies)
    with open(model_dir / "content_model.pkl", "wb") as file:
        pickle.dump(content_model, file)
    with open(model_dir / "movie_lookup.pkl", "wb") as file:
        pickle.dump(movies.to_dict("records"), file)

    metrics = {
        "ratings": int(len(ratings)),
        "movies": int(len(movies)),
        "svd_rmse": float(rmse),
        "model_dir": str(model_dir.resolve()),
    }
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train MovieLens SVD and content recommendation models.")
    parser.add_argument("--source", choices=["mongo", "csv"], default="mongo")
    parser.add_argument("--dataset-dir", default="data/ml-latest-small")
    parser.add_argument("--metadata", default=None)
    parser.add_argument("--model-dir", default=str(MODEL_DIR))
    args = parser.parse_args()
    metrics = train(args.source, args.dataset_dir, args.metadata, args.model_dir)
    print("Training complete")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

