import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const setAuthToken = (token: string) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    if (typeof window !== 'undefined' && typeof window.localStorage?.setItem === 'function') {
      window.localStorage.setItem('token', token);
    }
  } else {
    delete api.defaults.headers.common['Authorization'];
    if (typeof window !== 'undefined' && typeof window.localStorage?.removeItem === 'function') {
      window.localStorage.removeItem('token');
    }
  }
};

// Interceptor to handle 401s
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && [401, 403, 404].includes(error.response.status)) {
      // Clear token and redirect to login if session is invalid or user was purged
      delete api.defaults.headers.common['Authorization'];
      if (typeof window !== 'undefined' && typeof window.localStorage?.removeItem === 'function') {
        window.localStorage.removeItem('token');
        // If we are not already on login/register, redirect
        if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

