import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowLeft, ArrowRight, BarChart3, Check, Gamepad2, Link, LockKeyhole, LogOut, ShieldCheck, User, X, Youtube } from 'lucide-react';
import GameReport from '../features/recommendations/GameReport';

// Temporary preview bypass. Restore this flag when report checkout is ready.
const REPORT_PAYWALL_ENABLED = false;
const ACCESS_TOKEN_KEY = 'launchpad_access_token';

type UserRole = 'game_developer' | 'content_creator';
type PlanName = 'starter' | 'pro' | 'studio';
type Account = {
  id: number;
  email: string;
  display_name: string | null;
  premium_role: UserRole | null;
  subscription_plan: PlanName | null;
  subscription_status: 'inactive' | 'active' | 'pending_youtube_verification';
  youtube_channel_id: string | null;
};
type AuthSession = { access_token: string; user: Account };

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || ''}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new Error(body?.error?.message || 'Request failed.');
  return body as T;
}

function steamLink(value: string): string | null {
  try {
    const url = new URL(value.trim());
    const match = url.pathname.match(/^\/app\/([1-9]\d*)(?:\/[^/]*)?\/?$/);
    if (url.protocol !== 'https:' || url.hostname !== 'store.steampowered.com' || url.port || url.username || url.password || !match) return null;
    return `https://store.steampowered.com/app/${match[1]}/`;
  } catch { return null; }
}

