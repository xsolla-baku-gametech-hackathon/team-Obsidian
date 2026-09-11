export const ACCESS_TOKEN_KEY = 'launchpad_access_token';

const API_UNAVAILABLE = 'API server is unavailable. Start FastAPI with ./scripts/run_api.sh or run ./scripts/dev.sh.';

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${import.meta.env.VITE_API_BASE_URL || ''}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
  } catch {
    throw new Error(API_UNAVAILABLE);
  }

  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new Error(body?.error?.message || API_UNAVAILABLE);
  return body as T;
}
