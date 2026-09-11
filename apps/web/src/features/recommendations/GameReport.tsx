import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CalendarCheck, RefreshCw, ShieldAlert, Tag } from 'lucide-react';
import { ACCESS_TOKEN_KEY } from '../../lib/api/client';

type Profile = { app_id: number; name: string; genres: string[]; tags: string[]; description: string };
type UpcomingCompetitor = {
  app_id: number;
  name: string;
  similarity: number;
  release_date: string | null;
  release_date_raw?: string | null;
  attention_weight?: number;
  attention_reason?: string | null;
  attention_source?: string | null;
};
type ReleaseWindow = {
  start_date: string;
  end_date: string;
  rank?: number;
  competition_score?: number;
  observed_release_count?: number;
  evidence_app_ids?: number[];
  explanation: string;
};

export type Analysis = {
  game: Profile;
  target_source: string;
  upcoming_catalog?: { status: string; game_count: number; collected_at?: string; notes?: string };
  catalog: { game_count: number; dataset_id: string; future_release_count: number };
  competitors: {
    game: Profile & { release_date: string | null; review_count: number | null; peak_ccu: number | null };
    similarity: number;
    regular_price_minor: number | null;
    currency: string | null;
  }[];
  refreshed_competitor_count: number;
  earliest_date: string;
  latest_date: string;
  report: {
    competitors?: UpcomingCompetitor[];
    model_version: string;
    generated_at: string;
    recommendations: string[];
    warnings: string[];
    price: {
      status: string;
      currency: string;
      region: string;
      suggested_price_minor: number | null;
      lower_price_minor: number | null;
      upper_price_minor: number | null;
      evidence_app_ids: number[];
      explanation: string;
    };
    release: {
      status: string;
      explanation: string;
      best_date?: string | null;
      high_risk_windows?: ReleaseWindow[];
      windows: ReleaseWindow[];
    };
  };
};

function money(value: number | null, currency: string | null): string {
  return value === null || !currency
    ? 'Unavailable'
    : new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value / 100);
}

function sourceNotice(source: string): string {
  if (source === 'steam_live_metadata_only') {
    return 'Steam metadata loaded. Historical pricing comparisons are limited. Launch timing uses the upcoming calendar.';
  }
  if (source === 'downloaded_catalog') {
    return 'Steam lookup was unavailable. Showing downloaded catalog details.';
  }
  return '';
}

function shortDateRange(window?: ReleaseWindow): string {
  if (!window) return 'More evidence needed';
  return `${window.start_date} - ${window.end_date}`;
}

function releaseCountText(count?: number): string {
  if (!count) return 'no dated releases';
  return `${count} dated release${count === 1 ? '' : 's'}`;
}

function windowPressureLabel(window?: ReleaseWindow, intent: 'best' | 'backup' | 'avoid' | 'evidence' = 'evidence'): string {
  if (!window || window.competition_score === undefined) return 'Pressure score unavailable';
  const count = releaseCountText(window.observed_release_count);
  const score = window.competition_score.toFixed(window.competition_score >= 10 ? 1 : 2);

  if (window.competition_score === 0) return `Clear window: ${count} nearby.`;
  if (intent === 'best') return `Lowest-pressure option found: ${count} nearby.`;
  if (intent === 'backup') return `Backup option: ${count} nearby.`;
  if (intent === 'avoid') return `Most crowded observed window: ${count} nearby.`;
  return `Pressure score ${score} from ${count} nearby.`;
}

function cleanDescription(value: string): string {
  const text = value.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
  return text.length > 220 ? `${text.slice(0, 217)}...` : text;
}

