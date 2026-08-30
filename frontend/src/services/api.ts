import axios, { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface APIState {
  merchantId: string;
  mode: 'SIMULATION' | 'REAL_TEST';
  token: string | null;
  apiKey: string;
}

const getStoredToken = (): string | null => {
  try {
    if (typeof window !== 'undefined' && window.localStorage && typeof window.localStorage.getItem === 'function') {
      return window.localStorage.getItem('recoverai_jwt_token');
    }
  } catch {
    // Ignore storage access errors
  }
  return null;
};

// In-memory Auth / Tenant state
export const currentApiState: APIState = {
  merchantId: 'm_alpha_123',
  mode: 'SIMULATION',
  token: getStoredToken(),
  apiKey: 'key_admin_secret_999',
};

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Request Interceptor for Authorization & Tenant Context
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Inject Bearer JWT if available, else X-API-Key
    if (currentApiState.token) {
      config.headers.Authorization = `Bearer ${currentApiState.token}`;
    } else if (currentApiState.apiKey) {
      config.headers['X-API-Key'] = currentApiState.apiKey;
    }

    // Inject merchant scoping header
    if (currentApiState.merchantId) {
      config.headers['X-Merchant-ID'] = currentApiState.merchantId;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor for Error Notifications
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    const message = error.response?.data?.message || error.message || 'Network error occurred';
    console.error('[API Error]:', message, error.response?.status);
    return Promise.reject(error);
  }
);

// Health Check API
export const checkBackendHealth = async (): Promise<{ status: string; timestamp?: string }> => {
  try {
    const res = await api.get('/health');
    return res.data;
  } catch {
    return { status: 'offline' };
  }
};
