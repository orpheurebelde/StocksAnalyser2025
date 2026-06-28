import { useEffect, useRef, useState } from 'react';
import { BarChart3, LockKeyhole, ShieldCheck } from 'lucide-react';
import api from '../api';

const GOOGLE_SCRIPT_ID = 'google-identity-services';
const GOOGLE_SCRIPT_URL = 'https://accounts.google.com/gsi/client';
const DEVICE_STORAGE_KEY = 'stocks_analyser_device_id';

const getDeviceId = () => {
  let value = window.localStorage.getItem(DEVICE_STORAGE_KEY);
  if (!value) {
    value = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
    window.localStorage.setItem(DEVICE_STORAGE_KEY, value);
  }
  return value;
};

export default function Login({ onAuthenticated, sessionChecking = false }) {
  const buttonRef = useRef(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [blockedCredential, setBlockedCredential] = useState('');
  const [requestMessage, setRequestMessage] = useState('');
  const [requestStatus, setRequestStatus] = useState('');
  const embeddedClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
  const [clientId, setClientId] = useState(embeddedClientId);
  const [configChecked, setConfigChecked] = useState(Boolean(embeddedClientId));

  useEffect(() => {
    if (embeddedClientId) return undefined;
    let active = true;
    api.get('/api/auth/config')
      .then((response) => {
        if (active) setClientId(response.data.google_client_id || '');
      })
      .catch(() => {
        if (active) setError('Could not load Google login configuration.');
      })
      .finally(() => {
        if (active) setConfigChecked(true);
      });
    return () => { active = false; };
  }, [embeddedClientId]);

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
            const response = await api.post('/api/auth/google', { credential, device_id: getDeviceId() });
            onAuthenticated(response.data.user);
          } catch (requestError) {
            const detail = requestError.response?.data?.detail || 'Google login failed. Please try again.';
            setError(detail);
            if (detail.includes('Registration limit reached')) setBlockedCredential(credential);
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

  const submitAccessRequest = async (event) => {
    event.preventDefault();
    setLoading(true);
    setRequestStatus('');
    try {
      const response = await api.post('/api/auth/registration-access/request', {
        credential: blockedCredential,
        device_id: getDeviceId(),
        message: requestMessage,
      });
      setRequestStatus(response.data.message || 'Access request submitted to administrator.');
      setBlockedCredential('');
    } catch (requestError) {
      setRequestStatus(requestError.response?.data?.detail || 'Could not submit access request.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-card glass-panel">
        <div className="login-brand-icon"><BarChart3 size={34} /></div>
        <p className="metric-label">Secure financial intelligence</p>
        <h1 className="text-gradient">StocksAnalyser</h1>
        <p className="login-intro">Sign in to access saved filings, analysis tools, and your authenticated activity history.</p>
        {sessionChecking && <p className="metric-label" role="status">Checking existing session in background...</p>}

        <div className="login-security-row">
          <span><ShieldCheck size={16} /> Google verified identity</span>
          <span><LockKeyhole size={16} /> Secure server session</span>
        </div>

        {clientId ? <div className="google-login-button" ref={buttonRef} /> : configChecked ? (
          <div className="login-config-error">Set <code>GOOGLE_CLIENT_ID</code> on backend or <code>VITE_GOOGLE_CLIENT_ID</code> on frontend.</div>
        ) : (
          <p className="metric-label">Loading Google login configuration...</p>
        )}
        {loading && <p className="metric-label">Creating secure session...</p>}
        {error && <p className="login-error" role="alert">{error}</p>}
        {blockedCredential && (
          <form className="registration-request-form" onSubmit={submitAccessRequest}>
            <label htmlFor="registration-message">Request access from administrator</label>
            <textarea id="registration-message" value={requestMessage} onChange={(event) => setRequestMessage(event.target.value)} maxLength={1000} placeholder="Explain why you need access." />
            <button className="btn-primary" type="submit" disabled={loading}>Send access request</button>
          </form>
        )}
        {requestStatus && <p className="metric-label" role="status">{requestStatus}</p>}
        <small className="login-privacy">Only basic profile identity is requested. Passwords and Google access tokens are never stored.</small>
      </section>
    </main>
  );
}
