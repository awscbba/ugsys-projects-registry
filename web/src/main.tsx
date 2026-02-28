import React from "react";
import ReactDOM from "react-dom/client";
import App from "./app/App";
import { initializeAuth } from "./stores/authStore";
import "./index.css";

// Hydrate auth state from localStorage before first render
initializeAuth();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
