import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, Check, Gamepad2, Link, LockKeyhole, X } from 'lucide-react';

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
  const [checkoutNotice, setCheckoutNotice] = useState(false);
  const paywall = useRef<HTMLDialogElement>(null);

  function confirm(event: FormEvent) {
    event.preventDefault();
    const url = steamLink(input);
    if (!url) {
      setError('Enter a Steam store game link, like https://store.steampowered.com/app/123456/');
      return;
    }
    setError('');
    setConfirmed(url);
    setCheckoutNotice(false);
    paywall.current?.showModal();
  }

  return <div className="page">
    <header className="header">
      <a className="brand" href="/" aria-label="Launchpad home"><span><Gamepad2 size={21} /></span>launchpad.</a>
      <span className="header-note">A clearer start for your next game.</span>
    </header>

    <main className="landing">
      <div className="eyebrow">INDIE LAUNCH INTELLIGENCE</div>
      <h1>Your game.<br />Its next big opportunity.</h1>
      <p className="intro">Find your market, your launch window, and your creators.<br className="desktop-break" /> Start with your Steam link.</p>
      <form className="link-form" onSubmit={confirm} noValidate>
        <label htmlFor="steam-url">Your game's Steam store link</label>
        <div className={`input-row ${error ? 'invalid' : ''}`}>
          <Link size={19} aria-hidden="true" />
          <input id="steam-url" type="url" value={input} onChange={event => { setInput(event.target.value); setError(''); }} placeholder="https://store.steampowered.com/app/…" required aria-invalid={!!error} aria-describedby={error ? 'link-error' : 'link-hint'} autoComplete="url" />
          <button className="primary" type="submit">Confirm link <ArrowRight size={17} /></button>
        </div>
        {error ? <p id="link-error" className="error" role="alert">{error}</p> : <p id="link-hint" className="hint">Just one link. No forms, files, or game descriptions.</p>}
      </form>
      <div className="benefits"><span>Market insights</span><i /><span>Launch windows</span><i /><span>Creator matches</span></div>
    </main>

    <footer><span>Built for independent minds.</span><span>Frontend preview</span></footer>

    <dialog ref={paywall} className="report-dialog" aria-labelledby="paywall-title" onClose={() => setCheckoutNotice(false)}>
      <div className="report-header"><div><span className="confirmed"><Check size={14} />Link format confirmed</span><p>{confirmed}</p></div><button className="close" onClick={() => paywall.current?.close()} aria-label="Close report"><X size={21} /></button></div>
      <div className="report-body">
        <div className="preview" aria-hidden="true">
          <h2>Your launch report</h2><p>A clearer picture of your next move.</p>
          <div className="preview-stats">{['Market opportunity', 'Best launch window', 'Matched creators'].map(title => <div key={title}><span>{title}</span><strong>•••</strong><div className="skeleton" /></div>)}</div>
          <div className="preview-panels"><div><h3>Your competitive landscape</h3><div className="chart">{[42, 76, 55, 92, 38, 61, 47, 80].map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}</div></div><div><h3>Creators for your game</h3>{[1, 2, 3].map(n => <div className="creator-placeholder" key={n}><i /><div><div className="skeleton" /><div className="skeleton short" /></div></div>)}</div></div>
        </div>
        <div className="paywall-wrap"><section className="paywall"><span className="lock"><LockKeyhole size={24} /></span><p className="eyebrow">YOUR NEXT MOVE STARTS HERE</p><h2 id="paywall-title">Unlock the full picture.</h2><p className="paywall-copy">Get the insights you need to give<br className="desktop-break" /> your game a stronger start.</p><ul><li><Check size={16} />Competitor and market insights</li><li><Check size={16} />Recommended launch windows</li><li><Check size={16} />Creators matched to your niche</li></ul><button className="primary unlock" onClick={() => setCheckoutNotice(true)}>Unlock my report <ArrowRight size={17} /></button><p className="payment-note" role="status">{checkoutNotice ? 'Paid reports are coming soon. Checkout is not available yet.' : 'Preview only · No payment will be taken.'}</p></section></div>
      </div>
      <div className="report-footer"><LockKeyhole size={12} />Illustrative preview. Game lookup and report generation are not connected yet.</div>
    </dialog>
  </div>;
}
