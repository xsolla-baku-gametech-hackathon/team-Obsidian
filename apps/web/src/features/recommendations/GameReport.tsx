import { useEffect, useState } from 'react';
import { ArrowRight, RefreshCw } from 'lucide-react';

type Profile = { app_id: number; name: string; genres: string[]; tags: string[]; description: string };
export type Analysis = {
  game: Profile;
  target_source: string;
  upcoming_catalog?: { status: string; game_count: number; collected_at?: string; notes?: string };
  catalog: { game_count: number; dataset_id: string; future_release_count: number };
  competitors: {
    game: Profile & { release_date: string | null; review_count: number | null; peak_ccu: number | null };
    similarity: number; regular_price_minor: number | null; currency: string | null;
  }[];
  refreshed_competitor_count: number;
  earliest_date: string;
  latest_date: string;
  report: {
    competitors?: { app_id: number; name: string; similarity: number; release_date: string | null; release_date_raw?: string | null; attention_weight?: number; attention_reason?: string | null; attention_source?: string | null }[];
    model_version: string; generated_at: string; recommendations: string[]; warnings: string[];
    price: {
      status: string; currency: string; region: string; suggested_price_minor: number | null;
      lower_price_minor: number | null; upper_price_minor: number | null;
      evidence_app_ids: number[]; explanation: string;
    };
    release: {
      status: string; explanation: string;
      high_risk_windows?: { start_date: string; end_date: string; competition_score: number; evidence_app_ids: number[]; explanation: string }[];
      windows: { start_date: string; end_date: string; explanation: string }[];
    };
  };
};

function money(value: number | null, currency: string | null): string {
  return value === null || !currency ? 'Unavailable' : new Intl.NumberFormat(undefined, {
    style: 'currency', currency,
  }).format(value / 100);
}

function sourceNotice(source: string): string {
  if (source === 'steam_live_metadata_only') {
    return 'Steam metadata loaded. Historical pricing comparisons are unavailable. Launch timing uses the separate upcoming calendar.';
  }
  if (source === 'downloaded_catalog') {
    return 'Steam lookup was unavailable. Showing your game’s downloaded catalog details.';
  }
  return '';
}

