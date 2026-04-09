import React, { useState } from 'react';
import { FlaskConical, Play, Loader2, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { api } from '../api/client';
import { formatPercent } from '../utils/format';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };
const thStyle: React.CSSProperties = { textAlign: 'left', padding: '8px 14px', fontFamily: 'var(--mono)', fontSize: '7.5px', textTransform: 'uppercase', letterSpacing: '2px', color: 'var(--muted)', fontWeight: 500 };

interface EvalCaseResult {
  case_id: string;
  difficulty: string;
  description: string;
  ground_truth_score: number;
  ground_truth_matches: string[];
  ground_truth_misses: string[];
  insight_score: number;
  insight_matches: string[];
  insight_misses: string[];
  hallucination_detected: boolean;
  hallucinated_numbers: string[];
  judge_score: number;
  judge_feedback: string;
  final_score: number;
  grade: string;
  ai_output_length: number;
}

interface EvalReport {
  summary: {
    total_cases: number;
    avg_score: number;
    avg_ground_truth: number;
    avg_insight: number;
    hallucination_rate: number;
    avg_judge: number;
    overall_grade: string;
    by_difficulty: Record<string, number>;
  };
  cases: EvalCaseResult[];
}

function gradeColor(grade: string): string {
  if (grade.startsWith('A')) return 'var(--emerald)';
  if (grade.startsWith('B')) return 'var(--sky)';
  if (grade.startsWith('C')) return 'var(--amber)';
  return 'var(--rose)';
}

function diffColor(diff: string): string {
  if (diff === 'easy') return 'var(--emerald)';
  if (diff === 'medium') return 'var(--amber)';
  return 'var(--rose)';
}