export default function GameReport({
  steamUrl,
  earliestDate,
  latestDate,
  onComplete,
}: {
  steamUrl: string;
  earliestDate?: string;
  latestDate?: string;
  onComplete?: (data: Analysis) => void;
}) {
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
        const token = localStorage.getItem(ACCESS_TOKEN_KEY);
        if (!token) throw new Error('Log in and choose a premium plan before generating reports.');
        const response = await fetch(
          `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/steam/games/analyze`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({
              steam_url: steamUrl,
              country_code: 'US',
              earliest_date: earliestDate || undefined,
              latest_date: latestDate || undefined,
            }),
            signal: controller.signal,
          },
        );
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
        if (active) {
          setError(
            controller.signal.aborted
              ? 'The report took too long. Please try again.'
              : cause instanceof Error
                ? cause.message
                : 'Could not reach the report service.',
          );
        }
      } finally {
        window.clearTimeout(timer);
      }
    }

    void load();
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [steamUrl, earliestDate, latestDate, attempt]);

  if (error) {
    return <section className="live-report report-state">
      <h2 id="report-title">Couldn't generate your report</h2>
      <p role="alert">{error}</p>
      <button className="primary" onClick={() => setAttempt(value => value + 1)}>
        Try again <RefreshCw size={16} />
      </button>
    </section>;
  }

  if (!data) {
    return <section className="live-report report-state" aria-busy="true">
      <h2 id="report-title">Building your game's report</h2>
      <p role="status">
        Looking up your game, checking the upcoming release calendar, and finding
        historical price comparisons. This can take about 30 seconds.
      </p>
    </section>;
  }

  return <ReportView data={data} />;
}

