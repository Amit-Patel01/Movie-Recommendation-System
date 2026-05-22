# AI-Powered Movie Recommendation System

A premium, full-stack MovieLens recommendation application featuring a glassmorphic React frontend, Flask backend, MongoDB storage, JWT authentication, and a hybrid machine learning recommender engine.

## Key Features

- **Hybrid Recommendation Engine**: Blends matrix factorization (SVD), user-user collaborative filtering, item-item collaborative filtering, and content-based metadata (genres, overview, cast, director).
- **TMDb Live Integration**: Real-time syncing with The Movie Database (TMDb) to discover live theatrical, now-playing, and upcoming movies.
- **Interactive Movie Details Modal**: View comprehensive movie info (overview, cast, director, release date) and directly access streaming/rent provider links.
- **Watch Provider Routing**: Instant routing to streaming/rent options on platforms (Netflix, Prime Video, Apple TV, etc.) powered by TMDb watch providers.
- **Responsive Premium Layout**: Sleek dark-mode interface with adaptive grid controls on movie cards to prevent button truncation across all device sizes.

## Architecture

```text
Movie-Recommendation-System/
  backend/    Python Flask + MongoDB + Machine Learning Recommender
  frontend/   React JS + Vite (Tailored Vanilla CSS with glassmorphic design)
```

## Recommendation Engine

The backend combines multiple recommendation signals:

- Collaborative filtering, primary
  - User-user cosine similarity from live MongoDB ratings
  - Item-item cosine similarity from live MongoDB ratings
  - Matrix factorization using Surprise SVD
- Content-based filtering, secondary
  - Genre similarity
  - Movie overview similarity
  - Cast similarity
  - Director similarity
- Hybrid scoring
  - Blends SVD predictions, collaborative scores, content similarity, and popularity
  - Learns from user ratings, favorites, and watch history

## Backend Setup

Requirements:

- Python 3.10+
- MongoDB running locally on `mongodb://localhost:27017/`
- MovieLens dataset with `movies.csv` and `ratings.csv`

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put MovieLens small data here:

```text
backend/data/ml-latest-small/movies.csv
backend/data/ml-latest-small/ratings.csv
```

Import MovieLens into MongoDB:

```bash
python -m ml.data_loader --dataset-dir data/ml-latest-small --clear
```

Train Surprise SVD and content artifacts:

```bash
python -m ml.train_model --source mongo
```

Run Flask:

```bash
python app.py
```

Backend runs on:

```text
http://127.0.0.1:5000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on:

```text
http://localhost:5173
```

## Admin Login

Register a user with the invite code from `backend/.env`:

```text
ADMIN_INVITE_CODE=admin-setup-2026
```

That user can access the Admin panel to add, update, delete movies, and manage users.

## API Endpoints

Authentication:

- `POST /register`
- `POST /login`
- `GET /profile`

Movies and user activity:

- `GET /movies`
- `GET /movies/<movie_id>`
- `POST /rate_movie`
- `POST /watch_history`
- `GET /watch_history/<user_id>`
- `POST /favorite_movie`
- `GET /favorites/<user_id>`
- `GET /recommend/<user_id>`

Admin:

- `POST /admin/movies`
- `PUT /admin/movies/<movie_id>`
- `DELETE /admin/movies/<movie_id>`
- `GET /admin/users`
- `PATCH /admin/users/<user_id>`
- `DELETE /admin/users/<user_id>`

## MongoDB Collections

- `Users`
- `Movies`
- `Ratings`
- `WatchHistory`
- `Counters`

## Dataset Columns

MovieLens core files:

`movies.csv`

- `movieId`
- `title`
- `genres`

`ratings.csv`

- `userId`
- `movieId`
- `rating`
- `timestamp`

Optional metadata CSV for stronger content recommendations:

- `movieId`
- `overview`
- `cast`
- `director`
- `posterUrl`

Import it with:

```bash
python -m ml.data_loader --dataset-dir data/ml-latest-small --metadata data/movie_metadata.csv --clear
```

## ML Scripts

Train models:

```bash
python -m ml.train_model --source mongo
```

Train directly from CSV:

```bash
python -m ml.train_model --source csv --dataset-dir data/ml-latest-small
```

Generate CLI recommendations:

```bash
python -m ml.recommend 1 --top-n 10
```

## Notes

- `scikit-surprise` may require Microsoft C++ Build Tools on Windows if a prebuilt wheel is unavailable.
- Recommendations still work before SVD training using live user-user, item-item, content, and popularity signals.
- SVD improves after importing MovieLens and running `python -m ml.train_model --source mongo`.

