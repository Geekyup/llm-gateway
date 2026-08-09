import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  api,
  getAccessToken,
  getRefreshToken,
  setTokenPair,
  clearTokenPair,
  startGoogleLogin,
  type UserRead,
} from "./lib/api";
import { LoginGate } from "./components/auth/LoginGate";
import { Dashboard } from "./Dashboard";
import LandingPage from "./LandingPage";

export default function App() {
  const [authed, setAuthed] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [user, setUser] = useState<UserRead | null>(null);

  useEffect(() => {
    (async () => {
      if (location.hash.includes("access_token=")) {
        const params = new URLSearchParams(location.hash.slice(1));
        const accessToken = params.get("access_token");
        const refreshToken = params.get("refresh_token");
        if (accessToken && refreshToken) {
          setTokenPair(accessToken, refreshToken);
          history.replaceState(null, "", location.pathname + location.search);
        }
      }

      if (getAccessToken() || getRefreshToken()) {
        try {
          const me = await api.me();
          setUser(me);
          setAuthed(true);
        } catch {
          clearTokenPair();
          setAuthError("Your session expired — please sign in again.");
        }
      }
      setCheckingAuth(false);
    })();
  }, []);

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#0A0A0B" }}>
        <Loader2 size={20} className="animate-spin" color="#52525B" />
      </div>
    );
  }

  if (!authed) {
    if (authError) {
      return <LoginGate error={authError} />;
    }
    return <LandingPage onSignIn={() => { startGoogleLogin(); }} />;
  }

  return (
    <Dashboard
      user={user}
      onLogout={async () => {
        await api.logout();
        clearTokenPair();
        setUser(null);
        setAuthed(false);
      }}
    />
  );
}
