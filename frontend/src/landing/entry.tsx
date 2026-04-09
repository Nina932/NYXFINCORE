import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../index.css';
import LandingPage from './LandingPage';

document.documentElement.setAttribute('data-theme', 'dark');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LandingPage />
  </StrictMode>,
);