export function ReportView({ data }: { data: Analysis }) {
  const { report } = data;
  const price = report.price;
  const notice = sourceNotice(data.target_source);
  const bestWindow = report.release.windows[0];
  const secondWindow = report.release.windows[1];
  const avoidWindow = report.release.high_risk_windows?.[0];
  const upcoming = data.upcoming_catalog ? report.competitors || [] : [];
  const dated = upcoming.filter(game => game.release_date);
  const uncertain = upcoming.filter(game => !game.release_date);
  const topUpcoming = useMemo(
    () => [...dated]
      .sort((left, right) => {
        const leftWeight = left.attention_weight ?? 1;
        const rightWeight = right.attention_weight ?? 1;
        return (right.similarity * rightWeight) - (left.similarity * leftWeight);
      })
      .slice(0, 6),
    [dated],
  );
  const topHistorical = data.competitors.slice(0, 4);
  const priceText = price.status === 'free_to_play'
    ? 'Free to play'
    : price.suggested_price_minor === null
      ? 'More evidence needed'
      : money(price.suggested_price_minor, price.currency);
  const verdict = report.release.status === 'ranked'
    ? `Best launch window: ${shortDateRange(bestWindow)}`
    : 'Release timing needs more upcoming data';

  return <section className="live-report report-focused">
    <div className="report-hero">
      <div>
        <p className="eyebrow">REPORT VERDICT</p>
        <h2 id="report-title">{data.game.name}</h2>
        <p className="game-description">{cleanDescription(data.game.description)}</p>
      </div>
      <div className="verdict-card">
        <span>{report.release.status === 'ranked' ? 'Recommended' : 'Insufficient evidence'}</span>
        <strong>{verdict}</strong>
        <small>Horizon: {data.earliest_date} - {data.latest_date}</small>
      </div>
    </div>

    <div className="game-tags">{data.game.tags.slice(0, 8).map(tag => <span key={tag}>{tag}</span>)}</div>
    {notice && <p className="report-notice">{notice}</p>}

    <section className="decision-grid" aria-label="Primary report outputs">
      <article className="decision-card primary-decision">
        <CalendarCheck size={20} />
        <span>Best window</span>
        <strong>{shortDateRange(bestWindow)}</strong>
        <p>{bestWindow ? windowPressureLabel(bestWindow, 'best') : report.release.explanation}</p>
      </article>
      <article className="decision-card danger-decision">
        <ShieldAlert size={20} />
        <span>Avoid first</span>
        <strong>{shortDateRange(avoidWindow)}</strong>
        <p>{avoidWindow ? windowPressureLabel(avoidWindow, 'avoid') : 'No major risk window found.'}</p>
      </article>
      <article className="decision-card">
        <Tag size={20} />
        <span>Suggested price</span>
        <strong>{priceText}</strong>
        <p>{price.lower_price_minor !== null
          ? `Comparable range: ${money(price.lower_price_minor, price.currency)} - ${money(price.upper_price_minor, price.currency)}`
          : price.explanation}</p>
      </article>
    </section>

    {secondWindow && <section className="next-best">
      <p className="eyebrow">BACKUP WINDOW</p>
      <strong>{shortDateRange(secondWindow)}</strong>
      <p>{windowPressureLabel(secondWindow, 'backup')}</p>
    </section>}

    <section>
      <div className="section-heading">
        <h3>Most relevant upcoming competitors</h3>
        <span>{dated.length} dated · {uncertain.length} without exact dates</span>
      </div>
      {!topUpcoming.length ? <p className="report-empty">No dated upcoming competitors were found for this horizon.</p> : <div className="priority-list">
        {topUpcoming.map(game => <article className="priority-row" key={game.app_id}>
          <div>
            <a href={`https://store.steampowered.com/app/${game.app_id}/`} target="_blank" rel="noreferrer">
              {game.name}<ArrowRight size={14} />
            </a>
            <p>{game.release_date} · {Math.round(game.similarity * 100)}% similar{(game.attention_weight ?? 1) > 1 ? ' · high attention' : ''}</p>
          </div>
          {game.attention_reason && <small>{game.attention_reason}</small>}
        </article>)}
      </div>}
    </section>

    <section>
      <div className="section-heading">
        <h3>Best historical price comparables</h3>
        <span>{data.competitors.length} matches</span>
      </div>
      {!topHistorical.length ? <p className="report-empty">No strong historical comparables were found in the catalog.</p> : <div className="compact-comparables">
        {topHistorical.map(({ game, similarity, regular_price_minor, currency }) => <article className="comparable-row" key={game.app_id}>
          <a href={`https://store.steampowered.com/app/${game.app_id}/`} target="_blank" rel="noreferrer">{game.name}</a>
          <span>{Math.round(similarity * 100)}% similar</span>
          <strong>{money(regular_price_minor, currency)}</strong>
        </article>)}
      </div>}
    </section>

    <section className="action-panel">
      <h3>Recommended next moves</h3>
      <ul className="report-recommendations">{report.recommendations.slice(0, 3).map(item => <li key={item}>{item}</li>)}</ul>
    </section>

    <details className="report-evidence">
      <summary>Full evidence and limitations</summary>
      <div className="evidence-grid">
        {report.release.windows.map(window => <article className="advice-card" key={window.start_date}>
          <h3>{window.rank ? `Window #${window.rank}` : 'Release window'}</h3>
          <strong>{shortDateRange(window)}</strong>
          <p>{windowPressureLabel(window)}</p>
          <p>{window.explanation}</p>
        </article>)}
        {report.release.high_risk_windows?.map(window => <article className="advice-card" key={`risk-${window.start_date}`}>
          <h3>High-risk window</h3>
          <strong>{shortDateRange(window)}</strong>
          <p>{windowPressureLabel(window)}</p>
          <p>{window.evidence_app_ids?.map(id => upcoming.find(game => game.app_id === id)?.name || `Steam app ${id}`).slice(0, 8).join(', ')}</p>
        </article>)}
      </div>
      {uncertain.length > 0 && <p>
        {uncertain.length} upcoming games have no exact release date yet. They are not assigned
        invented dates and may change this report when their dates become known.
      </p>}
      <ul>{report.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
      <p>
        Upcoming dataset: {data.upcoming_catalog?.status === 'ready' ? data.upcoming_catalog.collected_at : 'Unavailable or stale'} ·
        Historical dataset: {data.catalog.dataset_id} · Model: {report.model_version} ·
        Generated: {new Date(report.generated_at).toLocaleString()}
      </p>
    </details>
  </section>;
}
