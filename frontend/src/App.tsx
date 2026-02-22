import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { ToastContainer } from './components/ToastContainer';
import { ToastProvider } from './contexts/ToastContext';
import { AnalysisPage } from './pages/AnalysisPage';
import { EndingPage } from './pages/EndingPage';
import { ExplorePage } from './pages/ExplorePage';
import { HomePage } from './pages/HomePage';
import { RewritePage } from './pages/RewritePage';
import { SearchPage } from './pages/SearchPage';

export default function App() {
  return (
    <ToastProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/movie/:movieId" element={<AnalysisPage />} />
          <Route path="/rewrite/:movieId" element={<RewritePage />} />
          <Route path="/ending/:movieId" element={<EndingPage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
      <ToastContainer />
    </ToastProvider>
  );
}
