import {
  BrainCircuit,
  Compass,
  Film,
  Heart,
  History,
  Loader2,
  Radio,
  Search,
  ShieldCheck,
  Smile,
  Sparkles,
  Star,
  Zap,
  UserRound,
  Menu,
  Clapperboard
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import AdminPanel from "./components/AdminPanel";
import MovieCard from "./components/MovieCard";
import Navigation from "./components/Navigation";
import MovieDetailModal from "./components/MovieDetailModal";

function AuthScreen({ onAuth, notify }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "", inviteCode: "" });
  const [busy, setBusy] = useState(false);

  function setField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = mode === "login" ? await api.login(form) : await api.register(form);
      localStorage.setItem("movieToken", payload.token);
      onAuth(payload.user);
      notify(mode === "login" ? "Welcome back." : "Account created.");
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-copy">
          <div className="logo-lockup">
            <span className="brand-mark large">
              <BrainCircuit size={30} />
            </span>
            <span>CineMind</span>
          </div>
          <h1>AI movie recommendations that learn from ratings.</h1>
          <p>
            Live TMDb discovery with recommendations that adapt to your ratings, favorites, and watch history.
          </p>
          <div className="auth-metrics">
            <span>SVD</span>
            <span>User-user CF</span>
            <span>Item-item CF</span>
            <span>Content AI</span>
          </div>
        </div>

        <form className="auth-form" onSubmit={submit}>
          <div className="segmented">
            <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
              Login
            </button>
            <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>
              Register
            </button>
          </div>
          {mode === "register" && (
            <label>
              Name
              <input value={form.name} onChange={(event) => setField("name", event.target.value)} required />
            </label>
          )}
          <label>
            Email
            <input type="email" value={form.email} onChange={(event) => setField("email", event.target.value)} required />
          </label>
          <label>
            Password
            <input
              type="password"
              value={form.password}
              onChange={(event) => setField("password", event.target.value)}
              minLength="6"
              required
            />
          </label>
          {mode === "register" && (
            <label>
              Admin invite code
              <input value={form.inviteCode} onChange={(event) => setField("inviteCode", event.target.value)} placeholder="Optional" />
            </label>
          )}
          <button type="submit" disabled={busy}>
            {busy ? <Loader2 className="spin" size={17} /> : <UserRound size={17} />}
            <span>{mode === "login" ? "Login" : "Create Account"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="stat">
      <Icon size={19} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyState({ title, text }) {
  return (
    <div className="empty-state">
      <Film size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

const MOODS = [
  { id: "happy", label: "Happy", icon: Smile },
  { id: "sad", label: "Emotional", icon: Heart },
  { id: "adventurous", label: "Adventurous", icon: Compass },
  { id: "thoughtful", label: "Thoughtful", icon: BrainCircuit },
  { id: "thrilled", label: "Thrilled", icon: Zap },
  { id: "romantic", label: "Romantic", icon: Heart }
];

function MoodSelector({ activeMood, onChange }) {
  return (
    <div className="mood-selector-container animate-fade-in">
      <p className="mood-selector-title">How are you feeling today?</p>
      <div className="mood-chips">
        {MOODS.map((m) => {
          const Icon = m.icon;
          return (
            <button
              key={m.id}
              type="button"
              className={`mood-chip ${activeMood === m.id ? "active" : ""}`}
              onClick={() => onChange(m.id)}
            >
              <Icon size={16} />
              <span>{m.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [stats, setStats] = useState({ ratings: 0, watchHistory: 0 });
  const [view, setView] = useState("dashboard");
  const [movies, setMovies] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [history, setHistory] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState(null);
  const [mood, setMood] = useState("");
  const [liveMovies, setLiveMovies] = useState([]);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [liveTab, setLiveTab] = useState("now_playing");
  const [tmdbConfigured, setTmdbConfigured] = useState(false);
  const [maskedKey, setMaskedKey] = useState("");
  const [tmdbKeyInput, setTmdbKeyInput] = useState("");
  const [language, setLanguage] = useState(() => localStorage.getItem("movieLang") || "en-US");
  const [selectedMovie, setSelectedMovie] = useState(null);

  const favoriteIds = useMemo(() => new Set(favorites.map((movie) => movie.movieId)), [favorites]);

  const filteredLiveMovies = useMemo(() => {
    return liveMovies.filter((movie) => movie.type === liveTab);
  }, [liveMovies, liveTab]);

  function notify(message, type = "success") {
    setNotice({ message, type });
    window.clearTimeout(notify.timeout);
    notify.timeout = window.setTimeout(() => setNotice(null), 3200);
  }

  async function boot() {
    const token = localStorage.getItem("movieToken");
    if (!token) return;
    try {
      const payload = await api.profile();
      setUser(payload.user);
      setStats(payload.stats);
    } catch {
      localStorage.removeItem("movieToken");
      setUser(null);
    }
  }

  async function loadMovies(query = search, semantic = false) {
    setLoading(true);
    try {
      const payload = await api.movies(query, 40, semantic);
      setMovies(payload.movies || []);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function loadLiveMovies() {
    setLoading(true);
    try {
      const payload = await api.liveMovies();
      setLiveMovies(payload.movies || []);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function loadTMDbKeyStatus() {
    try {
      const res = await api.getTMDbKey();
      setTmdbConfigured(res.configured);
      if (res.configured) {
        setMaskedKey(res.maskedKey);
      } else {
        setMaskedKey("");
      }
    } catch (err) {
      console.error("Failed to load TMDb key status:", err);
    }
  }

  async function handleSaveTMDbKey(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await api.setTMDbKey(tmdbKeyInput);
      notify("TMDb API Key settings updated.");
      setTmdbKeyInput("");
      await loadTMDbKeyStatus();
      if (view === "live") {
        await loadLiveMovies();
      }
    } catch (error) {
      notify("Failed to update TMDb API Key: " + error.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function loadPersonalData(activeUser = user, currentMood = mood) {
    if (!activeUser) return;
    setLoading(true);
    try {
      const [recPayload, favPayload, historyPayload, profilePayload] = await Promise.all([
        api.recommend(activeUser.userId, 12, currentMood),
        api.favorites(activeUser.userId),
        api.watchHistory(activeUser.userId),
        api.profile()
      ]);
      setRecommendations(recPayload.recommendations || []);
      setFavorites(favPayload.favorites || []);
      setHistory(historyPayload.history || []);
      setStats(profilePayload.stats || { ratings: 0, watchHistory: 0 });
      setUser(profilePayload.user || activeUser);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleMoodChange(newMood) {
    const nextMood = mood === newMood ? "" : newMood;
    setMood(nextMood);
    setLoading(true);
    try {
      const recPayload = await api.recommend(user.userId, 12, nextMood);
      setRecommendations(recPayload.recommendations || []);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    boot();
  }, []);

  useEffect(() => {
    if (user) {
      localStorage.setItem("movieLang", language);
      loadPersonalData(user);
      loadMovies(search);
      loadLiveMovies();
    }
  }, [language, user?.userId]);

  useEffect(() => {
    if (user) {
      if (view === "live") {
        loadLiveMovies();
      }
      if (view === "profile") {
        loadTMDbKeyStatus();
      }
    }
  }, [view, user?.userId]);

  async function rateMovie(movieOrId, rating) {
    try {
      const resolvedId = (movieOrId && typeof movieOrId === "object") ? (movieOrId.movieId || movieOrId.tmdbId) : movieOrId;
      await api.rateMovie(resolvedId, rating);
      notify("Rating saved. Your next recommendations will adapt.");
      await loadPersonalData();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function favoriteMovie(movieOrId) {
    try {
      const resolvedId = (movieOrId && typeof movieOrId === "object") ? (movieOrId.movieId || movieOrId.tmdbId) : movieOrId;
      const action = favoriteIds.has(resolvedId) ? "remove" : "add";
      await api.favoriteMovie(resolvedId, action);
      notify(action === "add" ? "Added to favorites." : "Removed from favorites.");
      const payload = await api.favorites(user.userId);
      setFavorites(payload.favorites || []);
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function watchMovie(movieOrId) {
    try {
      const resolvedId = (movieOrId && typeof movieOrId === "object") ? (movieOrId.movieId || movieOrId.tmdbId) : movieOrId;
      await api.watchMovie(resolvedId);
      notify("Watch history updated.");
      await loadPersonalData();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  function logout() {
    localStorage.removeItem("movieToken");
    setUser(null);
    setView("dashboard");
  }

  if (!user) {
    return (
      <>
        {notice && <div className={`toast ${notice.type}`}>{notice.message}</div>}
        <AuthScreen onAuth={setUser} notify={notify} />
      </>
    );
  }

  const movieActions = {
    onRate: rateMovie,
    onFavorite: favoriteMovie,
    onWatch: watchMovie,
    onDetail: (movie) => setSelectedMovie(movie)
  };

  return (
    <div className="app-shell">
      <Navigation
        active={view}
        setActive={setView}
        user={user}
        onLogout={logout}
        language={language}
        setLanguage={setLanguage}
        isOpen={isMobileMenuOpen}
        onClose={() => setIsMobileMenuOpen(false)}
      />
      <main className="content">
        <header className="mobile-header">
          <button className="mobile-menu-btn" onClick={() => setIsMobileMenuOpen(true)} title="Open Menu">
            <Menu size={24} />
          </button>
          <div className="mobile-logo">
            <span className="brand-mark">
              <Clapperboard size={18} />
            </span>
            <span>CineMind</span>
          </div>
          <div style={{ width: 24 }}></div>
        </header>

        {notice && <div className={`toast ${notice.type}`}>{notice.message}</div>}

        {view === "dashboard" && (
          <section className="section-stack">
            <div className="top-band">
              <div>
                <p className="eyebrow">Personalized AI dashboard</p>
                <h1>Welcome, {user.name}</h1>
                <p>
                  Recommendations combine SVD matrix factorization, user-user filtering, item-item filtering, and content signals.
                </p>
              </div>
              <button onClick={() => loadPersonalData()} disabled={loading} title="Refresh recommendations">
                {loading ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
                <span>Refresh AI Picks</span>
              </button>
            </div>

            <MoodSelector activeMood={mood} onChange={handleMoodChange} />

            <div className="stats-grid">
              <Stat icon={Star} label="Ratings" value={stats.ratings} />
              <Stat icon={History} label="Watched" value={stats.watchHistory} />
              <Stat icon={Heart} label="Favorites" value={favorites.length} />
              <Stat icon={ShieldCheck} label="Role" value={user.role} />
            </div>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Top recommendations {mood && `(${mood} mood)`}</p>
                <h2>Movies matched to your taste</h2>
              </div>
              <button className="secondary" onClick={() => setView("recommendations")}>
                <Sparkles size={16} />
                <span>View All</span>
              </button>
            </div>
            <MovieGrid movies={recommendations.slice(0, 6)} actions={movieActions} favoriteIds={favoriteIds} emptyTitle="No recommendations yet" />
          </section>
        )}

        {view === "recommendations" && (
          <section className="section-stack">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Hybrid recommendation system {mood && `(${mood} mood)`}</p>
                <h1>Recommended movies</h1>
              </div>
              <button onClick={() => loadPersonalData()} disabled={loading}>
                {loading ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
                <span>Refresh</span>
              </button>
            </div>

            <MoodSelector activeMood={mood} onChange={handleMoodChange} />

            <MovieGrid movies={recommendations} actions={movieActions} favoriteIds={favoriteIds} emptyTitle="Rate or watch a few movies first" />
          </section>
        )}

        {view === "search" && (
          <section className="section-stack">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Global movie catalog</p>
                <h1>Search movies</h1>
              </div>
              <button className="secondary" onClick={() => loadMovies("", false)} disabled={loading}>
                {loading ? <Loader2 className="spin" size={16} /> : <Radio size={16} />}
                <span>Popular TMDb</span>
              </button>
            </div>
            <form
              className="search-bar"
              onSubmit={(event) => {
                event.preventDefault();
                loadMovies(search, false);
              }}
            >
              <Search size={18} />
              <input 
                value={search} 
                onChange={(event) => setSearch(event.target.value)} 
                placeholder="Search TMDb by movie title" 
              />
              <button type="submit">Search</button>
            </form>
            <MovieGrid movies={movies} actions={movieActions} favoriteIds={favoriteIds} emptyTitle="No movies found" />
          </section>
        )}

        {view === "favorites" && (
          <section className="section-stack">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Saved movies</p>
                <h1>Favorite list</h1>
              </div>
            </div>
            <MovieGrid movies={favorites} actions={movieActions} favoriteIds={favoriteIds} emptyTitle="No favorites yet" />
          </section>
        )}

        {view === "history" && (
          <section className="section-stack">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Behavior signals</p>
                <h1>Watch history</h1>
              </div>
            </div>
            {history.length === 0 ? (
              <EmptyState title="No watch history yet" text="Mark movies as watched so content-based recommendations get smarter." />
            ) : (
              <div className="history-list">
                {history.map((item) => (
                  <MovieCard
                    key={item.id || `${item.movieId}-${item.timestamp}`}
                    movie={item.movie}
                    {...movieActions}
                    isFavorite={favoriteIds.has(item.movie?.movieId || item.movie?.tmdbId)}
                    compact
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {view === "live" && (
          <section className="section-stack animate-fade-in">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Real-Time Theater & Releasing Catalog</p>
                <h1 className="live-heading">
                  <span>Live & Upcoming Movies</span>
                  <span className="live-badge-dot inline" />
                </h1>
              </div>
              
              <div className="search-mode-selector">
                <button
                  type="button"
                  className={`search-mode-btn ${liveTab === "now_playing" ? "active" : ""}`}
                  onClick={() => setLiveTab("now_playing")}
                >
                  Now Playing
                </button>
                <button
                  type="button"
                  className={`search-mode-btn ${liveTab === "upcoming" ? "active" : ""}`}
                  onClick={() => setLiveTab("upcoming")}
                >
                  Upcoming Releases
                </button>
              </div>
            </div>

            {loading && !liveMovies.length ? (
              <div className="empty-state">
                <Loader2 className="spin" size={28} />
                <h3>Fetching live catalog...</h3>
                <p>Contacting CineMind API and TMDb servers.</p>
              </div>
            ) : (
              <MovieGrid
                movies={filteredLiveMovies}
                actions={movieActions}
                favoriteIds={favoriteIds}
                emptyTitle={`No ${liveTab === "now_playing" ? "Now Playing" : "Upcoming"} movies available.`}
              />
            )}
          </section>
        )}

        {view === "profile" && (
          <section className="section-stack animate-fade-in">
            <div className="profile-panel">
              <span className="avatar">
                <UserRound size={34} />
              </span>
              <div>
                <p className="eyebrow">Profile</p>
                <h1>{user.name}</h1>
                <p>{user.email}</p>
              </div>
            </div>
            <div className="stats-grid">
              <Stat icon={Star} label="Ratings" value={stats.ratings} />
              <Stat icon={History} label="Watch history" value={stats.watchHistory} />
              <Stat icon={Heart} label="Favorites" value={favorites.length} />
              <Stat icon={ShieldCheck} label="Access" value={user.role} />
            </div>

            {user.role === "admin" && (
              <div className="admin-form tmdb-settings animate-fade-in">
                <h3>
                  <Radio size={18} />
                  <span>TMDb Live Integration Settings</span>
                </h3>
                <p>
                  CineMind uses The Movie Database (TMDb) for movie search, live releases, recommendations, posters, and provider data.
                </p>
                <form onSubmit={handleSaveTMDbKey} className="settings-form">
                  {tmdbConfigured ? (
                    <div className="connection-card">
                      <div>
                        <span>TMDB Live Connected</span>
                        <code>Key: {maskedKey}</code>
                      </div>
                      <button type="button" className="danger" onClick={async () => {
                        setLoading(true);
                        try {
                          await api.setTMDbKey("");
                          notify("TMDb API Key removed.");
                          await loadTMDbKeyStatus();
                        } catch (err) {
                          notify(err.message, "error");
                        } finally {
                          setLoading(false);
                        }
                      }}>
                        Disconnect Key
                      </button>
                    </div>
                  ) : (
                    <div className="settings-form">
                      <label>
                        <span>Enter TMDb API Key (v3 auth)</span>
                        <input
                          type="password"
                          placeholder="e.g. 8f2c3d..."
                          value={tmdbKeyInput}
                          onChange={(e) => setTmdbKeyInput(e.target.value)}
                          required
                        />
                      </label>
                      <div className="button-row">
                        <button type="submit" disabled={loading}>
                          Save API Key
                        </button>
                        <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noreferrer">
                          Get Key from TMDb
                        </a>
                      </div>
                    </div>
                  )}
                </form>
              </div>
            )}
          </section>
        )}

        {view === "admin" && user.role === "admin" && <AdminPanel notify={notify} />}
      </main>

      {selectedMovie && (
        <MovieDetailModal
          movie={selectedMovie}
          onClose={() => setSelectedMovie(null)}
          onRate={rateMovie}
          onFavorite={favoriteMovie}
          onWatch={watchMovie}
          isFavorite={favoriteIds.has(selectedMovie.movieId || selectedMovie.tmdbId)}
        />
      )}
    </div>
  );
}

function MovieGrid({ movies, actions, favoriteIds, emptyTitle }) {
  if (!movies?.length) {
    return <EmptyState title={emptyTitle} text="Explore live search results or refresh the feed." />;
  }
  return (
    <div className="movie-grid">
      {movies.map((movie) => (
        <MovieCard
          key={movie.movieId || movie.tmdbId}
          movie={movie}
          {...actions}
          isFavorite={favoriteIds?.has(movie.movieId || movie.tmdbId)}
        />
      ))}
    </div>
  );
}
