import axios from 'axios';

// Use the VITE_API_URL environment variable if it exists (for Vercel deployment),
// otherwise gracefully fallback to localhost for local development.
const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: baseURL,
});

export default api;