export default function EvalPage() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  const runAll = async () => {
    setLoading(true); setError('');
    try {
      const data = await api.evalRunAll() as EvalReport;
      setReport(data);
    } catch (err) { setError(err instanceof Error ? err.message : 'Evaluation failed'); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <FlaskConical size={20} style={{ color: 'var(--sky)' }} /> AI Evaluation
          </h1>
          <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
            Test AI reasoning quality on financial cases — ground truth, hallucination detection, judge scoring
          </p>
        </div>
        <button onClick={runAll} disabled={loading} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: loading ? 'var(--bg3)' : 'linear-gradient(135deg, var(--sky), var(--blue))',
          color: loading ? 'var(--muted)' : '#000', fontWeight: 600, padding: '8px 18px',
          borderRadius: 8, border: 'none', cursor: loading ? 'default' : 'pointer', fontSize: 12,
        }}>
          {loading ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Running Eval...</> : <><Play size={14} /> Run All Cases</>}
        </button>
      </div>

      {error && <div style={{ background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.15)', color: 'var(--rose)', fontSize: 12, borderRadius: 8, padding: '8px 14px' }}>{error}</div>}

      {/* Summary */}
      {report && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
            {[
              { label: 'Overall Grade', value: report.summary.overall_grade, color: gradeColor(report.summary.overall_grade), big: true },
              { label: 'Avg Score', value: `${report.summary.avg_score.toFixed(1)}/100`, color: 'var(--sky)' },
              { label: 'Ground Truth', value: formatPercent(report.summary.avg_ground_truth * 100), color: 'var(--emerald)' },
              { label: 'Insight Quality', value: formatPercent(report.summary.avg_insight * 100), color: 'var(--violet)' },
              { label: 'Hallucination', value: formatPercent(report.summary.hallucination_rate * 100), color: report.summary.hallucination_rate > 0.3 ? 'var(--rose)' : 'var(--emerald)' },
              { label: 'Judge Score', value: formatPercent(report.summary.avg_judge * 100), color: 'var(--amber)' },
            ].map(kpi => (
              <div key={kpi.label} style={{ ...card, padding: 14 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, textTransform: 'uppercase', letterSpacing: 2, color: 'var(--muted)', marginBottom: 4 }}>{kpi.label}</div>
                <div style={{ fontSize: kpi.big ? 28 : 18, fontWeight: 700, color: kpi.color, fontFamily: 'var(--mono)' }}>{kpi.value}</div>
              </div>
            ))}
          </div>

          {/* By difficulty */}
          {Object.keys(report.summary.by_difficulty).length > 0 && (
            <div style={{ display: 'flex', gap: 8 }}>
              {Object.entries(report.summary.by_difficulty).map(([diff, score]) => (
                <div key={diff} style={{ ...card, padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: `${diffColor(diff)}15`, color: diffColor(diff), fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>{diff}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: 'var(--heading)' }}>{score.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Case Results */}
          <div style={{ ...card, overflow: 'hidden' }}>
            <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--b1)' }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Case Results ({report.cases.length})</h3>
            </div>
            <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                  {['Case', 'Difficulty', 'GT Score', 'Insight', 'Hallucination', 'Judge', 'Final', 'Grade'].map(h => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {report.cases.map(c => (
                  <React.Fragment key={c.case_id}>
                    <tr style={{ borderBottom: '1px solid var(--b1)', cursor: 'pointer' }} onClick={() => setExpandedCase(expandedCase === c.case_id ? null : c.case_id)}>
                      <td style={{ padding: '7px 14px' }}>
                        <div style={{ color: 'var(--heading)', fontWeight: 500 }}>{c.case_id}</div>
                        <div style={{ fontSize: 9, color: 'var(--muted)' }}>{c.description}</div>
                      </td>
                      <td style={{ padding: '7px 14px' }}>
                        <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: `${diffColor(c.difficulty)}15`, color: diffColor(c.difficulty) }}>{c.difficulty}</span>
                      </td>
                      <td style={{ padding: '7px 14px', fontFamily: 'var(--mono)', color: c.ground_truth_score >= 0.8 ? 'var(--emerald)' : c.ground_truth_score >= 0.5 ? 'var(--amber)' : 'var(--rose)' }}>
                        {formatPercent(c.ground_truth_score * 100)}
                      </td>
                      <td style={{ padding: '7px 14px', fontFamily: 'var(--mono)', color: c.insight_score >= 0.8 ? 'var(--emerald)' : 'var(--amber)' }}>
                        {formatPercent(c.insight_score * 100)}
                      </td>
                      <td style={{ padding: '7px 14px', textAlign: 'center' }}>
                        {c.hallucination_detected
                          ? <XCircle size={14} style={{ color: 'var(--rose)' }} />
                          : <CheckCircle size={14} style={{ color: 'var(--emerald)' }} />
                        }
                      </td>
                      <td style={{ padding: '7px 14px', fontFamily: 'var(--mono)' }}>{formatPercent(c.judge_score * 100)}</td>
                      <td style={{ padding: '7px 14px', fontFamily: 'var(--mono)', fontWeight: 700, color: 'var(--heading)' }}>{c.final_score.toFixed(1)}</td>
                      <td style={{ padding: '7px 14px' }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: gradeColor(c.grade) }}>{c.grade}</span>
                      </td>
                    </tr>
                    {expandedCase === c.case_id && (
                      <tr key={`${c.case_id}-detail`}>
                        <td colSpan={8} style={{ padding: '12px 14px', background: 'var(--bg3)' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 11 }}>
                            <div>
                              <h4 style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>Ground Truth</h4>
                              {c.ground_truth_matches.map((m, i) => (
                                <div key={i} style={{ display: 'flex', gap: 4, marginBottom: 2 }}>
                                  <CheckCircle size={10} style={{ color: 'var(--emerald)', marginTop: 2, flexShrink: 0 }} />
                                  <span style={{ color: 'var(--emerald)' }}>{m}</span>
                                </div>
                              ))}
                              {c.ground_truth_misses.map((m, i) => (
                                <div key={i} style={{ display: 'flex', gap: 4, marginBottom: 2 }}>
                                  <XCircle size={10} style={{ color: 'var(--rose)', marginTop: 2, flexShrink: 0 }} />
                                  <span style={{ color: 'var(--rose)' }}>{m}</span>
                                </div>
                              ))}
                            </div>
                            <div>
                              <h4 style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>Insights</h4>
                              {c.insight_matches.map((m, i) => (
                                <div key={i} style={{ display: 'flex', gap: 4, marginBottom: 2 }}>
                                  <CheckCircle size={10} style={{ color: 'var(--emerald)', marginTop: 2, flexShrink: 0 }} />
                                  <span style={{ color: 'var(--emerald)' }}>{m}</span>
                                </div>
                              ))}
                              {c.insight_misses.map((m, i) => (
                                <div key={i} style={{ display: 'flex', gap: 4, marginBottom: 2 }}>
                                  <XCircle size={10} style={{ color: 'var(--rose)', marginTop: 2, flexShrink: 0 }} />
                                  <span style={{ color: 'var(--rose)' }}>{m}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div style={{ marginTop: 8 }}>
                            <h4 style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>Judge Feedback</h4>
                            <p style={{ color: 'var(--text)', lineHeight: 1.5 }}>{c.judge_feedback}</p>
                          </div>
                          {c.hallucinated_numbers.length > 0 && (
                            <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <AlertTriangle size={12} style={{ color: 'var(--rose)' }} />
                              <span style={{ fontSize: 10, color: 'var(--rose)' }}>Hallucinated numbers: {c.hallucinated_numbers.join(', ')}</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Info when no results */}
      {!report && !loading && (
        <div style={{ ...card, padding: 24, textAlign: 'center' }}>
          <FlaskConical size={40} style={{ color: 'var(--dim)', margin: '0 auto 12px' }} />
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--heading)', marginBottom: 4 }}>AI Reasoning Evaluation</h2>
          <p style={{ fontSize: 12, color: 'var(--muted)', maxWidth: 500, margin: '0 auto', lineHeight: 1.6 }}>
            Tests the AI's ability to detect hidden financial anomalies, provide deep insights,
            avoid hallucinations, and reason about financial data like a Big4 analyst.
            Click "Run All Cases" to start.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
            {['Ground Truth Matching (40%)', 'Insight Quality (30%)', 'Hallucination Check (20%)', 'LLM Judge (10%)'].map(label => (
              <span key={label} style={{ fontSize: 9, padding: '4px 8px', borderRadius: 4, background: 'var(--bg3)', color: 'var(--muted)', border: '1px solid var(--b1)' }}>{label}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
