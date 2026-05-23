'use client';

import { RuledDivider } from '@/components/editorial/RuledDivider';
import { signOut } from '@/lib/api/authClient';
import type { components } from '@/types/api';

type UserResponse = components['schemas']['UserResponse'];

interface ProfileCardProps {
  profile: UserResponse;
}

function formatEditorialDate(iso: string): string {
  const d = new Date(iso);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}.${month}.${day}`;
}

function getInitial(email: string): string {
  return email.charAt(0).toUpperCase();
}

function getShortCredential(id: string): string {
  return id.replace(/-/g, '').slice(0, 8).toUpperCase();
}

/**
 * プロフィール情報を「記者証（Press Credential）」様式で表示するカード。
 *
 * 設計意図:
 * - Fraunces Black のモノグラムを中心に据えることで、味気ない円形アバターを避けつつ
 *   エディトリアル感を担保する。
 * - 認証番号（UUID の先頭8桁）を朱赤で表示し、公文書的な重みを与える。
 * - FILED SINCE / CREDENTIAL NO. は新聞の奥付スタイルで小キャプション化する。
 * - ハードシャドウ（box-shadow で色を指定）により、印刷物のスタンプ感を出す。
 */
export function ProfileCard({ profile }: ProfileCardProps) {
  const initial = getInitial(profile.email);
  const filedDate = formatEditorialDate(profile.createdAt);
  const shortCredential = getShortCredential(profile.id);

  return (
    <article
      className="mt-10 pb-10 animate-fade-in-up"
      aria-label="メンバーダッシュボード"
    >
      {/* ─── セクションヘッダー ─── */}
      <RuledDivider variant="double" />
      <div className="flex items-baseline justify-between py-3">
        <span className="font-mono text-xs small-caps tracking-editorial text-ink-muted">
          Member Dossier
        </span>
        <span className="font-mono text-xs tabular text-vermilion" aria-label={`認証番号 ${shortCredential}`}>
          № {shortCredential}
        </span>
      </div>
      <RuledDivider variant="single" />

      {/* ─── モノグラム + 基本情報 ─── */}
      <div className="flex flex-col items-center gap-8 py-14">
        {/* スタンプ様のモノグラム */}
        <div
          className="animate-stamp-in flex items-center justify-center w-32 h-32 bg-paper-high border-2 border-ink"
          style={{
            boxShadow: '5px 5px 0 var(--ink-primary)',
          }}
          aria-hidden="true"
        >
          <span
            className="font-display font-black text-[5rem] text-ink leading-none tracking-tightest select-none"
            style={{ marginTop: '-0.05em' }}
          >
            {initial}
          </span>
        </div>

        {/* 肩書き + メールアドレス */}
        <div className="text-center space-y-1">
          <p className="font-mono text-[0.65rem] small-caps tracking-editorial text-ink-muted">
            Correspondent
          </p>
          <p className="font-serif text-xl leading-snug text-ink">
            {profile.email}
          </p>
        </div>
      </div>

      {/* ─── 詳細グリッド ─── */}
      <RuledDivider variant="single" />
      <div className="grid grid-cols-2" style={{ borderBottom: '1px solid var(--rule-line)' }}>
        {/* Filed Since */}
        <div
          className="px-0 py-6"
          style={{ borderRight: '1px solid var(--rule-line)' }}
        >
          <p className="font-mono text-[0.6rem] small-caps tracking-editorial text-ink-muted mb-2">
            Filed Since
          </p>
          <p className="font-mono tabular text-ink text-base leading-none">
            {filedDate}
          </p>
        </div>

        {/* Press ID */}
        <div className="px-5 py-6">
          <p className="font-mono text-[0.6rem] small-caps tracking-editorial text-ink-muted mb-2">
            Press ID
          </p>
          <p className="font-mono tabular text-mustard text-base leading-none">
            {shortCredential}
          </p>
        </div>
      </div>

      {/* ─── フル UUID ─── */}
      <div
        className="mt-0 px-0 py-5"
        style={{ borderBottom: '1px solid var(--rule-line)' }}
      >
        <p className="font-mono text-[0.6rem] small-caps tracking-editorial text-ink-muted mb-2">
          Credential Certificate
        </p>
        <p
          className="font-mono text-[0.7rem] tabular text-ink-muted break-all"
          aria-label={`クレデンシャル番号 ${profile.id}`}
        >
          {profile.id}
        </p>
      </div>

      {/* ─── アクション ─── */}
      <div className="flex justify-end pt-8">
        <button
          type="button"
          onClick={signOut}
          className="font-mono text-[0.7rem] small-caps tracking-editorial text-ink-muted hover:text-vermilion transition-colors duration-150 group"
          aria-label="サインアウトする"
        >
          サインアウト{' '}
          <span
            className="inline-block transition-transform duration-150 group-hover:translate-x-1"
            aria-hidden="true"
          >
            →
          </span>
        </button>
      </div>
    </article>
  );
}
