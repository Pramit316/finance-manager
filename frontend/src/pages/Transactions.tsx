import React, { useEffect, useState, useCallback } from 'react';
import { Search, Filter, ChevronLeft, ChevronRight, Edit2, Check, X, Plus } from 'lucide-react';
import { API } from '../config';
import { authFetch } from '../lib/api';

const KIND_COLORS: Record<string, string> = {
  EXPENSE: '#ef4444',
  INCOME: '#10b981',
  INTERNAL_TRANSFER: '#8b5cf6',
  REFUND: '#06b6d4',
  BANK_FEE: '#f59e0b',
  INTEREST: '#3b82f6',
  TAX: '#f97316',
  UNKNOWN: '#6b7280',
};

const KIND_LABELS: Record<string, string> = {
  EXPENSE: 'Expense',
  INCOME: 'Income',
  INTERNAL_TRANSFER: 'Transfer',
  REFUND: 'Refund',
  BANK_FEE: 'Bank Fee',
  INTEREST: 'Interest',
  TAX: 'Tax',
  UNKNOWN: 'Unknown',
};

const ALL_KINDS = ['EXPENSE', 'INCOME', 'INTERNAL_TRANSFER', 'REFUND', 'BANK_FEE', 'INTEREST', 'TAX', 'UNKNOWN'];

const fmt = (n: number | string | null | undefined) => {
  const num = parseFloat(String(n ?? 0));
  return new Intl.NumberFormat('en-NP', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num);
};

interface Transaction {
  id: string;
  account_id: string;
  source: string;
  transaction_date: string;
  description_raw: string;
  description_clean: string | null;
  source_reference: string | null;
  amount: string;
  currency: string;
  transaction_kind: string | null;
  category: string | null;
  subcategory: string | null;
  merchant: string | null;
  is_internal_transfer: boolean | null;
  transfer_group_id: string | null;
  balance_after: string | null;
  classification_source: string | null;
}

interface Account {
  id: string;
  name: string;
  institution: string;
}

interface EditState {
  id: string;
  transaction_kind: string;
  category: string;
  merchant: string;
}