export default function App() {
  const [input, setInput] = useState('');
  const [confirmed, setConfirmed] = useState('');
  const [error, setError] = useState('');
  const [subscription, setSubscription] = useState(false);
  const [subscriptionSource, setSubscriptionSource] = useState<'home' | 'report'>('home');
  const [selectedPlan, setSelectedPlan] = useState('Starter');
  const [billing, setBilling] = useState<'monthly' | 'yearly'>('monthly');
  const subscriptionTitle = useRef<HTMLHeadingElement>(null);
  const unlockButton = useRef<HTMLButtonElement>(null);
  const [checkoutNotice, setCheckoutNotice] = useState(false);
  const paywall = useRef<HTMLDialogElement>(null);
  const authDialog = useRef<HTMLDialogElement>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [authMode, setAuthMode] = useState<'login' | 'signup'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authName, setAuthName] = useState('');
  const [authError, setAuthError] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [selectedRole, setSelectedRole] = useState<UserRole>('game_developer');
  const [youtubeChannel, setYoutubeChannel] = useState('');
  const canUseReports = account?.subscription_status === 'active';
  const needsPlan = account?.subscription_status === 'inactive';
  const needsYouTube = account?.subscription_status === 'pending_youtube_verification';

  useEffect(() => {
    if (subscription) subscriptionTitle.current?.focus();
  }, [subscription]);

  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    void api<Account>('/api/v1/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(setAccount)
      .catch(() => localStorage.removeItem(ACCESS_TOKEN_KEY));
  }, []);

  function openAuth(mode: 'login' | 'signup') {
    setAuthMode(mode);
    setAuthError('');
    setAuthBusy(false);
    authDialog.current?.showModal();
  }

  async function submitAuth(event: FormEvent) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError('');
    try {
      const session = await api<AuthSession>(`/api/v1/auth/${authMode}`, {
        method: 'POST',
        body: JSON.stringify({
          email: authEmail,
          password: authPassword,
          ...(authMode === 'signup' ? { display_name: authName || null } : {}),
        }),
      });
      localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
      setAccount(session.user);
      authDialog.current?.close();
      setAuthPassword('');
      if (session.user.subscription_status !== 'active') {
        setSubscription(true);
        paywall.current?.showModal();
      }
    } catch (cause) {
      setAuthError(cause instanceof Error ? cause.message : 'Authentication failed.');
    } finally {
      setAuthBusy(false);
    }
  }

  function logout() {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      void api('/api/v1/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => undefined);
    }
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    setAccount(null);
  }

  async function choosePlan(plan: PlanName) {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!account || !token) {
      openAuth('signup');
      return;
    }
    setCheckoutNotice(false);
    const updated = await api<Account>('/api/v1/auth/subscription', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ plan, role: selectedRole }),
    });
    setAccount(updated);
    setSelectedPlan(plan[0].toUpperCase() + plan.slice(1));
    setCheckoutNotice(true);
  }

  async function verifyYoutube() {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token || !youtubeChannel.trim()) return;
    const updated = await api<Account>('/api/v1/auth/youtube/dev-verify', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        channel_id: youtubeChannel.trim(),
        google_subject: `dev-google:${account?.id}`,
      }),
    });
    setAccount(updated);
  }

  function openSubscription(source: 'home' | 'report') {
    if (!account) {
      openAuth('signup');
      return;
    }
    setSubscriptionSource(source);
    setBilling('monthly');
    setCheckoutNotice(false);
    setSubscription(true);
    paywall.current?.showModal();
  }

  function confirm(event: FormEvent) {
    event.preventDefault();
    if (!account) {
      openAuth('signup');
      return;
    }
    if (!canUseReports) {
      openSubscription('home');
      return;
    }
    const url = steamLink(input);
    if (!url) {
      setError('Enter a Steam store game link, like https://store.steampowered.com/app/123456/');
      return;
    }
    setError('');
    setConfirmed(url);
    setSubscription(false);
    setBilling('monthly');
    setCheckoutNotice(false);
    paywall.current?.showModal();
  }

  return <div className="page">
    <header className="header">
      <a className="brand" href="/" aria-label="Launchpad home"><span><Gamepad2 size={21} /></span>launchpad.</a>
      <div className="auth-actions">{account ? <><span className="account-chip"><User size={15} />{account.display_name || account.email}</span><button className="auth-login" type="button" onClick={logout}>Log out <LogOut size={14} /></button></> : <><button className="auth-login" type="button" onClick={() => openAuth('login')}>Log in</button><button className="primary" type="button" onClick={() => openAuth('signup')}>Sign up</button></>}</div>
    </header>

    <main className={canUseReports ? 'landing workspace' : 'landing welcome'}>
      {!account && <>
        <div className="eyebrow">INDIE LAUNCH INTELLIGENCE</div>
        <h1>Know the market before you launch.</h1>
        <p className="intro">Launchpad turns Steam data into pricing context, competitor maps, and release timing evidence for indie teams and creator partners.</p>
        <div className="welcome-actions"><button className="primary" type="button" onClick={() => openAuth('signup')}>Create free account <ArrowRight size={17} /></button><button className="secondary" type="button" onClick={() => openAuth('login')}>Log in</button></div>
        <div className="welcome-grid">
          <article><BarChart3 size={21} /><h2>Market reports</h2><p>Paste a Steam game link after signup and compare it against the local Steam catalog.</p></article>
          <article><Gamepad2 size={21} /><h2>Developer plans</h2><p>Game developers unlock reports immediately after choosing a subscription plan.</p></article>
          <article><Youtube size={21} /><h2>Creator access</h2><p>Content creators verify a YouTube channel before their premium workspace activates.</p></article>
          <article><ShieldCheck size={21} /><h2>Secure accounts</h2><p>Passwords are hashed, sessions expire, and premium API routes require authentication.</p></article>
        </div>
      </>}
      {account && !canUseReports && <section className="onboarding-panel">
        <p className="eyebrow">WELCOME, {account.display_name || account.email}</p>
        <h1>Finish your workspace setup.</h1>
        {needsPlan && <p className="intro">Your account is ready. Choose a subscription and account type to unlock Steam reports.</p>}
        {needsYouTube && <p className="intro">Your creator plan is selected. Verify your YouTube channel to activate premium access.</p>}
        <div className="setup-steps">
          <div className="done"><Check size={18} /><span>Account created</span></div>
          <div className={needsYouTube ? 'done' : ''}><Check size={18} /><span>Subscription selected</span></div>
          <div><Youtube size={18} /><span>{needsYouTube ? 'YouTube verification required' : 'Creator verification if needed'}</span></div>
        </div>
        {needsPlan && <button className="primary setup-cta" onClick={() => openSubscription('home')}>Choose plan <ArrowRight size={17} /></button>}
        {needsYouTube && <section className="youtube-verify inline-verify"><h3>Verify your YouTube channel</h3><p>Enter a channel ID for local development. The production version will use Google OAuth.</p><div><input value={youtubeChannel} onChange={event => setYoutubeChannel(event.target.value)} placeholder="YouTube channel ID, e.g. UC…" /><button className="primary" onClick={() => void verifyYoutube()}>Verify YouTube</button></div></section>}
      </section>}
      {canUseReports && <>
        <div className="eyebrow">PREMIUM WORKSPACE</div>
        <h1>Your game.<br />Its next big opportunity.</h1>
        <p className="intro">Find similar games and see how your pricing compares.<br className="desktop-break" /> Start with your Steam link.</p>
        <form className="link-form" onSubmit={confirm} noValidate>
          <label htmlFor="steam-url">Your game's Steam store link</label>
          <div className={`input-row ${error ? 'invalid' : ''}`}>
            <Link size={19} aria-hidden="true" />
            <input id="steam-url" type="url" value={input} onChange={event => { setInput(event.target.value); setError(''); }} placeholder="https://store.steampowered.com/app/…" required aria-invalid={!!error} aria-describedby={error ? 'link-error' : 'link-hint'} autoComplete="url" />
            <button className="primary" type="submit">Generate report <ArrowRight size={17} /></button>
          </div>
          {error ? <p id="link-error" className="error" role="alert">{error}</p> : <p id="link-hint" className="hint">Signed in as {account.email}</p>}
        </form>
        <div className="benefits"><span>Competitor matches</span><i /><span>Price recommendations</span><i /><span>Steam market data</span></div>
      </>}
    </main>

    <footer><span>Built for independent minds.</span><span>Steam launch intelligence</span></footer>

    <dialog ref={paywall} className="report-dialog" aria-labelledby={subscription ? "subscription-title" : REPORT_PAYWALL_ENABLED ? "paywall-title" : "report-title"} onClose={() => { setCheckoutNotice(false); setSubscription(false); setConfirmed(''); }}>
      <div className="report-header"><div><span className="confirmed"><Check size={14} />{subscription ? 'Launchpad subscriptions' : 'Link format confirmed'}</span><p>{subscription ? 'Ongoing insights for your next launches' : confirmed}</p></div><button className="close" onClick={() => paywall.current?.close()} aria-label="Close dialog"><X size={21} /></button></div>
      {subscription ? <section className="subscription-screen">
        <button className="back-button" onClick={() => { if (subscriptionSource === 'home') { paywall.current?.close(); } else { setSubscription(false); setCheckoutNotice(false); requestAnimationFrame(() => unlockButton.current?.focus()); } }}><ArrowLeft size={15} /> {subscriptionSource === 'home' ? 'Back to home' : 'Back to single report'}</button>
        <div className="subscription-heading"><p className="eyebrow">INVEST IN YOUR NEXT MOVE</p><h2 id="subscription-title" ref={subscriptionTitle} tabIndex={-1}>Choose your premium workspace.</h2><p>Plans unlock either a game developer or content creator account after login.</p></div>
        <fieldset className="billing-options role-options"><legend>Choose account type</legend>{([
          ['game_developer', 'Game developer'],
          ['content_creator', 'Content creator'],
        ] as const).map(([role, label]) => <label key={role} className={selectedRole === role ? 'selected' : ''}><input type="radio" name="role" checked={selectedRole === role} onChange={() => { setSelectedRole(role); setCheckoutNotice(false); }} /><span>{label}</span></label>)}</fieldset>
        <fieldset className="billing-options plan-billing"><legend>Choose your billing cycle</legend>{(['monthly', 'yearly'] as const).map(cycle => <label key={cycle} className={billing === cycle ? 'selected' : ''}><input type="radio" name="billing" checked={billing === cycle} onChange={() => { setBilling(cycle); setCheckoutNotice(false); }} /><span>{cycle === 'monthly' ? 'Monthly' : 'Yearly'}</span>{cycle === 'yearly' && <small>Save 20%</small>}</label>)}</fieldset>
        <div className="subscription-plans">
          {[
            { id: 'starter', name: 'Starter', price: 19, reports: 3, badge: 'For solo developers', description: 'Keep a close eye on your next launch.' },
            { id: 'pro', name: 'Pro', price: 39, reports: 10, badge: 'For growing teams', description: 'Compare opportunities across more games.' },
            { id: 'studio', name: 'Studio', price: 79, reports: 30, badge: 'For studios', description: 'Support a larger portfolio of launches.' },
          ].map(plan => <article key={plan.name} className={`subscription-card ${plan.name === 'Pro' ? 'annual-plan' : ''}`}>
            <div className="plan-heading"><h3 className="plan-name">{plan.name}</h3><span className="plan-badge">{plan.badge}</span></div>
            <p className="plan-description">{plan.description}</p>
            <p className="plan-price">${billing === 'monthly' ? plan.price : (plan.price * 0.8).toFixed(2)}<span> / month</span></p>
            <p className="billing-detail">{billing === 'monthly' ? `$${plan.price} billed monthly · Renews monthly` : `$${(plan.price * 12 * 0.8).toFixed(2)} billed yearly · Renews yearly`} · USD</p>
            <ul className="plan-features">{[`${plan.reports} full reports per month`, 'Competitor and market insights', 'Recommended launch windows', 'Creators matched to your niche'].map(feature => <li key={feature}><Check size={17} />{feature}</li>)}</ul>
            <p className="plan-allowance">Report allowance resets monthly. Unused reports do not roll over.</p>
            <button className="primary unlock" onClick={() => void choosePlan(plan.id as PlanName)}>Choose {plan.name} <ArrowRight size={17} /></button>
          </article>)}
        </div>
        {account?.subscription_status === 'pending_youtube_verification' && <section className="youtube-verify"><h3>Verify your YouTube channel</h3><p>Content creator accounts require a YouTube channel connected through Google. This local dev button stores the verified channel until OAuth credentials are added.</p><div><input value={youtubeChannel} onChange={event => setYoutubeChannel(event.target.value)} placeholder="YouTube channel ID, e.g. UC…" /><button className="primary" onClick={() => void verifyYoutube()}>Verify YouTube</button></div></section>}
        <p className="subscription-note" role="status">{checkoutNotice ? `${selectedPlan} ${billing} selected for ${selectedRole === 'content_creator' ? 'content creator' : 'game developer'}. ${selectedRole === 'content_creator' ? 'YouTube verification is required.' : 'Premium account is active.'}` : account ? `Signed in as ${account.email}` : 'Log in or sign up before choosing a plan.'}</p>
      </section> : <div className="report-body">
        {confirmed && <GameReport key={confirmed} steamUrl={confirmed} />}
        {REPORT_PAYWALL_ENABLED && <div className="paywall-wrap"><section className="paywall"><span className="lock"><LockKeyhole size={24} /></span><p className="eyebrow">YOUR NEXT MOVE STARTS HERE</p><h2 id="paywall-title">Unlock the full picture.</h2><p className="paywall-copy">One game. One complete report.<br className="desktop-break" /> Get the insights you need, when you need them.</p><ul><li><Check size={16} />Competitor and market insights</li><li><Check size={16} />Recommended launch windows</li><li><Check size={16} />Creators matched to your niche</li></ul><div className="single-report-price"><strong>$9<span> / report</span></strong><p>One-time payment · USD · No recurring charges</p></div><button className="primary unlock" onClick={() => setCheckoutNotice(true)}>Buy my report · $9 <ArrowRight size={17} /></button><div className="subscription-alternative"><span>Need insights more often?</span><button ref={unlockButton} className="plans-link" onClick={() => openSubscription('report')}>Or buy a subscription <ArrowRight size={14} /></button></div><p className="payment-note" role="status">{checkoutNotice ? 'Checkout is coming soon. No payment was taken.' : 'Preview pricing · No payment will be taken.'}</p></section></div>}
      </div>}
      <div className="report-footer"><Check size={12} />{subscription ? 'Checkout is not connected. No payment will be taken.' : 'Premium report access · Recommendations include their evidence and data limitations.'}</div>
    </dialog>
    <dialog ref={authDialog} className="auth-dialog" aria-labelledby="auth-title">
      <button className="close auth-close" onClick={() => authDialog.current?.close()} aria-label="Close dialog"><X size={21} /></button>
      <form onSubmit={submitAuth} className="auth-form">
        <p className="eyebrow">LAUNCHPAD ACCOUNT</p>
        <h2 id="auth-title">{authMode === 'login' ? 'Log in' : 'Create your account'}</h2>
        {authMode === 'signup' && <label>Display name<input value={authName} onChange={event => setAuthName(event.target.value)} autoComplete="name" /></label>}
        <label>Email<input type="email" value={authEmail} onChange={event => setAuthEmail(event.target.value)} autoComplete="email" required /></label>
        <label>Password<input type="password" value={authPassword} onChange={event => setAuthPassword(event.target.value)} autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} required minLength={8} /></label>
        {authError && <p className="error" role="alert">{authError}</p>}
        <button className="primary unlock" type="submit" disabled={authBusy}>{authBusy ? 'Please wait…' : authMode === 'login' ? 'Log in' : 'Sign up'}</button>
        <button className="auth-switch" type="button" onClick={() => { setAuthMode(authMode === 'login' ? 'signup' : 'login'); setAuthError(''); }}>{authMode === 'login' ? 'Need an account? Sign up' : 'Already have an account? Log in'}</button>
      </form>
    </dialog>
  </div>;
}
