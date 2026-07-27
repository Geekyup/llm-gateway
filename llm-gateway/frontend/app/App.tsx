import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { LoginGate } from "./components/auth/LoginGate";
import { Dashboard } from "./components/Dashboard";
import { api, getAdminToken, clearAdminToken } from "./lib/api";

export default function App() {
  const [authed, setAuthed] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    (async () => {
      if (getAdminToken()) {
        const ok = await api.verifyToken();
        setAuthed(ok);
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
    return <LoginGate onAuthenticated={() => setAuthed(true)} />;
  }

  return <Dashboard onLogout={() => { clearAdminToken(); setAuthed(false); }} />;
}
