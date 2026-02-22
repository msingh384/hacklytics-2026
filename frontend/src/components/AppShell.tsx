import { Link, NavLink } from 'react-router-dom';
import type { PropsWithChildren } from 'react';

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-root">
      <header className="top-nav">
        <Link className="brand" to="/">
          <img src="/DirectorsCutLogo.png" alt="" className="brand-logo" />
          <span className="brand-text">DirectorsCut</span>
        </Link>
        <nav>
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/explore">Explore</NavLink>
        </nav>
      </header>
      <main className="page-container">{children}</main>
    </div>
  );
}
