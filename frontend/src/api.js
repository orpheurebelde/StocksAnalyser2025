import axios from 'axios';

// Production defaults to same-origin /api through the Vercel rewrite so auth
// cookies remain first-party. VITE_API_URL can still override this behavior.
const baseURL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '');

const api = axios.create({
  baseURL: baseURL,
  withCredentials: true,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    return Promise.reject(error);
  },
);

export default api;
