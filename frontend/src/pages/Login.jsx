import { useEffect, useRef, useState } from 'react';
import { BarChart3, LockKeyhole, ShieldCheck } from 'lucide-react';
import api from '../api';

const GOOGLE_SCRIPT_ID = 'google-identity-services';
const GOOGLE_SCRIPT_URL = 'https://accounts.google.com/gsi/client';

export default function Login({ onAuthenticated }) {
  const buttonRef = useRef(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!clientId) return undefined;
    let cancelled = false;

    const initializeGoogle = () => {
      if (cancelled || !window.google?.accounts?.id || !buttonRef.current) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        auto_select: false,
        cancel_on_tap_outside: true,
        callback: async ({ credential }) => {
          setLoading(true);
          setError('');
          try {
            const response = await api.post('/api/auth/google', { credential });
            onAuthenticated(response.data.user);
          } catch (requestError) {
            setError(requestError.response?.data?.detail || 'Google login failed. Please try again.');
          } finally {
            setLoading(false);
          }
        },
      });
      buttonRef.current.replaceChildren();
      window.google.accounts.id.renderButton(buttonRef.current, {
        type: 'standard',
        theme: 'filled_black',
        size: 'large',
        shape: 'pill',
        text: 'signin_with',
        width: 320,
      });
    };

    let script = document.getElementById(GOOGLE_SCRIPT_ID);
    if (!script) {
      script = document.createElement('script');
      script.id = GOOGLE_SCRIPT_ID;
      script.src = GOOGLE_SCRIPT_URL;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    if (window.google?.accounts?.id) initializeGoogle();
    else script.addEventListener('load', initializeGoogle, { once: true });

    return () => {
      cancelled = true;
      script?.removeEventListener('load', initializeGoogle);
    };
  }, [clientId, onAuthenticated]);

  return (
    <main className="login-page">
      <section className="login-card glass-panel">
        <div className="login-brand-icon"><BarChart3 size={34} /></div>
        <p className="metric-label">Secure financial intelligence</p>
        <h1 className="text-gradient">StocksAnalyser</h1>
        <p className="login-intro">Sign in to access saved filings, analysis tools, and your authenticated activity history.</p>

        <div className="login-security-row">
          <span><ShieldCheck size={16} /> Google verified identity</span>
          <span><LockKeyhole size={16} /> Secure server session</span>
        </div>

        {clientId ? <div className="google-login-button" ref={buttonRef} /> : (
          <div className="login-config-error">Set <code>VITE_GOOGLE_CLIENT_ID</code> to enable Google login.</div>
        )}
        {loading && <p className="metric-label">Creating secure session...</p>}
        {error && <p className="login-error" role="alert">{error}</p>}
        <small className="login-privacy">Only basic profile identity is requested. Passwords and Google access tokens are never stored.</small>
      </section>
    </main>
  );
}
