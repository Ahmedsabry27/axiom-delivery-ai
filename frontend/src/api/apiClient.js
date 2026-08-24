import { getAccessToken } from "../services/auth";

export async function authFetch(url, options = {}) {
  const token = await getAccessToken();

  return fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
}