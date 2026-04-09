import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import AppMain from './AppMain';

// Initialize theme from localStorage before first render
const savedTheme = localStorage.getItem('finai-theme') as 'dark' | 'light' | null;
if (savedTheme) {
  document.documentElement.setAttribute('data-theme', savedTheme);
} else {
  document.documentElement.setAttribute('data-theme', 'dark');
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppMain />
  </StrictMode>,
);
