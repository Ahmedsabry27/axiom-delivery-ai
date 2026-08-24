import axios from "axios";
import { getAccessToken } from "./auth";

const apiBaseUrl = import.meta.env.VITE_API_URL || "";
if (import.meta.env.PROD && apiBaseUrl && !apiBaseUrl.startsWith("https://")) {
  throw new Error("VITE_API_URL must use HTTPS in production");
}

const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

// --------------------------------------------------
// Request Interceptor
// --------------------------------------------------
api.interceptors.request.use(
  async (config) => {
    try {
      const token = await getAccessToken();

      config.headers = config.headers || {};

      if (import.meta.env.DEV) {
        console.log("[api.js] request", config.url, "token present?", !!token);
      }

      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      } else if (import.meta.env.DEV) {
        console.warn("No access token available for API request", config.url);
      }

      return config;
    } catch (error) {
      if (import.meta.env.DEV) console.error("Failed to retrieve access token", error);
      return Promise.reject(error);
    }
  },
  (error) => Promise.reject(error)
);

// --------------------------------------------------
// Response Interceptor
// --------------------------------------------------
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (import.meta.env.DEV) {
      console.error("API request failed", {
        status: error.response?.status,
        url: error.config?.url,
      });
    }
    return Promise.reject(error);
  }
);

export default api;