export const Transactions: React.FC = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [dbCategories, setDbCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filters
  const [accountId, setAccountId] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [kindFilter, setKindFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  // Edit state
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [showManualForm, setShowManualForm] = useState(false);
  const [manual, setManual] = useState({ account_id: '', transaction_date: new Date().toISOString().slice(0, 10), description: '', amount: '', direction: 'EXPENSE', category: '', subcategory: '', merchant: '', payment_method: 'CASH', notes: '' });
  const [manualError, setManualError] = useState('');

  const PAGE_SIZE = 50;

  const fetchData = useCallback(async () => {
    try {
      const [accRes, catRes] = await Promise.all([
        authFetch(`${API}/api/accounts/`),
        authFetch(`${API}/api/analytics/distinct-categories`)
      ]);
      if (accRes.ok) setAccounts(await accRes.json());
      if (catRes.ok) setDbCategories((await catRes.json()).categories || []);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('page_size', String(PAGE_SIZE));
    if (accountId) params.set('account_id', accountId);
    if (sourceFilter) params.set('source', sourceFilter);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (kindFilter) params.set('transaction_kind', kindFilter);
    if (categoryFilter) params.set('category', categoryFilter);
    if (minAmount) params.set('min_amount', minAmount);
    if (maxAmount) params.set('max_amount', maxAmount);
    if (search) params.set('search', search);

    try {
      const res = await authFetch(`${API}/api/transactions/?${params}`);
      if (res.ok) {
        const data = await res.json();
        setTransactions(data.transactions);
        setTotal(data.total);
      }
    } finally {
      setLoading(false);
    }
  }, [page, accountId, sourceFilter, dateFrom, dateTo, kindFilter, categoryFilter, minAmount, maxAmount, search]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchTransactions(); }, [fetchTransactions]);

  // Reset page when filters change
  useEffect(() => { setPage(1); }, [accountId, sourceFilter, dateFrom, dateTo, kindFilter, categoryFilter, minAmount, maxAmount, search]);

  const startEdit = (t: Transaction) => {
    setEditing({
      id: t.id,
      transaction_kind: t.transaction_kind || '',
      category: t.category || '',
      merchant: t.merchant || '',
    });
  };

  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const body: Record<string, string> = {};
      if (editing.transaction_kind) body.transaction_kind = editing.transaction_kind;
      if (editing.category) body.category = editing.category;
      if (editing.merchant) body.merchant = editing.merchant;

      const res = await authFetch(`${API}/api/transactions/${editing.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setEditing(null);
        fetchTransactions();
      }
    } finally {
      setSaving(false);
    }
  };

  const deleteManual = async (transaction: Transaction) => {
    if (transaction.source !== 'MANUAL' || !window.confirm('Delete this manual transaction?')) return;
    const res = await authFetch(`${API}/api/transactions/manual/${transaction.id}`, { method: 'DELETE' });
    if (res.ok) fetchTransactions();
  };

  const createManual = async (event: React.FormEvent) => {
    event.preventDefault();
    setManualError('');
    const res = await authFetch(`${API}/api/transactions/manual`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...manual, amount: manual.amount }) });
    if (!res.ok) { setManualError((await res.json().catch(() => null))?.detail || 'Could not create transaction'); return; }
    setShowManualForm(false);
    setManual({ ...manual, description: '', amount: '', category: '', subcategory: '', merchant: '', notes: '' });
    fetchTransactions();
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const accountMap = Object.fromEntries(accounts.map(a => [a.id, a]));

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h2>Transactions</h2>
          <p className="page-subtitle">{total.toLocaleString()} transactions total</p>
        </div>
        <button className="btn" onClick={() => { setManual(prev => ({ ...prev, account_id: prev.account_id || accounts[0]?.id || '' })); setShowManualForm(true); }}><Plus size={17} /> Add Transaction</button>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        {/* Search */}
        <div className="search-wrap">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search description, ref, or merchant…"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') setSearch(searchInput); }}
            className="search-input"
          />
          {searchInput && (
            <button className="search-clear" onClick={() => { setSearchInput(''); setSearch(''); }}>
              <X size={14} />
            </button>
          )}
        </div>

        <div className="filter-group">
          <Filter size={14} style={{ color: 'var(--text-secondary)' }} />
          
          <select value={accountId} onChange={e => setAccountId(e.target.value)} className="filter-select">
            <option value="">All Accounts</option>
            {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>

          <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)} className="filter-select">
            <option value="">All Sources</option>
            <option value="NABIL">Nabil</option>
            <option value="ESEWA">eSewa</option>
            <option value="MANUAL">Manual</option>
            <option value="STANDARD_CHARTERED">Standard Chartered</option>
          </select>

          <select value={kindFilter} onChange={e => setKindFilter(e.target.value)} className="filter-select">
            <option value="">All Types</option>
            {ALL_KINDS.map(k => <option key={k} value={k}>{KIND_LABELS[k]}</option>)}
          </select>

          <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className="filter-select">
            <option value="">All Categories</option>
            {dbCategories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          
          <input
            type="number"
            placeholder="Min Amount"
            value={minAmount}
            onChange={e => setMinAmount(e.target.value)}
            className="filter-select"
            style={{ width: 100 }}
          />
          
          <input
            type="number"
            placeholder="Max Amount"
            value={maxAmount}
            onChange={e => setMaxAmount(e.target.value)}
            className="filter-select"
            style={{ width: 100 }}
          />

          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="filter-select"
            title="From date"
          />
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="filter-select"
            title="To date"
          />

          {(accountId || sourceFilter || kindFilter || categoryFilter || dateFrom || dateTo || search || minAmount || maxAmount) && (
            <button className="btn-ghost" onClick={() => {
              setAccountId(''); setSourceFilter(''); setKindFilter(''); setCategoryFilter('');
              setDateFrom(''); setDateTo(''); setSearch(''); setSearchInput('');
              setMinAmount(''); setMaxAmount('');
            }}>
              Clear
            </button>
          )}
        </div>
      </div>

      {showManualForm && (
        <div className="modal-backdrop" onClick={() => setShowManualForm(false)}>
          <form className="modal card" onSubmit={createManual} onClick={e => e.stopPropagation()}>
            <div className="page-header"><h3>Add Transaction</h3><button type="button" className="icon-btn" onClick={() => setShowManualForm(false)}><X size={18} /></button></div>
            <div className="form-grid">
              <div className="form-group"><label>Date</label><input type="date" required value={manual.transaction_date} onChange={e => setManual({ ...manual, transaction_date: e.target.value })} /></div>
              <div className="form-group"><label>Account</label><select required value={manual.account_id} onChange={e => setManual({ ...manual, account_id: e.target.value })}>{accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
              <div className="form-group"><label>Description</label><input type="text" required value={manual.description} onChange={e => setManual({ ...manual, description: e.target.value })} /></div>
              <div className="form-group"><label>Amount</label><input type="number" min="0.01" step="0.01" required value={manual.amount} onChange={e => setManual({ ...manual, amount: e.target.value })} /></div>
              <div className="form-group"><label>Direction</label><select value={manual.direction} onChange={e => setManual({ ...manual, direction: e.target.value })}><option value="EXPENSE">Expense</option><option value="INCOME">Income</option></select></div>
              <div className="form-group"><label>Payment method</label><select value={manual.payment_method} onChange={e => setManual({ ...manual, payment_method: e.target.value })}><option value="CASH">Cash</option><option value="MANUAL_OTHER">Other</option></select></div>
              <div className="form-group"><label>Category</label><input type="text" required value={manual.category} list="transaction-categories" onChange={e => setManual({ ...manual, category: e.target.value })} /></div>
              <div className="form-group"><label>Subcategory</label><input type="text" value={manual.subcategory} onChange={e => setManual({ ...manual, subcategory: e.target.value })} /></div>
              <div className="form-group"><label>Merchant / payee</label><input type="text" value={manual.merchant} onChange={e => setManual({ ...manual, merchant: e.target.value })} /></div>
              <div className="form-group"><label>Notes</label><input type="text" value={manual.notes} onChange={e => setManual({ ...manual, notes: e.target.value })} /></div>
            </div>
            {manualError && <div className="result-banner error">{manualError}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}><button type="button" className="btn-ghost" onClick={() => setShowManualForm(false)}>Cancel</button><button type="submit" className="btn">Save Transaction</button></div>
          </form>
        </div>
      )}

      {/* Table */}
      <div className="card table-card">
        {loading ? (
          <div className="table-loading">
            <div className="loader" style={{ width: 36, height: 36 }} />
          </div>
        ) : transactions.length === 0 ? (
          <div className="table-empty">No transactions match your filters.</div>
        ) : (
          <div className="table-scroll">
            <table className="txn-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Source</th>
                  <th>Account</th>
                  <th>Description</th>
                  <th>Type</th>
                  <th>Category</th>
                  <th className="col-right">Amount</th>
                  <th className="col-right">Balance</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(t => {
                  const amount = parseFloat(t.amount);
                  const isTransfer = t.transaction_kind === 'INTERNAL_TRANSFER' || t.is_internal_transfer;
                  const isEditing = editing?.id === t.id;
                  const acct = accountMap[t.account_id];

                  return (
                    <tr key={t.id} className={isTransfer ? 'row-transfer' : ''}>
                      <td className="col-date">{t.transaction_date}</td>
                      <td><span className="source-badge">{t.source}</span></td>
                      <td className="col-account">
                        <span className="acct-badge">{acct?.institution || t.source}</span>
                      </td>
                      <td className="col-desc">
                        <div className="desc-main" title={t.description_raw}>{t.description_raw}</div>
                        {(t.merchant || t.source_reference) && (
                            <div className="desc-sub">
                                {t.merchant} {t.merchant && t.source_reference ? '·' : ''} {t.source_reference ? `Ref: ${t.source_reference}` : ''}
                            </div>
                        )}
                      </td>
                      <td>
                        {isEditing ? (
                          <select
                            value={editing.transaction_kind}
                            onChange={e => setEditing({ ...editing, transaction_kind: e.target.value })}
                            className="filter-select"
                            style={{ width: 130 }}
                          >
                            {ALL_KINDS.map(k => <option key={k} value={k}>{KIND_LABELS[k]}</option>)}
                          </select>
                        ) : (
                          <span
                            className="kind-badge"
                            style={{ backgroundColor: `${KIND_COLORS[t.transaction_kind || 'UNKNOWN']}22`, color: KIND_COLORS[t.transaction_kind || 'UNKNOWN'] }}
                          >
                            {isTransfer ? 'Internal Transfer' : KIND_LABELS[t.transaction_kind || 'UNKNOWN'] ?? t.transaction_kind}
                          </span>
                        )}
                      </td>
                      <td>
                        {isEditing ? (
                          <select
                            value={editing.category}
                            onChange={e => setEditing({ ...editing, category: e.target.value })}
                            className="filter-select"
                            style={{ width: 140 }}
                          >
                            <option value="">— none —</option>
                            {dbCategories.map(c => <option key={c} value={c}>{c}</option>)}
                            {!dbCategories.includes(editing.category) && editing.category && (
                                <option value={editing.category}>{editing.category}</option>
                            )}
                          </select>
                        ) : (
                          <span className="cat-label">{t.category || <span style={{ color: 'var(--text-secondary)' }}>—</span>}</span>
                        )}
                      </td>
                      <td className={`col-right amount ${amount >= 0 ? 'positive' : 'negative'}`}>
                        {amount >= 0 ? '+' : ''}{fmt(amount)} <span className="currency">{t.currency}</span>
                      </td>
                      <td className="col-right col-balance">
                        {t.balance_after != null ? `${fmt(t.balance_after)}` : '—'}
                      </td>
                      <td className="col-actions">
                        {isEditing ? (
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button className="icon-btn success" onClick={saveEdit} disabled={saving} title="Save">
                              <Check size={14} />
                            </button>
                            <button className="icon-btn" onClick={() => setEditing(null)} title="Cancel">
                              <X size={14} />
                            </button>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button className="icon-btn" onClick={() => startEdit(t)} title="Edit classification"><Edit2 size={14} /></button>
                            {t.source === 'MANUAL' && <button className="icon-btn" onClick={() => deleteManual(t)} title="Delete manual transaction"><X size={14} /></button>}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button className="icon-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
            <ChevronLeft size={16} />
          </button>
          <span className="page-info">Page {page} of {totalPages}</span>
          <button className="icon-btn" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
};
