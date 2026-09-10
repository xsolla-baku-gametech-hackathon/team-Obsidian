import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Check, Gamepad2, Link, LockKeyhole, X } from 'lucide-react';
import GameReport from '../features/recommendations/GameReport';

// Temporary preview bypass. Restore this flag when report checkout is ready.
const REPORT_PAYWALL_ENABLED = false;

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

  useEffect(() => {
    if (subscription) subscriptionTitle.current?.focus();
  }, [subscription]);

  function openSubscription(source: 'home' | 'report') {
    setSubscriptionSource(source);
    setBilling('monthly');
    setCheckoutNotice(false);
    setSubscription(true);
    paywall.current?.showModal();
  }

  function confirm(event: FormEvent) {
    event.preventDefault();
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
      <div className="auth-actions"><button className="auth-login" type="button">Log in</button><button className="primary" type="button">Sign up</button></div>
    </header>

    <main className="landing">
      <div className="eyebrow">INDIE LAUNCH INTELLIGENCE</div>
      <h1>Your game.<br />Its next big opportunity.</h1>
      <p className="intro">Find similar games and see how your pricing compares.<br className="desktop-break" /> Start with your Steam link.</p>
      <form className="link-form" onSubmit={confirm} noValidate>
        <label htmlFor="steam-url">Your game's Steam store link</label>
        <div className={`input-row ${error ? 'invalid' : ''}`}>
          <Link size={19} aria-hidden="true" />
          <input id="steam-url" type="url" value={input} onChange={event => { setInput(event.target.value); setError(''); }} placeholder="https://store.steampowered.com/app/…" required aria-invalid={!!error} aria-describedby={error ? 'link-error' : 'link-hint'} autoComplete="url" />
          <button className="primary" type="submit">Generate report <ArrowRight size={17} /></button>
        </div>
        {error ? <p id="link-error" className="error" role="alert">{error}</p> : <p id="link-hint" className="hint">Just one link. No forms, files, or game descriptions.</p>}
      </form>
      <div className="benefits"><span>Competitor matches</span><i /><span>Price recommendations</span><i /><span>Steam market data</span></div>
      <aside className="home-subscription"><div><span className="eyebrow">LAUNCHPAD PLANS</span><h2>More games on the horizon?</h2><p>Get ongoing insights with a subscription. From $19/month.</p></div><button className="plans-link" onClick={() => openSubscription('home')}>Explore subscriptions <ArrowRight size={16} /></button></aside>
    </main>

    <footer><span>Built for independent minds.</span><span>Steam launch intelligence</span></footer>

    <dialog ref={paywall} className="report-dialog" aria-labelledby={subscription ? "subscription-title" : REPORT_PAYWALL_ENABLED ? "paywall-title" : "report-title"} onClose={() => { setCheckoutNotice(false); setSubscription(false); setConfirmed(''); }}>
      <div className="report-header"><div><span className="confirmed"><Check size={14} />{subscription ? 'Launchpad subscriptions' : 'Link format confirmed'}</span><p>{subscription ? 'Ongoing insights for your next launches' : confirmed}</p></div><button className="close" onClick={() => paywall.current?.close()} aria-label="Close dialog"><X size={21} /></button></div>
      {subscription ? <section className="subscription-screen">
        <button className="back-button" onClick={() => { if (subscriptionSource === 'home') { paywall.current?.close(); } else { setSubscription(false); setCheckoutNotice(false); requestAnimationFrame(() => unlockButton.current?.focus()); } }}><ArrowLeft size={15} /> {subscriptionSource === 'home' ? 'Back to home' : 'Back to single report'}</button>
        <div className="subscription-heading"><p className="eyebrow">INVEST IN YOUR NEXT MOVE</p><h2 id="subscription-title" ref={subscriptionTitle} tabIndex={-1}>A plan for every next launch.</h2><p>For studios, teams, and developers who want insights more often.</p></div>
        <fieldset className="billing-options plan-billing"><legend>Choose your billing cycle</legend>{(['monthly', 'yearly'] as const).map(cycle => <label key={cycle} className={billing === cycle ? 'selected' : ''}><input type="radio" name="billing" checked={billing === cycle} onChange={() => { setBilling(cycle); setCheckoutNotice(false); }} /><span>{cycle === 'monthly' ? 'Monthly' : 'Yearly'}</span>{cycle === 'yearly' && <small>Save 20%</small>}</label>)}</fieldset>
        <div className="subscription-plans">
          {[
            { name: 'Starter', price: 19, reports: 3, badge: 'For solo developers', description: 'Keep a close eye on your next launch.' },
            { name: 'Pro', price: 39, reports: 10, badge: 'For growing teams', description: 'Compare opportunities across more games.' },
            { name: 'Studio', price: 79, reports: 30, badge: 'For studios', description: 'Support a larger portfolio of launches.' },
          ].map(plan => <article key={plan.name} className={`subscription-card ${plan.name === 'Pro' ? 'annual-plan' : ''}`}>
            <div className="plan-heading"><h3 className="plan-name">{plan.name}</h3><span className="plan-badge">{plan.badge}</span></div>
            <p className="plan-description">{plan.description}</p>
            <p className="plan-price">${billing === 'monthly' ? plan.price : (plan.price * 0.8).toFixed(2)}<span> / month</span></p>
            <p className="billing-detail">{billing === 'monthly' ? `$${plan.price} billed monthly · Renews monthly` : `$${(plan.price * 12 * 0.8).toFixed(2)} billed yearly · Renews yearly`} · USD</p>
            <ul className="plan-features">{[`${plan.reports} full reports per month`, 'Competitor and market insights', 'Recommended launch windows', 'Creators matched to your niche'].map(feature => <li key={feature}><Check size={17} />{feature}</li>)}</ul>
            <p className="plan-allowance">Report allowance resets monthly. Unused reports do not roll over.</p>
            <button className="primary unlock" onClick={() => { setSelectedPlan(plan.name); setCheckoutNotice(true); }}>Choose {plan.name} <ArrowRight size={17} /></button>
          </article>)}
        </div>
        <p className="subscription-note" role="status">{checkoutNotice ? `${selectedPlan} ${billing} checkout is coming soon. No payment was taken.` : 'Preview pricing · Checkout is not connected yet.'}</p>
      </section> : <div className="report-body">
        {confirmed && <GameReport key={confirmed} steamUrl={confirmed} />}
        {REPORT_PAYWALL_ENABLED && <div className="paywall-wrap"><section className="paywall"><span className="lock"><LockKeyhole size={24} /></span><p className="eyebrow">YOUR NEXT MOVE STARTS HERE</p><h2 id="paywall-title">Unlock the full picture.</h2><p className="paywall-copy">One game. One complete report.<br className="desktop-break" /> Get the insights you need, when you need them.</p><ul><li><Check size={16} />Competitor and market insights</li><li><Check size={16} />Recommended launch windows</li><li><Check size={16} />Creators matched to your niche</li></ul><div className="single-report-price"><strong>$9<span> / report</span></strong><p>One-time payment · USD · No recurring charges</p></div><button className="primary unlock" onClick={() => setCheckoutNotice(true)}>Buy my report · $9 <ArrowRight size={17} /></button><div className="subscription-alternative"><span>Need insights more often?</span><button ref={unlockButton} className="plans-link" onClick={() => openSubscription('report')}>Or buy a subscription <ArrowRight size={14} /></button></div><p className="payment-note" role="status">{checkoutNotice ? 'Checkout is coming soon. No payment was taken.' : 'Preview pricing · No payment will be taken.'}</p></section></div>}
      </div>}
      <div className="report-footer"><Check size={12} />{subscription ? 'Checkout is not connected. No payment will be taken.' : 'Free report access · Recommendations include their evidence and data limitations.'}</div>
    </dialog>
  </div>;
}
