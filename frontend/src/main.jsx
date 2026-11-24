// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/main.jsx
//
// FILE PURPOSE:
// The starting point of the React application. It puts the whole app on the web page.
//
// MAIN RESPONSIBILITY:
// Mount <App/> inside the router, login context and toast provider.
//
// WHAT THIS FILE DOES:
// 1. Finds the <div id="root"> element in index.html.
// 2. Wraps the app in BrowserRouter so page URLs work.
// 3. Wraps it in AuthProvider so every page knows who is logged in.
// 4. Wraps it in ToastProvider so any page can show small pop-up messages.
// 5. Loads the global stylesheet index.css.
//
// HOW THIS FILE WORKS:
// When the browser loads /src/main.jsx, ReactDOM.createRoot renders the component tree once. All other
// pages are reached from App.jsx inside this tree.
//
// INPUT:
// The HTML page (index.html) with an empty root element.
//
// OUTPUT:
// The running React application drawn in the browser.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: App.jsx, AuthContext.jsx, components/SharedUiComponents.jsx, index.css
//
// EXECUTION FLOW:
//    Browser opens index.html
//       |
//       v
//    main.jsx runs
//       |
//       v
//    Providers are created (router, auth, toasts)
//       |
//       v
//    App.jsx decides which page to show
//
// IMPORTANT DEPENDENCIES:
//    react, react-dom, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* React entry point and root rendering. */

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./AuthContext";
import { ToastProvider } from "./components/SharedUiComponents";
import { ThemeProvider } from "./components/ThemeContext";
import { apiUrl } from "./apiClient";
import "./index.css";

// Wake the free-tier backend while the visitor reads the page. Render sleeps the API after ~15 idle
// minutes and it needs ~60-90 s to wake, which used to 502 the first login of the day. This fire-and-
// forget ping starts the wake the moment the site opens, so by the time the sign-in form is submitted
// the API is already up. Failures are normal when offline - api() shows real errors on real requests.
fetch(apiUrl("/api/health/live")).catch(() => {});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
