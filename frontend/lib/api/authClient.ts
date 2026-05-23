import type { components } from '@/types/api';

type UserResponse = components['schemas']['UserResponse'];

/**
 * 現在ログイン中のユーザー情報を取得する。
 *
 * localStorage の `token` キーから Bearer トークンを取得して
 * Authorization ヘッダーに付与する。
 * ブラウザ外（SSR）では token が存在しないため、ヘッダーなしで送信する。
 */
export async function fetchCurrentUser(): Promise<UserResponse> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  const headers: HeadersInit = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch('/api/auth/me', { method: 'GET', headers });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<UserResponse>;
}

export function signOut(): void {
  localStorage.removeItem('token');
  window.location.href = '/';
}
