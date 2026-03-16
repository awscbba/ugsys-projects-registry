import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '@ugsys/ui-lib';
import App from './app/App';
import { initializeAuth } from './stores/authStore';
import './index.css';

// Hydrate auth state from localStorage before first render
initializeAuth();

const rootElement = document.getElementById('root');

if (!rootElement) {
  console.error('[App] #root element not found — cannot mount React app');
} else {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </React.StrictMode>
  );
}
