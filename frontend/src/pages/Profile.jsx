import { useEffect, useState } from 'react';
import { Activity, CalendarDays, LogOut, Mail, ShieldCheck, UserCircle } from 'lucide-react';
import api from '../api';

const formatDate = (value) => {
  if (!value) return 'Not available';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

export default function Profile({ user, onLogout }) {
  const [activity, setActivity] = useState([]);
  const [users, setUsers] = useState([]);
  const [registration, setRegistration] = useState(null);
  const [registrationRequests, setRegistrationRequests] = useState([]);
  const [registrationModalOpen, setRegistrationModalOpen] = useState(false);
  const [quotaRequests, setQuotaRequests] = useState([]);
  const [quotaModalOpen, setQuotaModalOpen] = useState(false);
  const [securityModalOpen, setSecurityModalOpen] = useState(false);
  const [fraudEvents, setFraudEvents] = useState([]);
  const [loginEvents, setLoginEvents] = useState([]);
  const [access, setAccess] = useState({
    requested: Boolean(user.analysis_requested),
    authorized: Boolean(user.analysis_authorized || user.is_admin),
  });
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    api.get('/api/auth/activity?limit=25')
      .then((response) => { if (active) setActivity(response.data.activity || []); })
      .catch((requestError) => {
        if (active) setError(requestError.response?.data?.detail || 'Could not load recent activity.');
      });
    if (user.is_admin) {
      api.get('/api/auth/admin/users')
        .then((response) => { if (active) { setUsers(response.data.users || []); setRegistration(response.data.registration || null); setRegistrationRequests(response.data.registration_requests || []); } })
        .catch((requestError) => {
          if (active) setError(requestError.response?.data?.detail || 'Could not load users.');
        });
      api.get('/api/auth/admin/quota-requests')
        .then((response) => { if (active) setQuotaRequests(response.data.requests || []); })
        .catch(() => {});
      api.get('/api/auth/admin/audit?limit=100')
        .then((response) => {
          if (active) {
            setFraudEvents(response.data.fraud_events || []);
            setLoginEvents(response.data.login_events || []);
          }
        })
        .catch(() => {});
    }
    return () => { active = false; };
  }, [user.is_admin]);

  const requestAccess = async () => {
    try {
      const response = await api.post('/api/auth/analysis-access/request');
      setAccess({ requested: response.data.user.analysis_requested, authorized: response.data.user.analysis_authorized });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not request analysis access.');
    }
  };

  const changeAccess = async (userId, authorized) => {
    try {
      const response = await api.patch(`/api/auth/admin/users/${userId}/analysis-access`, { authorized });
      setUsers((current) => current.map((item) => (item.id === userId ? response.data.user : item)));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not update analysis access.');
    }
  };

  const decideQuota = async (requestId, approved) => {
    try {
      const response = await api.patch(`/api/auth/admin/quota-requests/${requestId}`, { approved });
      setQuotaRequests((current) => current.map((item) => (item.id === requestId ? { ...item, ...response.data.request } : item)));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not update daily authorization.');
    }
  };

  const role = user.is_admin ? 'Administrator' : user.analysis_authorized ? 'Analyst' : 'User';

  return (
    <section className="profile-page">
      <div className="profile-heading">
        <div>
          <p className="metric-label">Account & access</p>
          <h2>Profile</h2>
        </div>
        <button className="profile-logout" onClick={onLogout} type="button"><LogOut size={18} /> Logout</button>
      </div>

      <div className="profile-card glass-panel">
        {user.picture_url ? <img src={user.picture_url} alt="" referrerPolicy="no-referrer" /> : (
          <div className="profile-avatar-fallback"><UserCircle size={52} /></div>
        )}
        <div className="profile-identity">
          <h3>{user.name || 'Google user'}</h3>
          <span><Mail size={15} /> {user.email}</span>
          <strong className={user.is_admin ? 'admin-role' : ''}><ShieldCheck size={16} /> {role}</strong>
        </div>
      </div>

      <div className="profile-facts">
        <div className="glass-panel"><CalendarDays size={20} /><span>Account created</span><strong>{formatDate(user.created_at)}</strong></div>
        <div className="glass-panel"><ShieldCheck size={20} /><span>Last Google login</span><strong>{formatDate(user.last_login_at)}</strong></div>
      </div>

      {!user.is_admin && (
        <div className="glass-panel profile-access">
          <div><ShieldCheck size={20} /><h3>AI analysis access</h3></div>
          <p>{access.authorized ? 'Authorized by administrator.' : access.requested ? 'Authorization request pending.' : 'Administrator authorization required before using AI agents.'}</p>
          {!access.authorized && !access.requested && <button type="button" onClick={requestAccess}>Request authorization</button>}
        </div>
      )}

      {user.is_admin && (
        <div className="glass-panel profile-activity">
          <div className="profile-activity-title"><ShieldCheck size={20} /><h3>User analysis authorization {registration ? `(${registration.registered_users}/${registration.registration_limit})` : ''}</h3><button type="button" onClick={() => setRegistrationModalOpen(true)}>Registration requests ({registrationRequests.filter((item) => item.status === 'pending').length})</button><button type="button" onClick={() => setQuotaModalOpen(true)}>Daily limit requests ({quotaRequests.filter((item) => item.status === 'pending').length})</button><button type="button" onClick={() => setSecurityModalOpen(true)}>Security log ({fraudEvents.length})</button></div>
          <div className="profile-activity-table-wrap">
            <table className="earnings-table">
              <thead><tr><th>User</th><th>Role</th><th>Request</th><th>Analysis</th><th>Action</th></tr></thead>
              <tbody>{users.map((item) => (
                <tr key={item.id}>
                  <td>{item.name || item.email}<br /><small>{item.email}</small></td>
                  <td>{item.is_admin ? 'Administrator' : item.analysis_authorized ? 'Analyst' : 'User'}</td>
                  <td>{item.analysis_requested ? 'Pending' : 'None'}</td>
                  <td>{item.analysis_authorized ? 'Allowed' : 'Blocked'}</td>
                  <td>{!item.is_admin && <button type="button" onClick={() => changeAccess(item.id, !item.analysis_authorized)}>{item.analysis_authorized ? 'Revoke' : 'Allow'}</button>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {user.is_admin && quotaModalOpen && (
        <div className="profile-modal-backdrop" role="presentation" onMouseDown={() => setQuotaModalOpen(false)}>
          <div className="glass-panel profile-modal" role="dialog" aria-modal="true" aria-label="Daily analysis authorization requests" onMouseDown={(event) => event.stopPropagation()}>
            <div className="profile-heading"><h3>Daily analysis limit requests</h3><button type="button" onClick={() => setQuotaModalOpen(false)}>Close</button></div>
            <div className="profile-activity-table-wrap">
              <table className="earnings-table">
                <thead><tr><th>User</th><th>Date</th><th>Status</th><th>Authorization</th></tr></thead>
                <tbody>{quotaRequests.map((item) => (
                  <tr key={item.id}><td>{item.name || item.email}<br /><small>{item.email}</small></td><td>{item.usage_date}</td><td>{item.status}</td><td><button type="button" onClick={() => decideQuota(item.id, true)}>Authorize</button> <button type="button" onClick={() => decideQuota(item.id, false)}>Reject</button></td></tr>
                ))}</tbody>
              </table>
              {quotaRequests.length === 0 && <p className="metric-label">No daily limit requests.</p>}
            </div>
          </div>
        </div>
      )}

      {user.is_admin && registrationModalOpen && (
        <div className="profile-modal-backdrop" role="presentation" onMouseDown={() => setRegistrationModalOpen(false)}>
          <div className="glass-panel profile-modal" role="dialog" aria-modal="true" aria-label="Registration access requests" onMouseDown={(event) => event.stopPropagation()}>
            <div className="profile-heading"><h3>Registration access requests</h3><button type="button" onClick={() => setRegistrationModalOpen(false)}>Close</button></div>
            <div className="profile-activity-table-wrap">
              <table className="earnings-table"><thead><tr><th>Time</th><th>User</th><th>IP</th><th>Message</th><th>Status</th></tr></thead><tbody>{registrationRequests.map((item) => <tr key={item.id}><td>{formatDate(item.requested_at)}</td><td>{item.name || item.email}<br /><small>{item.email}</small></td><td>{item.ip_address || 'Unknown'}</td><td>{item.request_message || 'No message'}</td><td>{item.status}</td></tr>)}</tbody></table>
            </div>
            {!registrationRequests.length && <p className="metric-label">No registration requests.</p>}
          </div>
        </div>
      )}

      {user.is_admin && securityModalOpen && (
        <div className="profile-modal-backdrop" role="presentation" onMouseDown={() => setSecurityModalOpen(false)}>
          <div className="glass-panel profile-modal" role="dialog" aria-modal="true" aria-label="Login security log" onMouseDown={(event) => event.stopPropagation()}>
            <div className="profile-heading"><h3>Login security log</h3><button type="button" onClick={() => setSecurityModalOpen(false)}>Close</button></div>
            <h4>Fraud signals</h4>
            <div className="profile-activity-table-wrap"><table className="earnings-table"><thead><tr><th>Time</th><th>Event</th><th>Email</th><th>IP</th><th>Result</th></tr></thead><tbody>{fraudEvents.map((item) => <tr key={item.id}><td>{formatDate(item.created_at)}</td><td>{item.event_type}</td><td>{item.attempted_email}</td><td>{item.ip_address || 'Unknown'}</td><td>{item.blocked ? 'Blocked' : 'Review'}</td></tr>)}</tbody></table></div>
            {!fraudEvents.length && <p className="metric-label">No fraud signals recorded.</p>}
            <h4 style={{ marginTop: '1.5rem' }}>Recent logins</h4>
            <div className="profile-activity-table-wrap"><table className="earnings-table"><thead><tr><th>Time</th><th>Email</th><th>IP</th><th>Event</th><th>Success</th></tr></thead><tbody>{loginEvents.map((item) => <tr key={item.id}><td>{formatDate(item.created_at)}</td><td>{item.email || 'Unknown'}</td><td>{item.ip_address || 'Unknown'}</td><td>{item.event_type}</td><td>{item.success ? 'Yes' : 'No'}</td></tr>)}</tbody></table></div>
          </div>
        </div>
      )}

      <div className="glass-panel profile-activity">
        <div className="profile-activity-title"><Activity size={20} /><h3>Recent activity</h3></div>
        {error && <p className="login-error">{error}</p>}
        {!error && activity.length === 0 && <p className="metric-label">No activity recorded yet.</p>}
        {activity.length > 0 && (
          <div className="profile-activity-table-wrap">
            <table className="earnings-table">
              <thead><tr><th>Time</th><th>IP</th><th>Method</th><th>Path</th><th>Status</th></tr></thead>
              <tbody>{activity.map((item, index) => (
                <tr key={`${item.created_at}-${item.path}-${index}`}>
                  <td>{formatDate(item.created_at)}</td>
                  <td>{item.ip_address || 'Unknown'}</td>
                  <td>{item.method}</td>
                  <td>{item.path}</td>
                  <td>{item.status_code}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