export default function GameReport({ steamUrl, earliestDate, latestDate, onComplete }: { steamUrl: string; earliestDate?: string; latestDate?: string; onComplete?: (data: Analysis) => void }) {
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort('timeout'), 90000);
    let active = true;
    setData(null);
    setError('');
    async function load() {
      try {
        const token = localStorage.getItem('launchpad_access_token');
        if (!token) throw new Error('Log in and choose a premium plan before generating reports.');
        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/steam/games/analyze`, {
          method: 'POST', headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ steam_url: steamUrl, country_code: 'US', earliest_date: earliestDate || undefined, latest_date: latestDate || undefined }), signal: controller.signal,
        });
        if (!response.headers.get('content-type')?.includes('application/json')) {
          throw new Error('The report service is unavailable. Start the API and try again.');
        }
        const result = await response.json();
        if (!response.ok) throw new Error(result.error?.message || 'Could not generate this report.');
        if (!result.game || !result.report || !Array.isArray(result.competitors)) {
          throw new Error('The report service returned an incomplete response. Please try again.');
        }
        if (active) {
          setData(result);
          onComplete?.(result);
        }
      } catch (cause) {
        if (active) setError(controller.signal.aborted
          ? 'The report took too long. Please try again.'
          : cause instanceof Error ? cause.message : 'Could not reach the report service.');
      } finally { window.clearTimeout(timer); }
    }
    void load();
    return () => { active = false; window.clearTimeout(timer); controller.abort(); };
  }, [steamUrl, earliestDate, latestDate, attempt]);

  if (error) return <section className="live-report report-state">
    <h2 id="report-title">Couldn’t generate your report</h2><p role="alert">{error}</p>
    <button className="primary" onClick={() => setAttempt(value => value + 1)}>Try again <RefreshCw size={16} /></button>
  </section>;

  if (!data) return <section className="live-report report-state" aria-busy="true">
    <h2 id="report-title">Building your game’s report</h2>
    <p role="status">Looking up your game, checking the upcoming release calendar, and finding historical price comparisons. This can take about 30 seconds.</p>
  </section>;

  return <ReportView data={data} />;
}

export function ReportView({ data }: { data: Analysis }) {
  const { report } = data;
  const price = report.price;
  const notice = sourceNotice(data.target_source);
  const isFreeToPlay = price.status === 'free_to_play';
  const upcoming = data.upcoming_catalog ? report.competitors || [] : [];
  const dated = upcoming.filter(game => game.release_date);
  const uncertain = upcoming.filter(game => !game.release_date);
  return <section className="live-report">
    <p className="eyebrow">YOUR GAME · YOUR MARKET</p>
    <h2 id="report-title">{data.game.name}</h2>
    <p className="game-description">{data.game.description.replace(/<[^>]*>/g, '')}</p>
    <div className="game-tags">{data.game.tags.slice(0, 8).map(tag => <span key={tag}>{tag}</span>)}</div>
    <p className="data-caption">Compared against {data.catalog.game_count.toLocaleString()} catalog games · {data.refreshed_competitor_count} historical records refreshed from Steam · Prices: US market</p>
    <p className="data-caption">Upcoming calendar: {data.upcoming_catalog?.game_count.toLocaleString() ?? 'Unavailable'} games{data.upcoming_catalog?.collected_at ? ` · Updated ${new Date(data.upcoming_catalog.collected_at).toLocaleString()}` : ''}</p>
    {notice && <p className="report-notice">{notice}</p>}

    <div className="advice-grid">
      <article className="advice-card"><h3>Suggested price</h3>
        <strong className="advice-value">{isFreeToPlay ? 'Free to play' : price.suggested_price_minor === null ? 'More evidence needed' : money(price.suggested_price_minor, price.currency)}</strong>
        {!isFreeToPlay && price.lower_price_minor !== null && <p>Comparable range: {money(price.lower_price_minor, price.currency)} – {money(price.upper_price_minor, price.currency)}</p>}
        <p>{price.explanation}</p><small>{price.evidence_app_ids.length} pricing comparables · {price.region} / {price.currency}</small>
      </article>
      <article className="advice-card"><h3>Release timing</h3>
        {report.release.status === 'ranked' ? report.release.windows.map(window => <div key={window.start_date}><strong>{window.start_date} – {window.end_date}</strong><p>{window.explanation}</p></div>) : <>
          <strong className="advice-value">Upcoming release data needed</strong>
          <p>{report.release.explanation}</p>
        </>}
        {report.release.status === 'ranked' && <p className="data-caption">{report.release.explanation}</p>}
        <small>Requested horizon: {data.earliest_date} – {data.latest_date}</small>
      </article>
    </div>

    <div className="section-heading"><h3>Upcoming launch competitors</h3><span>{dated.length} dated · {uncertain.length} awaiting dates</span></div>
    <p className="data-caption">Future releases in your planning horizon. High-attention titles can affect other genres too. Rankings describe known dates, not guaranteed launch success.</p>
    {!dated.length ? <p>No dated upcoming competitors are available for this horizon.</p> : <div className="competitor-grid">
      {dated.slice(0, 30).map(game => <article className="competitor-card" key={game.app_id}>
        <a href={`https://store.steampowered.com/app/${game.app_id}/`} target="_blank" rel="noreferrer">{game.name}<ArrowRight size={15} /></a>
        <p>{game.release_date} · {Math.round(game.similarity * 100)}% feature similarity</p>
        {game.attention_reason && <p className="price-evidence">{game.attention_reason}</p>}
        {game.attention_source && <a href={game.attention_source} target="_blank" rel="noreferrer">Attention evidence</a>}
      </article>)}
    </div>}
    {dated.length > 30 && <p className="data-caption">Showing the first 30 dated competitors; scoring includes the full calendar.</p>}
    {uncertain.length > 0 && <details className="report-evidence"><summary>Dates still to be announced ({uncertain.length})</summary><p>These releases are not assigned an invented date. They may change the recommendation when their dates become known.</p><ul>{uncertain.slice(0, 30).map(game => <li key={game.app_id}>{game.name} — {game.release_date_raw || 'To be announced'}</li>)}</ul></details>}
    {!!report.release.high_risk_windows?.length && <>
      <h3>High-risk launch windows</h3>
      <div className="advice-grid">{report.release.high_risk_windows.map(window => <article className="advice-card" key={window.start_date}>
        <strong>{window.start_date} – {window.end_date}</strong><p>Competition pressure: {window.competition_score.toFixed(2)}</p>
        <p>{window.explanation}</p><p>{window.evidence_app_ids.map(id => upcoming.find(game => game.app_id === id)?.name || `Steam app ${id}`).slice(0, 8).join(', ')}</p>
      </article>)}</div>
    </>}
    <div className="section-heading"><h3>Historical pricing and similarity comparables</h3><span>{data.competitors.length} matches</span></div>
    <p className="data-caption">Similarity measures shared game features, not success probability. Review and peak-player counts are historical catalog values.</p>
    {data.competitors.length === 0 ? <p>No sufficiently similar games were found in the catalog.</p> : <div className="competitor-grid">
      {data.competitors.map(({ game, similarity, regular_price_minor, currency }) => <article className="competitor-card" key={game.app_id}>
        <a href={`https://store.steampowered.com/app/${game.app_id}/`} target="_blank" rel="noreferrer">{game.name}<ArrowRight size={15} /></a>
        <p>{Math.round(similarity * 100)}% feature similarity · {game.release_date || 'Release date unknown'}</p>
        <div className="game-tags">{game.tags.filter(tag => data.game.tags.includes(tag)).slice(0, 4).map(tag => <span key={tag}>{tag}</span>)}</div>
        <dl><div><dt>Regular price</dt><dd>{money(regular_price_minor, currency)}</dd></div><div><dt>Catalog reviews</dt><dd>{game.review_count?.toLocaleString() ?? 'Unknown'}</dd></div><div><dt>Catalog peak players</dt><dd>{game.peak_ccu?.toLocaleString() ?? 'Unknown'}</dd></div></dl>
        {price.evidence_app_ids.includes(game.app_id) && <small className="price-evidence">Used in price comparison</small>}
      </article>)}
    </div>}
    <h3>Next steps for your game</h3>
    <ul className="report-recommendations">{report.recommendations.map(item => <li key={item}>{item}</li>)}</ul>
    <details className="report-evidence"><summary>Data sources and limitations</summary>
      <ul>{report.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
      <p>Upcoming dataset: {data.upcoming_catalog?.status === 'ready' ? data.upcoming_catalog.collected_at : 'Unavailable or stale'} · Historical dataset: {data.catalog.dataset_id} · Model: {report.model_version} · Generated: {new Date(report.generated_at).toLocaleString()}</p>
    </details>
  </section>;
}
