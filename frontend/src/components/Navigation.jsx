import {
  Clapperboard,
  Clock,
  Heart,
  LayoutDashboard,
  LogOut,
  Radio,
  Search,
  Settings,
  Sparkles,
  UserRound,
  X
} from "lucide-react";

const baseItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "recommendations", label: "Recommended", icon: Sparkles },
  { id: "search", label: "Search", icon: Search },
  { id: "live", label: "Live & Upcoming", icon: Radio, isLive: true },
  { id: "favorites", label: "Favorites", icon: Heart },
  { id: "history", label: "History", icon: Clock },
  { id: "profile", label: "Profile", icon: UserRound }
];

export default function Navigation({ active, setActive, user, onLogout, language, setLanguage, isOpen, onClose }) {
  const items = user?.role === "admin" ? [...baseItems, { id: "admin", label: "Admin", icon: Settings }] : baseItems;

  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? "open" : ""}`} onClick={onClose} />
      <aside className={`sidebar ${isOpen ? "open" : ""}`}>
        <button className="sidebar-close" onClick={onClose} title="Close Menu">
          <X size={20} />
        </button>

        <button className="brand" onClick={() => { setActive("dashboard"); onClose?.(); }} title="Dashboard">
          <span className="brand-mark">
            <Clapperboard size={20} />
          </span>
          <span>
            <strong>CineMind</strong>
          </span>
        </button>

        <nav>
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={active === item.id ? "nav-item active" : "nav-item"}
                onClick={() => { setActive(item.id); onClose?.(); }}
                title={item.label}
              >
                <Icon size={18} />
                <span>{item.label}</span>
                {item.isLive && <span className="live-badge-dot" />}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-lang-selector">
          <label className="sidebar-lang-label" htmlFor="lang-select">Language</label>
          <select
            id="lang-select"
            value={language || "en-US"}
            onChange={(e) => setLanguage(e.target.value)}
            className="sidebar-lang-select"
          >
            <option value="en-US">English (US)</option>
            <option value="hi-IN">हिन्दी (Hindi)</option>
            <option value="es-ES">Español (Spanish)</option>
            <option value="fr-FR">Français (French)</option>
            <option value="de-DE">Deutsch (German)</option>
            <option value="ja-JP">日本語 (Japanese)</option>
            <option value="ko-KR">한국어 (Korean)</option>
            <option value="ru-RU">Русский (Russian)</option>
          </select>
        </div>

        <div className="sidebar-user-container">
          <div className="sidebar-user">
            <div>
              <strong>{user?.name}</strong>
              <small>{user?.role}</small>
            </div>
            <button className="icon-button" onClick={() => { onLogout(); onClose?.(); }} title="Log out">
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
