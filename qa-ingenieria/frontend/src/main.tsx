import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ActivityProvider } from "./components/Activity";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ActivityProvider>
      <App />
    </ActivityProvider>
  </React.StrictMode>
);
