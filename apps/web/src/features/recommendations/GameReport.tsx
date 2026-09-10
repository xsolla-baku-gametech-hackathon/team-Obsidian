import { useEffect, useState } from 'react';
import { ArrowRight, RefreshCw } from 'lucide-react';

type Profile = { app_id: number; name: string; genres: string[]; tags: string[]; description: string };
type Analysis = {
  game: Profile;
  target_source: string;
  catalog: { game_count: number; dataset_id: string; future_release_count: number };
  competitors: {
    game: Profile & { release_date: string | null; review_count: number | null; peak_ccu: number | null };
    similarity: number; regular_price_minor: number | null; currency: string | null;
  }[];
  refreshed_competitor_count: number;
  earliest_date: string;
  latest_date: string;
  report: {
    model_version: string; generated_at: string; recommendations: string[]; warnings: string[];
    price: {
      status: string; currency: string; region: string; suggested_price_minor: number | null;
      lower_price_minor: number | null; upper_price_minor: number | null;
      evidence_app_ids: number[]; explanation: string;
    };
    release: {
      status: string; explanation: string;
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
    return 'Steam metadata loaded. Import the local catalog to unlock competitor matching and price comparisons.';
  }
  if (source === 'downloaded_catalog') {
    return 'Steam lookup was unavailable. Showing your game’s downloaded catalog details.';
  }
  return '';
}

function genreList(genres: string[]): string {
  return genres.length ? genres.join(', ') : 'Unknown genre';
}

export default function GameReport({ steamUrl }: { steamUrl: string }) {
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
        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/steam/games/analyze`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ steam_url: steamUrl, country_code: 'US' }), signal: controller.signal,
        });
        if (!response.headers.get('content-type')?.includes('application/json')) {
          throw new Error('The report service is unavailable. Start the API and try again.');
        }
        const result = await response.json();
        if (!response.ok) throw new Error(result.error?.message || 'Could not generate this report.');
        if (!result.game || !result.report || !Array.isArray(result.competitors)) {
          throw new Error('The report service returned an incomplete response. Please try again.');
        }
        if (active) setData(result);
      } catch (cause) {
        if (active) setError(controller.signal.aborted
          ? 'The report took too long. Please try again.'
          : cause instanceof Error ? cause.message : 'Could not reach the report service.');
      } finally { window.clearTimeout(timer); }
    }
    void load();
    return () => { active = false; window.clearTimeout(timer); controller.abort(); };
  }, [steamUrl, attempt]);

  if (error) return <section className="live-report report-state">
    <h2 id="report-title">Couldn’t generate your report</h2><p role="alert">{error}</p>
    <button className="primary" onClick={() => setAttempt(value => value + 1)}>Try again <RefreshCw size={16} /></button>
  </section>;

  if (!data) return <section className="live-report report-state" aria-busy="true">
    <h2 id="report-title">Building your game’s report</h2>
    <p role="status">Looking up your game, finding similar titles, and checking current Steam prices. This can take about 30 seconds.</p>
  </section>;

  const { report } = data;
  const price = report.price;
  const notice = sourceNotice(data.target_source);
  const isFreeToPlay = price.status === 'free_to_play';
  const metadataOnly = data.target_source === 'steam_live_metadata_only';
  if (metadataOnly) return <section className="live-report metadata-only-report">
    <p className="eyebrow">STEAM PAGE FOUND</p>
    <h2 id="report-title">{data.game.name}</h2>
    <p className="game-description">{data.game.description.replace(/<[^>]*>/g, '')}</p>
    <div className="metadata-facts">
      <div><dt>Genres</dt><dd>{genreList(data.game.genres)}</dd></div>
      <div><dt>Business model</dt><dd>{isFreeToPlay ? 'Free to play' : 'Premium or paid'}</dd></div>
      <div><dt>Catalog games loaded</dt><dd>0</dd></div>
    </div>
    <div className="setup-notice">
      <h3>Catalog database is missing</h3>
      <p>Steam metadata loaded correctly, but competitor matching, price comparison, and launch-window advice need the local Steam catalog database. Right now the app only knows about the submitted Steam page.</p>
      <code>python -m ili_pipeline.catalog</code>
    </div>
    <div className="advice-grid">
      <article className="advice-card"><h3>Suggested price</h3>
        <strong className="advice-value">{isFreeToPlay ? 'Free to play' : 'Not enough data'}</strong>
        <p>{price.explanation}</p>
      </article>
      <article className="advice-card"><h3>Release timing</h3>
        <strong className="advice-value">Not enough data</strong>
        <p>We need a catalog of similar released and upcoming games before this can recommend a launch window.</p>
      </article>
    </div>
  </section>;

  return <section className="live-report">
    <p className="eyebrow">YOUR GAME · YOUR MARKET</p>
    <h2 id="report-title">{data.game.name}</h2>
    <p className="game-description">{data.game.description.replace(/<[^>]*>/g, '')}</p>
    <div className="game-tags">{data.game.tags.slice(0, 8).map(tag => <span key={tag}>{tag}</span>)}</div>
    <p className="data-caption">Compared against {data.catalog.game_count.toLocaleString()} catalog games · {data.refreshed_competitor_count} competitor records refreshed from Steam · Prices: US market</p>
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
          <p>{data.catalog.future_release_count === 0 ? 'Your downloaded catalog contains no future release dates.' : 'This catalog does not establish complete upcoming-release coverage.'} We can identify competitors, but cannot reliably pick a quiet launch window from this download.</p>
        </>}
        <small>Requested horizon: {data.earliest_date} – {data.latest_date}</small>
      </article>
    </div>

    <div className="section-heading"><h3>Your competitive landscape</h3><span>{data.competitors.length} matches</span></div>
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
      <p>Dataset: {data.catalog.dataset_id} · Model: {report.model_version} · Generated: {new Date(report.generated_at).toLocaleString()}</p>
    </details>
  </section>;
}
