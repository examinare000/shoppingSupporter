'use client';

import { useEffect, useState } from 'react';
import { Masthead } from '@/components/editorial/Masthead';
import { RuledDivider } from '@/components/editorial/RuledDivider';
import { Logo } from '@/components/branding/Logo';
import { Spinner } from '@/components/feedback/Spinner';
import { ProfileCard } from '@/components/profile/ProfileCard';
import { fetchCurrentUser } from '@/lib/api/authClient';
import type { components } from '@/types/api';

type UserResponse = components['schemas']['UserResponse'];

/**
 * プロフィールページ。
 *
 * 認証トークンがあれば /api/auth/me を呼び出してユーザー情報を表示する。
 * 未認証または取得失敗の場合は、エラー状態を表示する。
 *
 * ローディング/エラー/成功の 3 状態はホームページと同様の SWR パターンを採用せず、
 * useEffect + useState にした理由: profileCard はワンショット表示で再取得が不要なため。
 */
export default function ProfilePage() {
  const [profile, setProfile] = useState<UserResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchCurrentUser()
      .then(setProfile)
      .catch((err: unknown) => {
        if (err instanceof Error && err.message.startsWith('401')) {
          setError('ログインが必要です');
        } else {
          setError('プロフィールの取得に失敗しました');
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <main className="relative z-10 min-h-screen">
      <div className="mx-auto max-w-screen-xl px-6">
        <Masthead />

        <div className="mx-auto max-w-md">
          {isLoading ? (
            <div className="py-24 flex justify-center">
              <Spinner />
            </div>
          ) : error ? (
            <ErrorState message={error} />
          ) : profile ? (
            <ProfileCard profile={profile} />
          ) : null}
        </div>

        <RuledDivider variant="double" className="mt-16" />
        <footer className="px-6 py-6 flex items-center justify-between font-mono text-xs small-caps text-ink-muted">
          <Logo size="sm" withDomain />
          <span>2026</span>
        </footer>
      </div>
    </main>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="py-24 text-center space-y-4 animate-fade-in-up">
      <p className="font-mono text-[0.65rem] small-caps tracking-editorial text-vermilion">
        — Access Denied —
      </p>
      <p className="font-serif text-base text-ink-muted">{message}</p>
      <a
        href="/"
        className="inline-block font-mono text-xs small-caps tracking-editorial text-ink-muted hover:text-ink transition-colors"
      >
        ホームへ戻る →
      </a>
    </div>
  );
}
