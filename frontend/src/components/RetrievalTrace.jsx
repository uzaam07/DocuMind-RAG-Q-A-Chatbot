import { ArrowRight } from 'lucide-react';

const FUNNEL = [
  ['retrieved', 'retrieved'],
  ['fused', 'fused'],
  ['reranked', 'reranked'],
  ['used', 'used'],
];
const STAGES = ['embed', 'retrieve', 'rerank', 'generate'];

/** Built only from the real `done` payload. Nothing here is estimated. */
export default function RetrievalTrace({ meta }) {
  const total = Math.max(1, meta.timings.total_ms);
  return (
    <section className="trace" aria-labelledby="trace-title">
      <h3 id="trace-title" className="trace__title">Retrieval trace</h3>
      <dl className="trace__facts">
        <div>
          <dt>mode</dt>
          <dd>{meta.mode}</dd>
        </div>
        <div>
          <dt>cache</dt>
          <dd>{meta.cached ? 'hit' : 'miss'}</dd>
        </div>
      </dl>
      <p className="trace__funnel">
        {FUNNEL.map(([key, label], index) => (
          <span key={key} className="trace__step">
            {index > 0 ? <ArrowRight size={12} strokeWidth={1.5} aria-label="to" role="img" /> : null}
            <span>
              {label} <b className="num">{meta.counts[key]}</b>
            </span>
          </span>
        ))}
      </p>
      {meta.rewritten_question ? (
        <p className="trace__rewrite">
          <span>rewritten</span> {meta.rewritten_question}
        </p>
      ) : null}
      <ul className="trace__latency" aria-label="Latency per stage in milliseconds">
        {STAGES.map((stage) => {
          const value = meta.timings[`${stage}_ms`];
          return (
            <li key={stage}>
              <span className="trace__stage">{stage}</span>
              <span className="num">{value}</span>
              <span className="meter" aria-hidden="true"><span style={{ '--v': Math.min(1, value / total) }} /></span>
            </li>
          );
        })}
        <li data-total>
          <span className="trace__stage">total</span>
          <span className="num">{meta.timings.total_ms}</span>
          <span className="meter" aria-hidden="true"><span style={{ '--v': 1 }} /></span>
        </li>
      </ul>
    </section>
  );
}
