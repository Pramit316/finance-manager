import React, { useEffect, useState } from 'react';
import { FileText, CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-react';

const API = 'http://localhost:8000';

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  IMPORTED: { icon: <CheckCircle size={16} />, color: '#10b981', label: 'Imported' },
  NEEDS_REVIEW: { icon: <AlertTriangle size={16} />, color: '#f59e0b', label: 'Needs Review' },
  FAILED: { icon: <XCircle size={16} />, color: '#ef4444', label: 'Failed' },
  PARSING: { icon: <Clock size={16} />, color: '#3b82f6', label: 'Parsing' },
  VALIDATING: { icon: <Clock size={16} />, color: '#3b82f6', label: 'Validating' },
  PENDING: { icon: <Clock size={16} />, color: '#6b7280', label: 'Pending' },
  READY: { icon: <Clock size={16} />, color: '#6b7280', label: 'Ready' },
};

const RECON_CONFIG: Record<string, { color: string; label: string }> = {
  PASSED: { color: '#10b981', label: '✓ Balanced' },
  FAILED: { color: '#ef4444', label: '✗ Unbalanced' },
  NOT_AVAILABLE: { color: '#6b7280', label: 'N/A' },
  PENDING: { color: '#6b7280', label: 'Pending' },
};

const fmt = (n: number | string | null | undefined) => {
  if (n == null) return '—';
  return new Intl.NumberFormat('en-NP', { minimumFractionDigits: 2 }).format(parseFloat(String(n)));
};

interface ImportRecord {
  import_id: string;
  source: string;
  status: string;
  filename: string;
  period_from: string | null;
  period_to: string | null;
  opening_balance: string | null;
  closing_balance: string | null;
  currency: string | null;
  rows_read: number;
  rows_inserted: number;
  duplicate_rows: number;
  total_debit: string | null;
  total_credit: string | null;
  reconciliation_status: string;
  reconciliation_difference: string | null;
  error_message: string | null;
  created_at: string;
}

export const Imports: React.FC = () => {
  const [imports, setImports] = useState<ImportRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/imports/`)
      .then(r => r.json())
      .then(data => setImports(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2>Statement Imports</h2>
          <p className="page-subtitle">{imports.length} statement{imports.length !== 1 ? 's' : ''} imported</p>
        </div>
      </div>

      {loading ? (
        <div className="table-loading"><div className="loader" style={{ width: 36, height: 36 }} /></div>
      ) : imports.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
          <FileText size={48} style={{ marginBottom: '1rem', opacity: 0.4 }} />
          <p>No statements imported yet. <a href="/upload" style={{ color: 'var(--accent-primary)' }}>Upload one</a> to get started.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {imports.map(imp => {
            const status = STATUS_CONFIG[imp.status] || STATUS_CONFIG.PENDING;
            const recon = RECON_CONFIG[imp.reconciliation_status] || RECON_CONFIG.PENDING;
            const isOpen = expanded === imp.import_id;

            return (
              <div key={imp.import_id} className="card import-card">
                {/* Summary row */}
                <div
                  className="import-header"
                  onClick={() => setExpanded(isOpen ? null : imp.import_id)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="import-icon">
                    <FileText size={20} />
                  </div>

                  <div className="import-info">
                    <div className="import-filename">{imp.filename}</div>
                    <div className="import-meta">
                      <span className="source-badge">{imp.source}</span>
                      {imp.period_from && (
                        <span>{imp.period_from} → {imp.period_to}</span>
                      )}
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        {new Date(imp.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>

                  <div className="import-stats">
                    <div className="import-stat">
                      <span className="stat-num">{imp.rows_inserted}</span>
                      <span className="stat-lbl">added</span>
                    </div>
                    <div className="import-stat">
                      <span className="stat-num">{imp.duplicate_rows}</span>
                      <span className="stat-lbl">dupes</span>
                    </div>
                  </div>

                  <div className="import-badges">
                    <span className="status-badge" style={{ color: status.color, borderColor: `${status.color}44`, backgroundColor: `${status.color}11` }}>
                      {status.icon} {status.label}
                    </span>
                    <span className="recon-badge" style={{ color: recon.color }}>
                      {recon.label}
                    </span>
                  </div>

                  <div className="import-chevron" style={{ color: 'var(--text-secondary)' }}>
                    {isOpen ? '▲' : '▼'}
                  </div>
                </div>

                {/* Expanded detail */}
                {isOpen && (
                  <div className="import-detail">
                    <div className="import-detail-grid">
                      <div>
                        <div className="detail-label">Opening Balance</div>
                        <div className="detail-value">{fmt(imp.opening_balance)} {imp.currency}</div>
                      </div>
                      <div>
                        <div className="detail-label">Closing Balance</div>
                        <div className="detail-value">{fmt(imp.closing_balance)} {imp.currency}</div>
                      </div>
                      <div>
                        <div className="detail-label">Total Credits</div>
                        <div className="detail-value positive">+{fmt(imp.total_credit)} {imp.currency}</div>
                      </div>
                      <div>
                        <div className="detail-label">Total Debits</div>
                        <div className="detail-value negative">-{fmt(imp.total_debit)} {imp.currency}</div>
                      </div>
                      <div>
                        <div className="detail-label">Rows Read</div>
                        <div className="detail-value">{imp.rows_read}</div>
                      </div>
                      {imp.reconciliation_difference != null && parseFloat(imp.reconciliation_difference) !== 0 && (
                        <div>
                          <div className="detail-label">Reconciliation Difference</div>
                          <div className="detail-value negative">{fmt(imp.reconciliation_difference)} {imp.currency}</div>
                        </div>
                      )}
                    </div>
                    {imp.error_message && (
                      <div className="import-error">
                        <AlertTriangle size={14} /> {imp.error_message}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
