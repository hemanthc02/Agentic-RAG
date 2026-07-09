import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useStore } from "./store/useStore";
import LandingPage       from "./pages/LandingPage";
import LoginPage         from "./pages/LoginPage";
import RegisterPage      from "./pages/RegisterPage";
import AboutPage         from "./pages/AboutPage";
import WorkspaceLayout   from "./components/WorkspaceLayout";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useStore((s) => s.token);
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const token = useStore((s) => s.token);
  return token ? <Navigate to="/app" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"         element={<LandingPage />} />
        <Route path="/about"    element={<AboutPage />} />
        <Route path="/login"    element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />

        {/* Single workspace: Ask / Research guide / Viva / Papers as tabs.
            All four tabs stay MOUNTED inside WorkspaceLayout (hidden via CSS)
            so in-flight work keeps its UI when the user switches tabs. */}
        <Route path="/app/*" element={<PrivateRoute><WorkspaceLayout /></PrivateRoute>} />

        {/* Legacy URLs */}
        <Route path="/home"       element={<Navigate to="/app" replace />} />
        <Route path="/experiment" element={<Navigate to="/app" replace />} />
        <Route path="/guide"      element={<Navigate to="/app/guide" replace />} />
        <Route path="/viva"       element={<Navigate to="/app/viva" replace />} />
        <Route path="/papers"     element={<Navigate to="/app/papers" replace />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
