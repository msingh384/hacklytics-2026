import { Link, NavLink } from 'react-router-dom';
import type { PropsWithChildren } from 'react';
import { useSearch } from '../contexts/SearchContext';

export function AppShell({ children }: PropsWithChildren) {
  const { query, setQuery } = useSearch();

  return (
    <div className="app-root">
      <header className="top-nav top-nav--netflix">
        <div className="top-nav__left">
          <Link className="top-nav__brand" to="/">
            DirectorsCut
          </Link>
          <nav className="top-nav__nav">
            <NavLink to="/" end className="top-nav__link">
              Home
            </NavLink>
            <NavLink to="/explore" className="top-nav__link">
              Explore
            </NavLink>
          </nav>
        </div>

        <div className="top-nav__search-wrap">
          <input
            type="search"
            className="top-nav__search"
            placeholder="Search movies..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search movies"
          />
        </div>
      </header>
      <main className="main-content">{children}</main>
    </div>
  );
}
