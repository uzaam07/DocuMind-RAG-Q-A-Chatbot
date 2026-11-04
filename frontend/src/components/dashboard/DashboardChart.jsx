import { BarChart3, CheckCircle2 } from 'lucide-react';
import { formatMs, formatPercent } from '../../lib/format.js';

const MODES = ['vector', 'hybrid', 'hybrid_rerank'];
const LABELS = { vector: 'Vector search', hybrid: 'Hybrid retrieval', hybrid_rerank: 'Hybrid + rerank' };

export default function DashboardChart({ result }) {
  const modes = MODES.filter((mode) => result?.modes?.[mode]);
  const values = modes.map((mode) => ({ mode, value: result.modes[mode].hit_at_k })).filter((item) => Number.isFinite(item.value));
  if (!values.length) return <div className="intel-empty"><BarChart3 size={20}/><span>Run the evaluation harness to compare retrieval modes here.</span></div>;
  const best = Math.max(...values.map((item) => item.value));
  const top = result.modes.hybrid_rerank;
  return (
    <>
      <div className="eval-bars">
        <div className="eval-bars__axis"><span>HIT@{result.k}</span><span>0%</span><span>50%</span><span>100%</span></div>
        {values.map(({ mode, value }) => <div className="eval-bars__row" key={mode}><span>{LABELS[mode]}</span><div className="eval-bars__track"><i style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }}/></div><strong>{formatPercent(value)}</strong>{value === best ? <CheckCircle2 size={14} className="eval-bars__best"/> : <span className="eval-bars__spacer"/>}</div>)}
      </div>
      <p className="intel-footnote">Latest offline evaluation · {result.dataset_size} questions · k = {result.k}{result.mock ? ' · mock model run' : ''}</p>
      {top ? <div className="intel-performance-strip"><div><span>TOP CONFIGURATION</span><strong>{LABELS.hybrid_rerank}</strong></div><div><span>ANSWER ACCURACY</span><strong>{formatPercent(top.answer_accuracy)}</strong></div><div><span>MEDIAN LATENCY</span><strong>{formatMs(top.latency_p50_ms)}</strong></div></div> : null}
    </>
  );
}
