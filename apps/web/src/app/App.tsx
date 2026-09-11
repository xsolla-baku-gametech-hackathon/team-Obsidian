import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import type { ReactNode } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  CalendarDays,
  Check,
  CreditCard,
  FileText,
  Gamepad2,
  KeyRound,
  LayoutDashboard,
  Link,
  LockKeyhole,
  LogOut,
  Search,
  ShieldCheck,
  Store,
  User,
  X,
  Youtube,
} from 'lucide-react';
import GameReport, { ReportView } from '../features/recommendations/GameReport';
import { api, ACCESS_TOKEN_KEY } from '../lib/api/client';
import { formatDate, money, prettyPlan, prettyRole } from '../lib/format';
import { steamLink } from '../lib/steam';
import type {
  Account,
  AuthSession,
  KeyRequest,
  OwnershipApplication,
  Page,
  PlanName,
  PublishedGame,
  ReportCollection,
  ReportSummary,
  SavedReport,
  UserRole,
} from '../lib/types';

// Temporary preview bypass. Restore this flag when report checkout is ready.
const REPORT_PAYWALL_ENABLED = false;

export default function App() {
  const [input, setInput] = useState('');
  const [confirmed, setConfirmed] = useState('');
  const [reportRun, setReportRun] = useState(0);
  const [earliestDate, setEarliestDate] = useState('');
  const [latestDate, setLatestDate] = useState('');
  const [reportDates, setReportDates] = useState({ earliest: '', latest: '' });
  const [error, setError] = useState('');
  const [page, setPage] = useState<Page>('dashboard');
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selectedReport, setSelectedReport] = useState<SavedReport | null>(null);
  const [reportSearch, setReportSearch] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [ownerships, setOwnerships] = useState<OwnershipApplication[]>([]);
  const [games, setGames] = useState<PublishedGame[]>([]);
  const [keyRequests, setKeyRequests] = useState<KeyRequest[]>([]);
  const [marketplaceError, setMarketplaceError] = useState('');
  const [selectedOwnershipReportId, setSelectedOwnershipReportId] = useState('');
  const [studioName, setStudioName] = useState('');
  const [applicantName, setApplicantName] = useState('');
  const [applicantTitle, setApplicantTitle] = useState('');
  const [businessEmail, setBusinessEmail] = useState('');
  const [companyWebsiteUrl, setCompanyWebsiteUrl] = useState('');
  const [officialContactUrl, setOfficialContactUrl] = useState('');
  const [steamworksProofUrl, setSteamworksProofUrl] = useState('');
  const [proofUrl, setProofUrl] = useState('');
  const [proofNotes, setProofNotes] = useState('');
  const [publishPitch, setPublishPitch] = useState('');
  const [keyMessage, setKeyMessage] = useState('');
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
  const filteredReports = reports.filter(report => `${report.game_name} ${report.steam_url}`.toLowerCase().includes(reportSearch.toLowerCase()));
  const latestReport = reports[0];

  useEffect(() => {
    if (subscription) subscriptionTitle.current?.focus();
  }, [subscription]);

  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    void api<Account>('/api/v1/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(user => {
        setAccount(user);
        if (user.subscription_status === 'active') void loadReports();
      })
      .catch(() => localStorage.removeItem(ACCESS_TOKEN_KEY));
  }, []);

  useEffect(() => {
    if (account?.subscription_status === 'active') void loadMarketplace();
  }, [account?.subscription_status, account?.premium_role]);

  async function loadReports() {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    try {
      setHistoryError('');
      const result = await api<ReportCollection>('/api/v1/reports', { headers: { Authorization: `Bearer ${token}` } });
      setReports(result.reports);
    } catch (cause) {
      setHistoryError(cause instanceof Error ? cause.message : 'Could not load reports.');
    }
  }

  async function loadMarketplace() {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    try {
      setMarketplaceError('');
      if (account?.premium_role === 'game_developer') {
        const [ownershipResult, keyResult, gamesResult] = await Promise.all([
          api<{ applications: OwnershipApplication[] }>('/api/v1/marketplace/ownership/applications', { headers: { Authorization: `Bearer ${token}` } }),
          api<{ requests: KeyRequest[] }>('/api/v1/marketplace/key-requests/incoming', { headers: { Authorization: `Bearer ${token}` } }),
          api<{ games: PublishedGame[] }>('/api/v1/marketplace/games', { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        setOwnerships(ownershipResult.applications);
        setKeyRequests(keyResult.requests);
        setGames(gamesResult.games);
      }
      if (account?.premium_role === 'content_creator') {
        const [gamesResult, keyResult] = await Promise.all([
          api<{ games: PublishedGame[] }>('/api/v1/marketplace/games', { headers: { Authorization: `Bearer ${token}` } }),
          api<{ requests: KeyRequest[] }>('/api/v1/marketplace/key-requests/mine', { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        setGames(gamesResult.games);
        setKeyRequests(keyResult.requests);
      }
    } catch (cause) {
      setMarketplaceError(cause instanceof Error ? cause.message : 'Marketplace data could not load.');
    }
  }

  async function applyOwnership(event: FormEvent) {
    event.preventDefault();
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    try {
      setMarketplaceError('');
      await api<OwnershipApplication>('/api/v1/marketplace/ownership/applications', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          report_id: Number(selectedOwnershipReportId),
          studio_name: studioName,
          applicant_name: applicantName,
          applicant_title: applicantTitle,
          business_email: businessEmail,
          company_website_url: companyWebsiteUrl || null,
          official_contact_url: officialContactUrl || null,
          steamworks_proof_url: steamworksProofUrl || null,
          proof_url: proofUrl || null,
          proof_notes: proofNotes,
        }),
      });
      setSelectedOwnershipReportId('');
      setStudioName('');
      setApplicantName('');
      setApplicantTitle('');
      setBusinessEmail('');
      setCompanyWebsiteUrl('');
      setOfficialContactUrl('');
      setSteamworksProofUrl('');
      setProofUrl('');
      setProofNotes('');
      await loadMarketplace();
    } catch (cause) {
      setMarketplaceError(cause instanceof Error ? cause.message : 'Ownership application failed.');
    }
  }

  async function publishApprovedGame(applicationId: number) {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    try {
      setMarketplaceError('');
      await api<PublishedGame>('/api/v1/marketplace/games', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          ownership_application_id: applicationId,
          pitch: publishPitch,
          contact_email: account?.email,
        }),
      });
      setPublishPitch('');
      await loadMarketplace();
    } catch (cause) {
      setMarketplaceError(cause instanceof Error ? cause.message : 'Publishing failed.');
    }
  }

  async function requestKey(gameId: number) {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    try {
      setMarketplaceError('');
      await api<KeyRequest>(`/api/v1/marketplace/games/${gameId}/key-requests`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: keyMessage }),
      });
      setKeyMessage('');
      await loadMarketplace();
    } catch (cause) {
      setMarketplaceError(cause instanceof Error ? cause.message : 'Key request failed.');
    }
  }

  async function openSavedReport(reportId: number) {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    try {
      setHistoryError('');
      const result = await api<SavedReport>(`/api/v1/reports/${reportId}`, { headers: { Authorization: `Bearer ${token}` } });
      setSelectedReport(result);
      setPage('reports');
    } catch (cause) {
      setHistoryError(cause instanceof Error ? cause.message : 'Could not open report.');
    }
  }

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
      setPage('dashboard');
      if (session.user.subscription_status === 'active') {
        void loadReports();
      } else {
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
    setReports([]);
    setSelectedReport(null);
    setConfirmed('');
    setPage('dashboard');
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
    if (updated.subscription_status === 'active') {
      paywall.current?.close();
      void loadReports();
    }
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
    paywall.current?.close();
    void loadReports();
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
    if (Boolean(earliestDate) !== Boolean(latestDate) || (earliestDate && (
      earliestDate < new Date().toISOString().slice(0, 10) ||
      (Date.parse(latestDate) - Date.parse(earliestDate)) / 86400000 < 6 ||
      (Date.parse(latestDate) - Date.parse(earliestDate)) / 86400000 > 365
    ))) {
      setError('Choose both dates, starting today or later, with a range of 7 to 366 days.');
      return;
    }
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
    setReportDates({ earliest: earliestDate, latest: latestDate });
    setReportRun(value => value + 1);
    setConfirmed(url);
    setSelectedReport(null);
    setPage('analyze');
  }

  function nav(target: Page) {
    setPage(target);
    if (target !== 'reports') setSelectedReport(null);
  }

  function renderWelcome() {
    return <main className="landing welcome">
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
    </main>;
  }

  function renderOnboarding() {
    return <main className="landing welcome"><section className="onboarding-panel">
      <p className="eyebrow">WELCOME, {account?.display_name || account?.email}</p>
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
    </section></main>;
  }

  function renderReportRows(items: ReportSummary[], compact = false) {
    if (!items.length) return <div className="empty-state"><FileText size={22} /><p>No reports yet. Run a Steam analysis and your history will appear here.</p></div>;
    return <div className={compact ? 'report-list compact' : 'report-list'}>{items.map(report => <article className="report-row" key={report.id}>
      <div><h3>{report.game_name}</h3><p>App {report.app_id} · {formatDate(report.created_at)} · {report.competitor_count} competitors</p></div>
      <div className="report-row-meta"><strong>{money(report.suggested_price_minor, report.price_currency)}</strong><span>{report.release_status.replaceAll('_', ' ')}</span></div>
      <button className="secondary" type="button" onClick={() => void openSavedReport(report.id)}>Open report</button>
    </article>)}</div>;
  }

  function renderDashboard() {
    const developer = account?.premium_role === 'game_developer';
    return <>
      <section className="dash-hero">
        <div><p className="eyebrow">COMMAND CENTER</p><h1>Welcome back, {account?.display_name || 'builder'}.</h1><p>{developer ? 'Track your reports, verify ownership, publish approved games, and review creator interest.' : 'Discover verified games from developers and track your key requests.'}</p></div>
        <button className="primary" type="button" onClick={() => nav(developer ? 'analyze' : 'marketplace')}>{developer ? 'Open Steam analysis' : 'Discover games'} <ArrowRight size={17} /></button>
      </section>
      <section className="metric-grid">
        <article><FileText size={19} /><span>Total reports</span><strong>{reports.length}</strong></article>
        <article><CreditCard size={19} /><span>Plan</span><strong>{prettyPlan(account?.subscription_plan ?? null)}</strong></article>
        <article><User size={19} /><span>Workspace</span><strong>{prettyRole(account?.premium_role ?? null)}</strong></article>
        <article><CalendarDays size={19} /><span>{developer ? 'Latest report' : 'Requests'}</span><strong>{developer ? latestReport ? formatDate(latestReport.created_at) : 'None yet' : keyRequests.length}</strong></article>
      </section>
      <section className="dashboard-grid">
        {developer ? <>
          <article className="feature-panel wide"><div><p className="eyebrow">PRIMARY TOOL</p><h2>Steam analysis</h2><p>Generate reports, then apply for ownership verification before publishing.</p></div><button className="primary" onClick={() => nav('analyze')}>Analyze a game <ArrowRight size={16} /></button></article>
          <article className="feature-panel"><h2>Ownership</h2><p>Submit proof for manual platform review. Approved games can be published.</p><button className="plans-link" onClick={() => nav('ownership')}>Verify game <ArrowRight size={14} /></button></article>
          <article className="feature-panel"><h2>Key requests</h2><p>See creator demand for your published games.</p><button className="plans-link" onClick={() => nav('keys')}>Review requests <ArrowRight size={14} /></button></article>
        </> : <>
          <article className="feature-panel wide"><div><p className="eyebrow">CREATOR ACCESS</p><h2>Discover games</h2><p>Browse verified developer listings and request keys for coverage.</p></div><button className="primary" onClick={() => nav('marketplace')}>Browse games <ArrowRight size={16} /></button></article>
          <article className="feature-panel"><h2>My requests</h2><p>Track pending and approved key requests.</p><button className="plans-link" onClick={() => nav('keys')}>Open requests <ArrowRight size={14} /></button></article>
          <article className="feature-panel"><h2>Account</h2><p>Manage your subscription and YouTube channel state.</p><button className="plans-link" onClick={() => nav('account')}>Open account <ArrowRight size={14} /></button></article>
        </>}
      </section>
      {developer && <section className="page-panel"><div className="section-heading"><h2>Recent reports</h2><button className="plans-link" onClick={() => nav('reports')}>View all <ArrowRight size={14} /></button></div>{renderReportRows(reports.slice(0, 3), true)}</section>}
    </>;
  }

  function renderAnalyzePage() {
    return <>
      <section className="page-heading"><p className="eyebrow">STEAM ANALYSIS</p><h1>Your game. Its next big opportunity.</h1><p>Paste a Steam page to generate a saved report with pricing context, competitors, and release-window evidence.</p></section>
      <section className="page-panel">
        <form className="link-form dashboard-form" onSubmit={confirm} noValidate>
          <label htmlFor="steam-url">Your game's Steam store link</label>
          <div className={`input-row ${error ? 'invalid' : ''}`}>
            <Link size={19} aria-hidden="true" />
            <input id="steam-url" type="url" value={input} onChange={event => { setInput(event.target.value); setError(''); }} placeholder="https://store.steampowered.com/app/…" required aria-invalid={!!error} aria-describedby={error ? 'link-error' : 'link-hint'} autoComplete="url" />
            <button className="primary" type="submit">Generate report <ArrowRight size={17} /></button>
          </div>
          <div className="release-range">
            <label>Earliest launch<input type="date" value={earliestDate} min={new Date().toISOString().slice(0, 10)} onChange={event => setEarliestDate(event.target.value)} /></label>
            <label>Latest launch<input type="date" value={latestDate} min={earliestDate || new Date().toISOString().slice(0, 10)} onChange={event => setLatestDate(event.target.value)} /></label>
            <p className="hint">Optional · Leave both empty to explore the next 90 days.</p>
          </div>
          {error ? <p id="link-error" className="error" role="alert">{error}</p> : <p id="link-hint" className="hint">Reports are saved automatically to My Reports.</p>}
        </form>
      </section>
      {confirmed ? <section className="page-panel report-output"><GameReport key={`${confirmed}-${reportRun}`} steamUrl={confirmed} earliestDate={reportDates.earliest} latestDate={reportDates.latest} onComplete={() => void loadReports()} /></section> : <section className="empty-state analysis-empty"><Search size={24} /><p>Generate a report to see the analysis here. Recent results will stay available from My Reports.</p></section>}
    </>;
  }

  function renderReportsPage() {
    return <>
      <section className="page-heading"><p className="eyebrow">MY REPORTS</p><h1>Every launch read, saved.</h1><p>Search your generated reports and reopen the full analysis without calling Steam again.</p></section>
      <section className="page-panel reports-layout">
        <div className="reports-list-panel">
          <div className="search-box"><Search size={17} /><input value={reportSearch} onChange={event => setReportSearch(event.target.value)} placeholder="Search by game or Steam URL" /></div>
          {historyError && <p className="error" role="alert">{historyError}</p>}
          {renderReportRows(filteredReports)}
        </div>
        <aside className="saved-report-panel">
          {selectedReport ? <ReportView data={selectedReport.payload} /> : <div className="empty-state"><FileText size={23} /><p>Select a report to preview the saved analysis here.</p></div>}
        </aside>
      </section>
    </>;
  }

  function renderOwnershipPage() {
    const approved = ownerships.filter(item => item.status === 'approved');
    return <>
      <section className="page-heading"><p className="eyebrow">OWNERSHIP REVIEW</p><h1>Verify before publishing.</h1><p>Apply for manual platform review using a report you created. Only approved games can be published to creators.</p></section>
      <section className="page-panel marketplace-layout">
        <form className="marketplace-form" onSubmit={applyOwnership}>
          <h2>Apply for verification</h2>
          <label>Report<select value={selectedOwnershipReportId} onChange={event => setSelectedOwnershipReportId(event.target.value)} required><option value="">Choose a report</option>{reports.map(report => <option key={report.id} value={report.id}>{report.game_name}</option>)}</select></label>
          <label>Studio name<input value={studioName} onChange={event => setStudioName(event.target.value)} required /></label>
          <label>Your name<input value={applicantName} onChange={event => setApplicantName(event.target.value)} required /></label>
          <label>Your role<input value={applicantTitle} onChange={event => setApplicantTitle(event.target.value)} required placeholder="Founder, producer, publisher manager" /></label>
          <label>Business email<input type="email" value={businessEmail} onChange={event => setBusinessEmail(event.target.value)} required placeholder="you@studio.com" /></label>
          <label>Company website<input type="url" value={companyWebsiteUrl} onChange={event => setCompanyWebsiteUrl(event.target.value)} placeholder="https://studio.com" /></label>
          <label>Official contact or press page<input type="url" value={officialContactUrl} onChange={event => setOfficialContactUrl(event.target.value)} placeholder="https://studio.com/press" /></label>
          <label>Steamworks proof link<input type="url" value={steamworksProofUrl} onChange={event => setSteamworksProofUrl(event.target.value)} placeholder="Private screenshot link for manual review" /></label>
          <label>Extra proof URL<input type="url" value={proofUrl} onChange={event => setProofUrl(event.target.value)} placeholder="Publisher page, trailer channel, announcement post" /></label>
          <label>Verification notes<textarea value={proofNotes} onChange={event => setProofNotes(event.target.value)} required placeholder="Explain your relationship to the game and where reviewers should compare the Steam page, website, email domain, and proof links." /></label>
          <button className="primary" type="submit">Submit for review <ShieldCheck size={16} /></button>
        </form>
        <div className="marketplace-list">
          <h2>Applications</h2>
          {marketplaceError && <p className="error" role="alert">{marketplaceError}</p>}
          {!ownerships.length && <div className="empty-state"><ShieldCheck size={22} /><p>No ownership applications yet.</p></div>}
          {ownerships.map(item => <article className="market-card" key={item.id}><h3>{item.game_name}</h3><p>{item.studio_name} · {item.applicant_title} · {item.status}</p><p>{item.business_email}</p>{item.reviewed_notes && <p>{item.reviewed_notes}</p>}</article>)}
        </div>
      </section>
      <section className="page-panel">
        <h2>Publish approved game</h2>
        {!approved.length ? <div className="empty-state"><Store size={22} /><p>No approved games yet. Platform owners must approve ownership first.</p></div> : <div className="marketplace-list">{approved.map(item => <article className="market-card" key={item.id}><h3>{item.game_name}</h3><textarea value={publishPitch} onChange={event => setPublishPitch(event.target.value)} placeholder="Creator-facing pitch" /><button className="secondary" onClick={() => void publishApprovedGame(item.id)}>Publish game</button></article>)}</div>}
      </section>
    </>;
  }

  function renderMarketplacePage() {
    const creator = account?.premium_role === 'content_creator';
    return <>
      <section className="page-heading"><p className="eyebrow">{creator ? 'DISCOVER GAMES' : 'PUBLISHED GAMES'}</p><h1>{creator ? 'Find games to cover.' : 'Creator-facing catalog.'}</h1><p>{creator ? 'Browse verified games published by developers and request access.' : 'These are the verified games visible to content creators.'}</p></section>
      <section className="page-panel">
        {marketplaceError && <p className="error" role="alert">{marketplaceError}</p>}
        {!games.length && <div className="empty-state"><Store size={22} /><p>No published games yet.</p></div>}
        <div className="marketplace-list">{games.map(game => <article className="market-card" key={game.id}><h3>{game.game_name}</h3><p>{game.pitch}</p><a href={game.steam_url} target="_blank" rel="noreferrer">Open Steam page</a>{creator && <div className="key-request-box"><textarea value={keyMessage} onChange={event => setKeyMessage(event.target.value)} placeholder="Why do you want to cover this game?" /><button className="secondary" onClick={() => void requestKey(game.id)}>Request key</button></div>}</article>)}</div>
      </section>
    </>;
  }

  function renderKeysPage() {
    return <>
      <section className="page-heading"><p className="eyebrow">KEY REQUESTS</p><h1>{account?.premium_role === 'content_creator' ? 'Your requested keys.' : 'Creator requests.'}</h1><p>{account?.premium_role === 'content_creator' ? 'Track requests you sent to developers.' : 'Review creator interest before approving keys later.'}</p></section>
      <section className="page-panel">
        {marketplaceError && <p className="error" role="alert">{marketplaceError}</p>}
        {!keyRequests.length && <div className="empty-state"><KeyRound size={22} /><p>No key requests yet.</p></div>}
        <div className="marketplace-list">{keyRequests.map(request => <article className="market-card" key={request.id}><h3>Request #{request.id}</h3><p>{request.message}</p><p>Status: {request.status}</p></article>)}</div>
      </section>
    </>;
  }

  function renderAccountPage() {
    return <>
      <section className="page-heading"><p className="eyebrow">ACCOUNT</p><h1>Your Launchpad workspace.</h1><p>Keep the account simple: login first, then plan and role. Creator verification sits here where it belongs.</p></section>
      <section className="account-grid">
        <article className="page-panel account-card"><h2>Profile</h2><dl><div><dt>Email</dt><dd>{account?.email}</dd></div><div><dt>Name</dt><dd>{account?.display_name || 'Not set'}</dd></div><div><dt>Status</dt><dd>{account?.subscription_status.replaceAll('_', ' ')}</dd></div></dl></article>
        <article className="page-panel account-card"><h2>Subscription</h2><dl><div><dt>Plan</dt><dd>{prettyPlan(account?.subscription_plan ?? null)}</dd></div><div><dt>Role</dt><dd>{prettyRole(account?.premium_role ?? null)}</dd></div><div><dt>YouTube</dt><dd>{account?.youtube_channel_id || 'Not connected'}</dd></div></dl><button className="primary" onClick={() => openSubscription('home')}>Manage plan <ArrowRight size={16} /></button></article>
      </section>
      {account?.premium_role === 'content_creator' && account.subscription_status !== 'active' && <section className="youtube-verify"><h3>Verify your YouTube channel</h3><p>Enter a channel ID for local development. Production will use Google OAuth.</p><div><input value={youtubeChannel} onChange={event => setYoutubeChannel(event.target.value)} placeholder="YouTube channel ID, e.g. UC…" /><button className="primary" onClick={() => void verifyYoutube()}>Verify YouTube</button></div></section>}
    </>;
  }

  function renderWorkspace() {
    const navItems: { id: Page; label: string; icon: ReactNode }[] = [
      { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={17} /> },
      ...(account?.premium_role === 'game_developer' ? [
        { id: 'analyze' as Page, label: 'Steam analysis', icon: <Search size={17} /> },
        { id: 'reports' as Page, label: 'My reports', icon: <FileText size={17} /> },
        { id: 'ownership' as Page, label: 'Ownership', icon: <ShieldCheck size={17} /> },
        { id: 'marketplace' as Page, label: 'Published games', icon: <Store size={17} /> },
        { id: 'keys' as Page, label: 'Key requests', icon: <KeyRound size={17} /> },
      ] : [
        { id: 'marketplace' as Page, label: 'Discover games', icon: <Store size={17} /> },
        { id: 'keys' as Page, label: 'My key requests', icon: <KeyRound size={17} /> },
      ]),
      { id: 'account', label: 'Account', icon: <User size={17} /> },
    ];
    return <main className="dashboard-shell">
      <aside className="sidebar" aria-label="Workspace navigation">
        <p className="eyebrow">WORKSPACE</p>
        <nav>{navItems.map(item => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => nav(item.id)}>{item.icon}{item.label}</button>)}</nav>
      </aside>
      <section className="dashboard-content">
        {page === 'dashboard' && renderDashboard()}
        {page === 'analyze' && renderAnalyzePage()}
        {page === 'reports' && renderReportsPage()}
        {page === 'ownership' && renderOwnershipPage()}
        {page === 'marketplace' && renderMarketplacePage()}
        {page === 'keys' && renderKeysPage()}
        {page === 'account' && renderAccountPage()}
      </section>
    </main>;
  }

  return <div className="page">
    <header className="header">
      <a className="brand" href="/" aria-label="Launchpad home"><span><img src="/launchpad-icon.png" alt="" /></span>launchpad.</a>
      <div className="auth-actions">{account ? <><button className="auth-login" type="button" onClick={() => nav('dashboard')}>Dashboard</button><button className="auth-login" type="button" onClick={() => nav(account.premium_role === 'content_creator' ? 'marketplace' : 'reports')}>{account.premium_role === 'content_creator' ? 'Discover' : 'My reports'}</button><button className="auth-login" type="button" onClick={() => nav('account')}>Account</button><span className="account-chip"><User size={15} />{account.display_name || account.email}</span><button className="auth-login" type="button" onClick={logout}>Log out <LogOut size={14} /></button></> : <><button className="auth-login" type="button" onClick={() => openAuth('login')}>Log in</button><button className="primary" type="button" onClick={() => openAuth('signup')}>Sign up</button></>}</div>
    </header>

    {!account && renderWelcome()}
    {account && !canUseReports && renderOnboarding()}
    {account && canUseReports && renderWorkspace()}

    <footer><span>Built for independent minds.</span><span>Steam launch intelligence</span></footer>

    <dialog ref={paywall} className="report-dialog" aria-labelledby={subscription ? 'subscription-title' : REPORT_PAYWALL_ENABLED ? 'paywall-title' : 'report-title'} onClose={() => { setCheckoutNotice(false); setSubscription(false); }}>
      <div className="report-header"><div><span className="confirmed"><Check size={14} />{subscription ? 'Launchpad subscriptions' : 'Link format confirmed'}</span><p>{subscription ? 'Ongoing insights for your next launches' : confirmed}</p></div><button className="close" onClick={() => paywall.current?.close()} aria-label="Close dialog"><X size={21} /></button></div>
      {subscription ? <section className="subscription-screen">
        <button className="back-button" onClick={() => { if (subscriptionSource === 'home') { paywall.current?.close(); } else { setSubscription(false); setCheckoutNotice(false); requestAnimationFrame(() => unlockButton.current?.focus()); } }}><ArrowLeft size={15} /> {subscriptionSource === 'home' ? 'Back to workspace' : 'Back to single report'}</button>
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
