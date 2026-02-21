import { Link, NavLink } from 'react-router-dom';
import type { PropsWithChildren } from 'react';

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-root">
      <header className="top-nav">
        <Link className="brand" to="/">
          DirectorsCut
        </Link>
        <nav>
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/explore">Explore</NavLink>
        </nav>
      </header>
      <main className="page-container">{children}</main>
    </div>
  );
}
