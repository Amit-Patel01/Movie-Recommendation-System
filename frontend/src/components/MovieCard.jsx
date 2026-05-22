import { CalendarDays, Check, Eye, Heart, Send, Star, Sparkles } from "lucide-react";
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

export default function MovieCard({ movie, onRate, onFavorite, onWatch, onDetail, isFavorite = false, compact = false }) {
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

  const posterStyle = movie.posterUrl ? { backgroundImage: `url(${movie.posterUrl})` } : undefined;

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
  const badgeLabel = movie.type === "now_playing" ? "Now Playing" : movie.type === "upcoming" ? "Upcoming" : "TMDb";

  return (
    <article className={compact ? "movie-card compact" : "movie-card"}>
      <div 
        className={movie.posterUrl ? "poster image clickable" : "poster clickable"} 
        style={posterStyle}
        onClick={() => onDetail?.(movie)}
        title="View details"
      >
        {!movie.posterUrl && <span>{posterInitials(movie.title)}</span>}
        {movie.isLive && <span className={`movie-badge ${movie.type || "catalog"}`}>{badgeLabel}</span>}
      </div>
      <div className="movie-body">
        <div className="movie-title-row">
          <h3 onClick={() => onDetail?.(movie)} className="clickable-title" title="View details">{movie.title}</h3>
          {movie.predictedRating && (
            <span className="score" title="Predicted rating">
              <Star size={14} fill="currentColor" /> {movie.predictedRating}
            </span>
          )}
        </div>
        <p className="genres">{movie.genres || "Uncategorized"}</p>
        
        {releaseYear && (
          <div className="movie-meta">
            <CalendarDays size={14} />
            <span>{releaseYear}</span>
            {movie.release_date && <span>{movie.release_date}</span>}
          </div>
        )}

        {hasProviders && (
          <div className="watch-providers animate-fade-in">
            {providers.flatrate?.length > 0 && (
              <div className="provider-category">
                <span className="providers-label">Stream:</span>
                <div className="providers-list">
                  {providers.flatrate.slice(0, 3).map((p) => {
                    const ChipTag = providers.link ? "a" : "div";
                    const chipProps = providers.link ? {
                      href: providers.link,
                      target: "_blank",
                      rel: "noreferrer",
                      className: "provider-chip clickable"
                    } : {
                      className: "provider-chip"
                    };
                    return (
                      <ChipTag key={p.provider_name} {...chipProps} title={`Watch on ${p.provider_name}`}>
                        {p.logo_path ? (
                          <img 
                            src={`https://image.tmdb.org/t/p/w92${p.logo_path}`} 
                            alt={p.provider_name} 
                            className="provider-logo"
                            onError={(e) => { e.target.style.display = 'none'; }} 
                          />
                        ) : null}
                        <span className="provider-name">{p.provider_name}</span>
                      </ChipTag>
                    );
                  })}
                </div>
              </div>
            )}
            {!compact && providers.rent?.length > 0 && (
              <div className="provider-category">
                <span className="providers-label">Rent:</span>
                <div className="providers-list">
                  {providers.rent.slice(0, 2).map((p) => {
                    const ChipTag = providers.link ? "a" : "div";
                    const chipProps = providers.link ? {
                      href: providers.link,
                      target: "_blank",
                      rel: "noreferrer",
                      className: "provider-chip clickable"
                    } : {
                      className: "provider-chip"
                    };
                    return (
                      <ChipTag key={p.provider_name} {...chipProps} title={`Rent on ${p.provider_name}`}>
                        {p.logo_path ? (
                          <img 
                            src={`https://image.tmdb.org/t/p/w92${p.logo_path}`} 
                            alt={p.provider_name} 
                            className="provider-logo"
                            onError={(e) => { e.target.style.display = 'none'; }} 
                          />
                        ) : null}
                        <span className="provider-name">{p.provider_name}</span>
                      </ChipTag>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {movie.reason && <p className="reason">{movie.reason}</p>}

        {movie.predictedRating && !movie.isLive && !compact && (
          <div className="ai-explain-container">
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
              <div className="ai-explain-bubble animate-fade-in">
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

        {movie.overview && <p className="overview">{movie.overview}</p>}
        {(movie.cast || movie.director) && (
          <p className="credits">
            {movie.director && <span>Director: {movie.director}</span>}
            {movie.cast && <span>Cast: {movie.cast}</span>}
          </p>
        )}

        <div className="card-actions">
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
          <button className={isFavorite ? "favorite active" : "favorite"} onClick={() => onFavorite?.(movie)} title="Add to favorites">
            {isFavorite ? <Check size={15} /> : <Heart size={15} />}
            <span>{isFavorite ? "Saved" : "Save"}</span>
          </button>
          <button onClick={() => onWatch?.(movie)} title="Add to watch history">
            <Eye size={15} />
            <span>Watched</span>
          </button>
        </div>
      </div>
    </article>
  );
}
