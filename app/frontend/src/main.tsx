import React from "react";
import ReactDOM from "react-dom/client";
import { Toaster } from "react-hot-toast";
import App from "./App.tsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
    <Toaster
      position="top-right"
      toastOptions={{
        style: {
          background: "#ffffff",
          color: "#18181b",
          border: "1px solid #e4e4e7",
          borderRadius: "12px",
          boxShadow: "0 20px 40px -15px rgba(0,0,0,0.1)",
        },
        success: { iconTheme: { primary: "#0d9488", secondary: "#fff" } },
        error:   { iconTheme: { primary: "#dc2626", secondary: "#fff" } },
      }}
    />
  </React.StrictMode>,
);
