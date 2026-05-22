const API_URL = import.meta.env.VITE_API_URL || "/api";

async function request(path, options = {}) {
  const token = localStorage.getItem("movieToken");
  const lang = localStorage.getItem("movieLang") || "en-US";
  const headers = {
    "Content-Type": "application/json",
    "Accept-Language": lang,
    ...(options.headers || {})
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || "Request failed");
  }
  return payload;
}

export const api = {
  register: (data) => request("/register", { method: "POST", body: JSON.stringify(data) }),
  login: (data) => request("/login", { method: "POST", body: JSON.stringify(data) }),
  profile: () => request("/profile"),
  movies: (search = "", limit = 40, semantic = false) =>
    request(`/movies?search=${encodeURIComponent(search)}&limit=${limit}&semantic=${semantic}`),
  recommend: (userId, topN = 12, mood = "") => request(`/recommend/${userId}?top_n=${topN}&mood=${encodeURIComponent(mood)}`),
  explain: (movieId) => request(`/movies/${movieId}/explain`),
  rateMovie: (movieId, rating) =>
    request("/rate_movie", { method: "POST", body: JSON.stringify({ movieId, rating }) }),
  watchMovie: (movieId) =>
    request("/watch_history", { method: "POST", body: JSON.stringify({ movieId }) }),
  favorites: (userId) => request(`/favorites/${userId}`),
  favoriteMovie: (movieId, action = "add") =>
    request("/favorite_movie", { method: "POST", body: JSON.stringify({ movieId, action }) }),
  watchHistory: (userId) => request(`/watch_history/${userId}`),
  adminUsers: () => request("/admin/users"),
  addMovie: (data) => request("/admin/movies", { method: "POST", body: JSON.stringify(data) }),
  updateMovie: (movieId, data) =>
    request(`/admin/movies/${movieId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteMovie: (movieId) => request(`/admin/movies/${movieId}`, { method: "DELETE" }),
  updateUser: (userId, data) =>
    request(`/admin/users/${userId}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteUser: (userId) => request(`/admin/users/${userId}`, { method: "DELETE" }),
  liveMovies: () => request("/movies/live"),
  importMovie: (tmdbId, metadata = {}) =>
    request("/movies/import", { method: "POST", body: JSON.stringify({ tmdbId, ...metadata }) }),
  getTMDbKey: () => request("/admin/tmdb_key"),
  setTMDbKey: (apiKey) =>
    request("/admin/tmdb_key", { method: "POST", body: JSON.stringify({ apiKey }) }),
  getWatchProviders: (tmdbId, movieId) =>
    request(`/movies/providers?tmdbId=${tmdbId || ""}&movieId=${movieId || ""}`)
};
