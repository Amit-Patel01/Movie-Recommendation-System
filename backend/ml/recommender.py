from __future__ import annotations

import json
import os
import pickle
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import MODEL_DIR


class HybridRecommender:
    def __init__(self, db, model_dir=MODEL_DIR):
        self.db = db
        self.model_dir = Path(model_dir)
        self.svd_model = None
        self.content_artifact = None
        self._load_artifacts()

    def _load_artifacts(self):
        svd_path = self.model_dir / "svd_model.pkl"
        content_path = self.model_dir / "content_model.pkl"
        if svd_path.exists():
            with open(svd_path, "rb") as file:
                self.svd_model = pickle.load(file)
        if content_path.exists():
            with open(content_path, "rb") as file:
                self.content_artifact = pickle.load(file)

    def refresh(self):
        self._load_artifacts()

    def _movies_df(self):
        movies = list(self.db["Movies"].find({}, {"_id": 0}))
        if not movies:
            return pd.DataFrame(columns=["movieId", "title", "genres", "overview", "cast", "director", "posterUrl"])
        df = pd.DataFrame(movies)
        for column in ["overview", "cast", "director", "posterUrl", "genres", "title"]:
            if column not in df.columns:
                df[column] = ""
            df[column] = df[column].fillna("")
        df["movieId"] = df["movieId"].astype(int)
        return df

    def _ratings_df(self):
        ratings = list(self.db["Ratings"].find({}, {"_id": 0}))
        if not ratings:
            return pd.DataFrame(columns=["userId", "movieId", "rating"])
        df = pd.DataFrame(ratings).rename(columns={"ratings": "rating"})
        df = df[["userId", "movieId", "rating"]].dropna()
        df["userId"] = df["userId"].astype(int)
        df["movieId"] = df["movieId"].astype(int)
        df["rating"] = df["rating"].astype(float)
        return df

    @staticmethod
    def _normalize(scores):
        if not scores:
            return {}
        values = np.array(list(scores.values()), dtype=float)
        min_value = float(values.min())
        max_value = float(values.max())
        if max_value == min_value:
            return {int(k): (1.0 if v > 0 else 0.0) for k, v in scores.items()}
        return {int(k): float((v - min_value) / (max_value - min_value)) for k, v in scores.items()}

    @staticmethod
    def _content_text(row):
        return " ".join(
            [
                str(row.get("genres", "")).replace("|", " "),
                str(row.get("overview", "")),
                str(row.get("cast", "")),
                str(row.get("director", "")),
            ]
        ).strip()

    def _popular_scores(self, ratings_df, candidate_ids):
        if ratings_df.empty:
            return {movie_id: 0.5 for movie_id in candidate_ids}
        global_mean = float(ratings_df["rating"].mean())
        grouped = ratings_df.groupby("movieId")["rating"].agg(["mean", "count"])
        scores = {}
        for movie_id in candidate_ids:
            if movie_id in grouped.index:
                row = grouped.loc[movie_id]
                weighted = (row["mean"] * row["count"] + global_mean * 5) / (row["count"] + 5)
                scores[int(movie_id)] = float(weighted)
            else:
                scores[int(movie_id)] = global_mean
        return scores

    def _svd_scores(self, user_id, candidate_ids):
        if self.svd_model is None:
            return {}
        scores = {}
        for movie_id in candidate_ids:
            try:
                scores[int(movie_id)] = float(self.svd_model.predict(str(user_id), str(movie_id)).est)
            except Exception:
                try:
                    scores[int(movie_id)] = float(self.svd_model.predict(user_id, movie_id).est)
                except Exception:
                    continue
        return scores

    def _user_user_scores(self, user_id, ratings_df, candidate_ids):
        if ratings_df.empty or user_id not in set(ratings_df["userId"]):
            return {}
        pivot = ratings_df.pivot_table(index="userId", columns="movieId", values="rating").fillna(0)
        if user_id not in pivot.index:
            return {}
        sims = cosine_similarity(pivot.loc[[user_id]], pivot)[0]
        sim_by_user = pd.Series(sims, index=pivot.index).drop(index=user_id, errors="ignore")
        sim_by_user = sim_by_user[sim_by_user > 0]
        if sim_by_user.empty:
            return {}

        scores = {}
        for movie_id in candidate_ids:
            if movie_id not in pivot.columns:
                continue
            ratings = pivot[movie_id]
            mask = ratings > 0
            useful_sims = sim_by_user[sim_by_user.index.isin(ratings[mask].index)]
            if useful_sims.empty:
                continue
            useful_ratings = ratings.loc[useful_sims.index]
            score = float(np.dot(useful_sims, useful_ratings) / useful_sims.sum())
            scores[int(movie_id)] = score
        return scores

    def _item_item_scores(self, user_id, ratings_df, candidate_ids):
        user_ratings = ratings_df[ratings_df["userId"] == user_id]
        if ratings_df.empty or user_ratings.empty:
            return {}
        pivot = ratings_df.pivot_table(index="movieId", columns="userId", values="rating").fillna(0)
        rated_ids = user_ratings["movieId"].astype(int).tolist()
        rated_ids = [movie_id for movie_id in rated_ids if movie_id in pivot.index]
        if not rated_ids:
            return {}

        scores = {}
        matrix = pivot.values
        movie_index = {int(movie_id): idx for idx, movie_id in enumerate(pivot.index)}
        for candidate_id in candidate_ids:
            if candidate_id not in movie_index:
                continue
            candidate_vector = matrix[movie_index[candidate_id]].reshape(1, -1)
            rated_vectors = matrix[[movie_index[movie_id] for movie_id in rated_ids]]
            sims = cosine_similarity(candidate_vector, rated_vectors)[0]
            positive = sims > 0
            if not positive.any():
                continue
            liked_ratings = user_ratings.set_index("movieId").loc[rated_ids, "rating"].values
            score = float(np.dot(sims[positive], liked_ratings[positive]) / sims[positive].sum())
            scores[int(candidate_id)] = score
        return scores

    def _content_scores(self, user_id, movies_df, ratings_df, candidate_ids):
        signals = set()
        liked = ratings_df[(ratings_df["userId"] == user_id) & (ratings_df["rating"] >= 3.5)]["movieId"].astype(int)
        signals.update(liked.tolist())
        signals.update(int(item["movieId"]) for item in self.db["WatchHistory"].find({"userId": user_id}, {"_id": 0, "movieId": 1}))
        user_doc = self.db["Users"].find_one({"userId": user_id}, {"favorites": 1})
        if user_doc:
            signals.update(int(movie_id) for movie_id in user_doc.get("favorites", []))
        signals = signals.intersection(set(movies_df["movieId"].astype(int)))
        if not signals or movies_df.empty:
            return {}

        working = movies_df.copy()
        working["contentText"] = working.apply(self._content_text, axis=1)
        vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
        matrix = vectorizer.fit_transform(working["contentText"])
        index_by_movie = {int(movie_id): idx for idx, movie_id in enumerate(working["movieId"])}
        signal_indices = [index_by_movie[movie_id] for movie_id in signals if movie_id in index_by_movie]
        if not signal_indices:
            return {}

        profile_vector = np.asarray(matrix[signal_indices].mean(axis=0))
        scores = {}
        for movie_id in candidate_ids:
            if movie_id not in index_by_movie:
                continue
            score = cosine_similarity(matrix[index_by_movie[movie_id]], profile_vector).ravel()[0]
            scores[int(movie_id)] = float(score)
        return scores

    def predict_rating(self, user_id, movie_id):
        svd = self._svd_scores(user_id, [movie_id])
        if svd:
            return round(float(svd[movie_id]), 2)
        ratings = self._ratings_df()
        if ratings.empty:
            return 3.5
        movie_ratings = ratings[ratings["movieId"] == movie_id]
        if not movie_ratings.empty:
            return round(float(movie_ratings["rating"].mean()), 2)
        return round(float(ratings["rating"].mean()), 2)

    def recommend(self, user_id, top_n=10):
        user_id = int(user_id)
        top_n = max(1, min(int(top_n), 50))
        movies_df = self._movies_df()
        ratings_df = self._ratings_df()
        if movies_df.empty:
            return []

        all_movie_ids = set(movies_df["movieId"].astype(int))
        rated_ids = set(ratings_df[ratings_df["userId"] == user_id]["movieId"].astype(int)) if not ratings_df.empty else set()
        watched_ids = set(
            int(item["movieId"]) for item in self.db["WatchHistory"].find({"userId": user_id}, {"_id": 0, "movieId": 1})
        )
        candidate_ids = sorted(all_movie_ids - rated_ids - watched_ids)
        if not candidate_ids:
            candidate_ids = sorted(all_movie_ids - rated_ids) or sorted(all_movie_ids)

        svd_scores = self._normalize(self._svd_scores(user_id, candidate_ids))
        user_scores = self._normalize(self._user_user_scores(user_id, ratings_df, candidate_ids))
        item_scores = self._normalize(self._item_item_scores(user_id, ratings_df, candidate_ids))
        content_scores = self._normalize(self._content_scores(user_id, movies_df, ratings_df, candidate_ids))
        popular_scores = self._normalize(self._popular_scores(ratings_df, candidate_ids))

        weights = {
            "matrix_factorization": 0.35 if svd_scores else 0.0,
            "user_user": 0.2,
            "item_item": 0.2,
            "content": 0.2,
            "popular": 0.05,
        }
        if not svd_scores:
            weights["user_user"] = 0.27
            weights["item_item"] = 0.27
            weights["content"] = 0.31
            weights["popular"] = 0.15

        rows = movies_df.set_index("movieId").to_dict("index")
        recommendations = []
        for movie_id in candidate_ids:
            score = (
                weights["matrix_factorization"] * svd_scores.get(movie_id, 0.0)
                + weights["user_user"] * user_scores.get(movie_id, 0.0)
                + weights["item_item"] * item_scores.get(movie_id, 0.0)
                + weights["content"] * content_scores.get(movie_id, 0.0)
                + weights["popular"] * popular_scores.get(movie_id, 0.0)
            )
            predicted = self.predict_rating(user_id, int(movie_id))
            movie = rows.get(movie_id, {})
            recommendations.append(
                {
                    "movieId": int(movie_id),
                    "title": movie.get("title", ""),
                    "genres": movie.get("genres", ""),
                    "overview": movie.get("overview", ""),
                    "cast": movie.get("cast", ""),
                    "director": movie.get("director", ""),
                    "posterUrl": movie.get("posterUrl", ""),
                    "hybridScore": round(float(score), 4),
                    "predictedRating": predicted,
                    "signals": {
                        "matrixFactorization": round(float(svd_scores.get(movie_id, 0.0)), 4),
                        "userUser": round(float(user_scores.get(movie_id, 0.0)), 4),
                        "itemItem": round(float(item_scores.get(movie_id, 0.0)), 4),
                        "content": round(float(content_scores.get(movie_id, 0.0)), 4),
                        "popular": round(float(popular_scores.get(movie_id, 0.0)), 4),
                    },
                    "reason": self._reason(movie_id, svd_scores, user_scores, item_scores, content_scores),
                }
            )

        recommendations.sort(key=lambda item: (item["hybridScore"], item["predictedRating"]), reverse=True)
        return recommendations[:top_n]

    @staticmethod
    def _reason(movie_id, svd_scores, user_scores, item_scores, content_scores):
        parts = []
        if svd_scores.get(movie_id, 0) > 0:
            parts.append("SVD predicted a strong fit")
        if user_scores.get(movie_id, 0) > 0:
            parts.append("similar users liked it")
        if item_scores.get(movie_id, 0) > 0:
            parts.append("it is close to movies you rated")
        if content_scores.get(movie_id, 0) > 0:
            parts.append("its genres/story/cast match your history")
        return ", ".join(parts[:2]) if parts else "popular with MovieLens users"

    def _call_gemini(self, prompt: str) -> str | None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 150
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=5) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"Gemini API error in recommender: {e}")
            return None

    def explain_recommendation(self, user_id, movie_id):
        movie = self.db["Movies"].find_one({"movieId": int(movie_id)})
        if not movie:
            return "Movie not found in our catalog."
        
        movie_title = movie.get("title", "this movie")
        movie_genres = movie.get("genres", "").replace("|", ", ")
        movie_overview = movie.get("overview", "")
        movie_director = movie.get("director", "")
        
        user_ratings = list(self.db["Ratings"].find({"userId": int(user_id)}).sort("rating", -1).limit(5))
        user_fav_doc = self.db["Users"].find_one({"userId": int(user_id)}, {"favorites": 1})
        user_favs = user_fav_doc.get("favorites", []) if user_fav_doc else []
        
        liked_movies_info = []
        if user_ratings:
            rated_movie_ids = [r["movieId"] for r in user_ratings]
            rated_movies = {m["movieId"]: m for m in self.db["Movies"].find({"movieId": {"$in": rated_movie_ids}})}
            for r in user_ratings:
                m_id = r["movieId"]
                if m_id in rated_movies:
                    liked_movies_info.append(f"'{rated_movies[m_id].get('title')}' (rated {r['rating']} stars)")
        
        fav_movies_info = []
        if user_favs:
            fav_movies = list(self.db["Movies"].find({"movieId": {"$in": [int(fid) for fid in user_favs]}}).limit(3))
            fav_movies_info = [f"'{m.get('title')}'" for m in fav_movies]
            
        prompt = (
            f"You are CineMind, a smart movie recommender AI. Explain in 1 or 2 conversational, warm, and highly engaging sentences "
            f"why the user would love to watch the movie '{movie_title}' (Genres: {movie_genres}. Director: {movie_director}. Summary: {movie_overview}).\n\n"
            f"Here is some context about the user's taste:\n"
        )
        if liked_movies_info:
            prompt += f"- They highly rated these movies: {', '.join(liked_movies_info[:3])}\n"
        if fav_movies_info:
            prompt += f"- They saved these as favorites: {', '.join(fav_movies_info)}\n"
        prompt += (
            "\nConnect the recommended movie's themes, director, or genres to their taste. Keep it short, and do NOT say 'based on your profile' or 'according to our database'."
        )
        
        explanation = self._call_gemini(prompt)
        if explanation:
            return explanation
            
        genres_list = [g.strip().lower() for g in movie.get("genres", "").split("|") if g.strip()]
        matched_movie = None
        matched_genre = None
        
        if user_ratings and genres_list:
            rated_movie_ids = [r["movieId"] for r in user_ratings if r["rating"] >= 4.0]
            rated_movies = list(self.db["Movies"].find({"movieId": {"$in": rated_movie_ids}}))
            for rm in rated_movies:
                rm_genres = [g.strip().lower() for g in rm.get("genres", "").split("|") if g.strip()]
                overlap = set(genres_list).intersection(set(rm_genres))
                if overlap:
                    matched_movie = rm.get("title")
                    matched_genre = list(overlap)[0].capitalize()
                    break
                    
        if matched_movie and matched_genre:
            return f"Since you loved '{matched_movie}', we highly recommend this movie as it features a similar blend of {matched_genre} elements that match your style."
        elif movie_genres:
            return f"This highly acclaimed film stands out in the {movie_genres} genre, offering a captivating story that aligns perfectly with what other film enthusiasts with your taste enjoy."
        else:
            return f"This popular title has been chosen for you because it has received high praise from similar viewers who share your rating patterns."

    def recommend_by_mood(self, user_id, mood, top_n=12):
        user_id = int(user_id)
        mood = str(mood).lower().strip()
        
        recs = self.recommend(user_id, top_n=60)
        if not recs:
            return []
            
        mood_genre_map = {
            "happy": ["comedy", "adventure", "family", "animation", "fantasy"],
            "sad": ["drama", "romance"],
            "adventurous": ["action", "adventure", "sci-fi", "fantasy", "thriller"],
            "thoughtful": ["mystery", "sci-fi", "crime", "documentary", "drama"],
            "thrilled": ["thriller", "horror", "action", "mystery"],
            "romantic": ["romance", "comedy", "drama"]
        }
        
        target_genres = mood_genre_map.get(mood, [])
        if not target_genres:
            return recs[:top_n]
            
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            candidates = recs[:20]
            candidates_data = [
                {"movieId": c["movieId"], "title": c["title"], "genres": c["genres"], "overview": c["overview"][:150]}
                for c in candidates
            ]
            prompt = (
                f"The user is feeling '{mood}'. Out of the following 20 movie recommendations curated for them, "
                f"select the top {top_n} movies that best match this mood. "
                f"For each selected movie, write a very short, cheerful mood-fit reason (max 10 words) like 'A fun watch to lift your spirits!'.\n\n"
                f"Candidate Movies JSON:\n{json.dumps(candidates_data)}\n\n"
                f"Respond ONLY with a valid JSON array of objects, containing 'movieId' and 'moodReason' fields. Do not include markdown code block syntax (like ```json), just the raw JSON."
            )
            response_text = self._call_gemini(prompt)
            if response_text:
                try:
                    clean_text = response_text.strip()
                    if clean_text.startswith("```"):
                        lines = clean_text.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines[-1].startswith("```"):
                            lines = lines[:-1]
                        clean_text = "\n".join(lines).strip()
                    
                    selections = json.loads(clean_text)
                    selection_map = {int(item["movieId"]): item["moodReason"] for item in selections}
                    
                    mood_recs = []
                    for r in recs:
                        m_id = r["movieId"]
                        if m_id in selection_map:
                            r["reason"] = f"Fits your {mood} mood: " + selection_map[m_id]
                            r["hybridScore"] += 0.2
                            mood_recs.append(r)
                            
                    if mood_recs:
                        mood_recs.sort(key=lambda x: (x["hybridScore"], x["predictedRating"]), reverse=True)
                        return mood_recs[:top_n]
                except Exception as e:
                    print(f"Failed to parse Gemini mood re-ranking: {e}")
        
        for r in recs:
            genres_list = [g.strip().lower() for g in r.get("genres", "").split("|") if g.strip()]
            match_count = sum(1 for g in genres_list if g in target_genres)
            if match_count > 0:
                boost = 0.3 * (match_count / len(target_genres))
                r["hybridScore"] += boost
                r["reason"] = f"Matches your {mood} mood (shares {match_count} genres)"
                
        recs.sort(key=lambda x: (x["hybridScore"], x["predictedRating"]), reverse=True)
        return recs[:top_n]

    def semantic_search(self, query, limit=20):
        query = str(query).strip()
        if not query:
            return []
            
        refined_query = query
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            prompt = (
                f"You are CineMind AI Search. The user is searching a movie catalog for: '{query}'. "
                f"Rewrite this query into a highly descriptive paragraph of keywords, genres, movie tropes, and synonyms "
                f"that will optimize TF-IDF search. Include synonyms for mood and tone. Do not write anything else, just the search expansion."
            )
            llm_refined = self._call_gemini(prompt)
            if llm_refined:
                refined_query = llm_refined
                
        if self.content_artifact is None:
            regex = {"$regex": query, "$options": "i"}
            mongo_query = {"$or": [{"title": regex}, {"genres": regex}, {"overview": regex}]}
            movies = list(self.db["Movies"].find(mongo_query).limit(limit))
            return [
                {
                    "movieId": m["movieId"],
                    "title": m["title"],
                    "genres": m["genres"],
                    "overview": m["overview"],
                    "cast": m["cast"],
                    "director": m["director"],
                    "posterUrl": m["posterUrl"],
                    "similarityScore": 0.5
                }
                for m in movies
            ]
            
        vectorizer = self.content_artifact["vectorizer"]
        matrix = self.content_artifact["matrix"]
        movie_ids = self.content_artifact["movie_ids"]
        
        query_vector = vectorizer.transform([refined_query])
        sims = cosine_similarity(query_vector, matrix).ravel()
        
        top_indices = np.argsort(sims)[::-1][:limit]
        
        movies_df = self._movies_df()
        if movies_df.empty:
            return []
            
        rows = movies_df.set_index("movieId").to_dict("index")
        matching = []
        
        for idx in top_indices:
            score = float(sims[idx])
            if score < 0.01:
                continue
            movie_id = int(movie_ids[idx])
            movie = rows.get(movie_id, {})
            if movie:
                matching.append({
                    "movieId": movie_id,
                    "title": movie.get("title", ""),
                    "genres": movie.get("genres", ""),
                    "overview": movie.get("overview", ""),
                    "cast": movie.get("cast", ""),
                    "director": movie.get("director", ""),
                    "posterUrl": movie.get("posterUrl", ""),
                    "similarityScore": round(score, 4)
                })
                
        if len(matching) < 5:
            existing_ids = {m["movieId"] for m in matching}
            regex = {"$regex": query, "$options": "i"}
            mongo_query = {"$or": [{"title": regex}, {"genres": regex}]}
            backup_movies = list(self.db["Movies"].find(mongo_query).limit(limit))
            for m in backup_movies:
                m_id = int(m["movieId"])
                if m_id not in existing_ids:
                    matching.append({
                        "movieId": m_id,
                        "title": m.get("title", ""),
                        "genres": m.get("genres", ""),
                        "overview": m.get("overview", ""),
                        "cast": m.get("cast", ""),
                        "director": m.get("director", ""),
                        "posterUrl": m.get("posterUrl", ""),
                        "similarityScore": 0.01
                    })
                    
        return matching[:limit]

