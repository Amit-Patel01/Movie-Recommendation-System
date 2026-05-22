import { CalendarDays, Check, Eye, Heart, Send, Star, Sparkles, X, ExternalLink, Play } from "lucide-react";
import { useState, useEffect } from "react";
import { api } from "../api";

function posterInitials(title = "Movie") {
  return title
    .split(/[\s:()]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export default function MovieDetailModal({ movie, onClose, onRate, onFavorite, onWatch, isFavorite = false }) {
  const [rating, setRating] = useState("4");
  const [explanation, setExplanation] = useState("");
  const [fetchingExplain, setFetchingExplain] = useState(false);
  const [showExplain, setShowExplain] = useState(false);
  const [providers, setProviders] = useState(null);

  useEffect(() => {
    let active = true;
    async function loadProviders() {
      try {
        const data = await api.getWatchProviders(movie.tmdbId, movie.movieId);
        if (active && data && data.providers) {
          setProviders(data.providers);
        }
      } catch (err) {
        console.error("Failed to load providers:", err);
      }
    }
    loadProviders();
    return () => {
      active = false;
    };
  }, [movie.tmdbId, movie.movieId]);

  async function handleToggleExplain() {
    if (showExplain) {
      setShowExplain(false);
      return;
    }
    setShowExplain(true);
    if (!explanation) {
      setFetchingExplain(true);
      try {
        const payload = await api.explain(movie.movieId);
        setExplanation(payload.explanation || "No explanation available.");
      } catch (err) {
        setExplanation("Could not load AI explanation at this time.");
      } finally {
        setFetchingExplain(false);
      }
    }
  }

  const hasProviders = providers && (providers.flatrate?.length > 0 || providers.rent?.length > 0 || providers.buy?.length > 0);
  const releaseYear = movie.release_date ? movie.release_date.slice(0, 4) : "";
  const posterStyle = movie.posterUrl ? { backgroundImage: `url(${movie.posterUrl})` } : undefined;

  return (
    <div className="modal-backdrop animate-fade-in" onClick={onClose}>
      <div className="modal-content animate-slide-up" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose} title="Close details">
          <X size={20} />
        </button>

        <div className="modal-layout">
          {/* Left Column: Poster & Quick Action */}
          <div className="modal-poster-col">
            <div className={movie.posterUrl ? "modal-poster image" : "modal-poster"} style={posterStyle}>
              {!movie.posterUrl && <span>{posterInitials(movie.title)}</span>}
            </div>
            {providers?.link && (
              <a
                href={providers.link}
                target="_blank"
                rel="noreferrer"
                className="watch-now-btn"
              >
                <Play size={16} fill="currentColor" />
                <span>Watch on Platform</span>
                <ExternalLink size={14} />
              </a>
            )}
          </div>

          {/* Right Column: Information */}
          <div className="modal-info-col">
            <div className="modal-header-row">
              <h2>{movie.title}</h2>
              {movie.predictedRating && (
                <div className="modal-score" title="Predicted rating">
                  <Star size={16} fill="currentColor" />
                  <span>{movie.predictedRating}</span>
                </div>
              )}
            </div>

            <p className="modal-genres">{movie.genres || "Uncategorized"}</p>

            {movie.release_date && (
              <div className="modal-meta">
                <CalendarDays size={14} />
                <span>Released: {movie.release_date}</span>
              </div>
            )}

            {movie.overview && (
              <div className="modal-section">
                <h4>Overview</h4>
                <p className="modal-overview">{movie.overview}</p>
              </div>
            )}

            {(movie.director || movie.cast) && (
              <div className="modal-section modal-credits">
                {movie.director && (
                  <p>
                    <strong>Director:</strong> {movie.director}
                  </p>
                )}
                {movie.cast && (
                  <p>
                    <strong>Cast:</strong> {movie.cast}
                  </p>
                )}
              </div>
            )}

            {/* AI Insight */}
            {movie.predictedRating && !movie.isLive && (
              <div className="modal-section ai-insight-section">
                <button
                  type="button"
                  className={`ai-explain-btn ${showExplain ? "active" : ""}`}
                  onClick={handleToggleExplain}
                  disabled={fetchingExplain}
                >
                  <Sparkles size={12} className={fetchingExplain ? "spin" : ""} />
                  <span>{showExplain ? "Hide AI Insight" : "CineMind AI Insight"}</span>
                </button>
                {showExplain && (
                  <div className="ai-explain-bubble animate-fade-in" style={{ marginTop: '8px' }}>
                    {fetchingExplain ? (
                      <div className="ai-explain-loading">
                        <span className="pulse-dot"></span>
                        <span>Formulating insight...</span>
                      </div>
                    ) : (
                      <p>{explanation}</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Watch Providers */}
            {hasProviders && (
              <div className="modal-section providers-section">
                <h4>Where to Watch</h4>
                <div className="watch-providers-container">
                  {providers.flatrate?.length > 0 && (
                    <div className="provider-category">
                      <span className="providers-label">Stream:</span>
                      <div className="providers-list">
                        {providers.flatrate.map((p) => (
                          <a
                            key={p.provider_name}
                            href={providers.link}
                            target="_blank"
                            rel="noreferrer"
                            className="provider-chip clickable"
                            title={`Watch on ${p.provider_name}`}
                          >
                            {p.logo_path ? (
                              <img
                                src={`https://image.tmdb.org/t/p/w92${p.logo_path}`}
                                alt={p.provider_name}
                                className="provider-logo"
                                onError={(e) => { e.target.style.display = 'none'; }}
                              />
                            ) : null}
                            <span className="provider-name">{p.provider_name}</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {providers.rent?.length > 0 && (
                    <div className="provider-category">
                      <span className="providers-label">Rent:</span>
                      <div className="providers-list">
                        {providers.rent.map((p) => (
                          <a
                            key={p.provider_name}
                            href={providers.link}
                            target="_blank"
                            rel="noreferrer"
                            className="provider-chip clickable"
                            title={`Rent on ${p.provider_name}`}
                          >
                            {p.logo_path ? (
                              <img
                                src={`https://image.tmdb.org/t/p/w92${p.logo_path}`}
                                alt={p.provider_name}
                                className="provider-logo"
                                onError={(e) => { e.target.style.display = 'none'; }}
                              />
                            ) : null}
                            <span className="provider-name">{p.provider_name}</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {providers.buy?.length > 0 && (
                    <div className="provider-category">
                      <span className="providers-label">Buy:</span>
                      <div className="providers-list">
                        {providers.buy.map((p) => (
                          <a
                            key={p.provider_name}
                            href={providers.link}
                            target="_blank"
                            rel="noreferrer"
                            className="provider-chip clickable"
                            title={`Buy on ${p.provider_name}`}
                          >
                            {p.logo_path ? (
                              <img
                                src={`https://image.tmdb.org/t/p/w92${p.logo_path}`}
                                alt={p.provider_name}
                                className="provider-logo"
                                onError={(e) => { e.target.style.display = 'none'; }}
                              />
                            ) : null}
                            <span className="provider-name">{p.provider_name}</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Quick Actions (Rate, Save, Watched) */}
            <div className="modal-section modal-actions-section">
              <h4>Update Your Status</h4>
              <div className="card-actions modal-actions">
                <label className="rating-control" title="Choose rating">
                  <Star size={15} />
                  <select value={rating} onChange={(event) => setRating(event.target.value)}>
                    {["5", "4.5", "4", "3.5", "3", "2.5", "2", "1.5", "1", "0.5"].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <button onClick={() => onRate?.(movie, Number(rating))} title="Rate movie">
                  <Send size={15} />
                  <span>Rate</span>
                </button>
                <button
                  className={isFavorite ? "favorite active" : "favorite"}
                  onClick={() => onFavorite?.(movie)}
                  title="Add to favorites"
                >
                  {isFavorite ? <Check size={15} /> : <Heart size={15} />}
                  <span>{isFavorite ? "Saved" : "Save"}</span>
                </button>
                <button onClick={() => onWatch?.(movie)} title="Add to watch history">
                  <Eye size={15} />
                  <span>Watched</span>
                </button>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
