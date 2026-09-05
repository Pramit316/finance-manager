import React, { useEffect, useState, useCallback } from 'react';
import { TrendingUp, TrendingDown, DollarSign, ArrowLeftRight, AlertCircle, Filter } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import { Link } from 'react-router-dom';

const API = 'http://localhost:8000';

const COLORS = ['#4f8ef7', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#6b7280'];

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
  EXPENSE: 'Expense', INCOME: 'Income', INTERNAL_TRANSFER: 'Transfer',
  REFUND: 'Refund', BANK_FEE: 'Bank Fee', INTEREST: 'Interest', TAX: 'Tax', UNKNOWN: 'Unknown',
};

const ALL_KINDS = ['EXPENSE', 'INCOME', 'INTERNAL_TRANSFER', 'REFUND', 'BANK_FEE', 'INTEREST', 'TAX', 'UNKNOWN'];

const fmt = (n: number | string | null | undefined) => {
  const num = parseFloat(String(n ?? 0));
  if (isNaN(num)) return '0.00';
  return new Intl.NumberFormat('en-NP', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num);
};

const fmtNPR = (n: number | string | null | undefined) => `NPR ${fmt(n)}`;

export const Dashboard: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [spendingCats, setSpendingCats] = useState<any[]>([]);
  const [incomeCats, setIncomeCats] = useState<any[]>([]);
  const [spendingByAcc, setSpendingByAcc] = useState<any[]>([]);
  const [monthlyTrend, setMonthlyTrend] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [recent, setRecent] = useState<any[]>([]);
  const [unknownCount, setUnknownCount] = useState(0);
  const [dbCategories, setDbCategories] = useState<string[]>([]);
  const [budget, setBudget] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [accountId, setAccountId] = useState('');
  const [source, setSource] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [kindFilter, setKindFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  
  const [selectedYear, setSelectedYear] = useState('');
  const [selectedMonth, setSelectedMonth] = useState('');

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    let from = dateFrom;
    let to = dateTo;
    
    if (selectedYear && selectedMonth) {
        const year = parseInt(selectedYear);
        const month = parseInt(selectedMonth);
        from = `${selectedYear}-${selectedMonth}-01`;
        
        // Calculate the last day of the month
        const lastDay = new Date(year, month, 0).getDate();
        to = `${selectedYear}-${selectedMonth}-${lastDay}`; 
    } else if (selectedYear) {
        from = `${selectedYear}-01-01`;
        to = `${selectedYear}-12-31`;
    }

    const params = new URLSearchParams();
    if (accountId) params.append('account_id', accountId);
    if (source) params.append('source', source);
    if (from) params.append('date_from', from);
    if (to) params.append('date_to', to);
    if (kindFilter) params.append('transaction_kind', kindFilter);
    if (categoryFilter) params.append('category', categoryFilter);

    try {
      const qs = params.toString();
      const q = qs ? `?${qs}` : '';

      const [
        summaryRes, spendCatRes, incCatRes, spendAccRes, 
        trendRes, unkRes, accsRes, recentRes, catsRes
      ] = await Promise.all([
        fetch(`${API}/api/analytics/summary${q}`),
        fetch(`${API}/api/analytics/categories${q}`),
        fetch(`${API}/api/analytics/income-categories${q}`),
        fetch(`${API}/api/analytics/spending-by-account${q}`),
        fetch(`${API}/api/analytics/monthly-trend${q}`),
        fetch(`${API}/api/analytics/unknown-count${q}`),
        fetch(`${API}/api/analytics/accounts`),
        fetch(`${API}/api/transactions/${q}${qs ? '&' : '?'}page=1&page_size=10`),
        fetch(`${API}/api/analytics/distinct-categories`)
      ]);

      if (!summaryRes.ok) throw new Error(`Summary: ${summaryRes.status}`);

      setSummary(await summaryRes.json());
      setSpendingCats((await spendCatRes.json()).categories || []);
      setIncomeCats((await incCatRes.json()).categories || []);
      setSpendingByAcc((await spendAccRes.json()).accounts || []);
      setMonthlyTrend((await trendRes.json()).months || []);
      setUnknownCount((await unkRes.json()).count || 0);
      setAccounts(await accsRes.json());
      setRecent((await recentRes.json()).transactions || []);
      setDbCategories((await catsRes.json()).categories || []);
      const now = new Date();
      const budgetRes = await fetch(`${API}/api/analytics/budget?year=${now.getFullYear()}&month=${now.getMonth() + 1}`);
      setBudget(budgetRes.ok ? await budgetRes.json() : null);
      
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [accountId, source, dateFrom, dateTo, kindFilter, categoryFilter, selectedYear, selectedMonth]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const totalBalance = accountId
    ? parseFloat(accounts.find(account => account.account_id === accountId)?.latest_balance ?? 0)
    : accounts.reduce((acc, curr) => acc + parseFloat(curr.latest_balance ?? 0), 0);
  
  const setDatePreset = (preset: string) => {
    const today = new Date();
    setSelectedYear('');
    setSelectedMonth('');
    
    if (preset === 'all') {
        setDateFrom('');
        setDateTo('');
    } else if (preset === 'today') {
        const d = today.toISOString().split('T')[0];
        setDateFrom(d);
        setDateTo(d);
    } else if (preset === 'month') {
        const first = new Date(today.getFullYear(), today.getMonth(), 1);
        setDateFrom(first.toISOString().split('T')[0]);
        setDateTo(today.toISOString().split('T')[0]);
    } else if (preset === 'year') {
        const first = new Date(today.getFullYear(), 0, 1);
        setDateFrom(first.toISOString().split('T')[0]);
        setDateTo(today.toISOString().split('T')[0]);
    }
  };

  if (error) {
    return (
      <div className="page-container">
        <div className="result-banner error">
          <AlertCircle style={{ marginRight: 8 }} />
          {error} — is the backend running on port 8000?
        </div>
      </div>
    );
  }

  const noData = !loading && (!summary || (summary.transaction_count === 0));

  return (
    <div className="page-container">
    
      {/* ── Unknown TX Banner ──────────────────────────────────────── */}
      {unknownCount > 0 && (
          <div className="result-banner warning" style={{ background: 'rgba(245,158,11,0.1)', borderLeft: '4px solid #f59e0b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#b45309' }}>
                  <AlertCircle size={20} />
                  <strong>Transactions needing review: {unknownCount}</strong>
                  <span>These transactions could not be auto-classified.</span>
              </div>
              <Link to="/transactions?transaction_kind=UNKNOWN" className="btn" style={{ background: '#f59e0b', color: '#fff' }}>Review Now</Link>
          </div>
      )}
      
      {/* ── Filters ─────────────────────────────────────────────── */}
      <div className="filters-bar">
        <div className="filter-group">
          <Filter size={14} style={{ color: 'var(--text-secondary)' }} />
          
          <button className="btn-ghost" onClick={() => setDatePreset('all')}>All Time</button>
          <button className="btn-ghost" onClick={() => setDatePreset('month')}>This Month</button>
          <button className="btn-ghost" onClick={() => setDatePreset('year')}>This Year</button>
          
          <select value={selectedYear} onChange={e => {setSelectedYear(e.target.value); setDateFrom(''); setDateTo('');}} className="filter-select">
            <option value="">Year</option>
            <option value="2026">2026</option>
            <option value="2025">2025</option>
          </select>
          
          <select value={selectedMonth} onChange={e => {setSelectedMonth(e.target.value); setDateFrom(''); setDateTo('');}} className="filter-select" disabled={!selectedYear}>
            <option value="">Month</option>
            {Array.from({length: 12}, (_, i) => {
                const m = String(i+1).padStart(2, '0');
                return <option key={m} value={m}>{new Date(2000, i).toLocaleString('default', {month: 'short'})}</option>
            })}
          </select>
          
          <select value={accountId} onChange={e => setAccountId(e.target.value)} className="filter-select">
            <option value="">All Accounts</option>
            {accounts.map(a => <option key={a.account_id} value={a.account_id}>{a.account_name}</option>)}
          </select>
          
          <select value={source} onChange={e => setSource(e.target.value)} className="filter-select">
            <option value="">All Sources</option>
            <option value="NABIL">Nabil</option>
            <option value="ESEWA">eSewa</option>
          </select>

          <select value={kindFilter} onChange={e => setKindFilter(e.target.value)} className="filter-select">
            <option value="">All Types</option>
            {ALL_KINDS.map(k => <option key={k} value={k}>{KIND_LABELS[k]}</option>)}
          </select>

          <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className="filter-select">
            <option value="">All Categories</option>
            {dbCategories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>

          {(accountId || source || kindFilter || categoryFilter || dateFrom || dateTo || selectedYear || selectedMonth) && (
            <button className="btn-ghost" onClick={() => {
              setAccountId(''); setSource(''); setKindFilter(''); setCategoryFilter('');
              setDateFrom(''); setDateTo(''); setSelectedYear(''); setSelectedMonth('');
            }}>
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {loading && !summary ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
          <div className="loader" style={{ width: 40, height: 40 }} />
        </div>
      ) : noData ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
          <DollarSign size={48} style={{ opacity: 0.3, marginBottom: '1rem' }} />
          <p style={{ marginBottom: '1rem' }}>No transaction data matches filters.</p>
        </div>
      ) : (
        <>
          {/* ── KPI Row ─────────────────────────────────────────────── */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-icon" style={{ background: 'rgba(79,142,247,0.15)' }}>
                <DollarSign size={24} color="#4f8ef7" />
              </div>
              <div>
                <div className="kpi-label">Total Balance</div>
                <div className="kpi-value">{fmtNPR(totalBalance)}</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon" style={{ background: 'rgba(16,185,129,0.15)' }}>
                <TrendingUp size={24} color="#10b981" />
              </div>
              <div>
                <div className="kpi-label">Total Income</div>
                <div className="kpi-value positive">{fmtNPR(summary?.total_income)}</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon" style={{ background: 'rgba(239,68,68,0.15)' }}>
                <TrendingDown size={24} color="#ef4444" />
              </div>
              <div>
                <div className="kpi-label">Total Spending</div>
                <div className="kpi-value negative">{fmtNPR(summary?.total_spending)}</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon" style={{ background: 'rgba(139,92,246,0.15)' }}>
                <ArrowLeftRight size={24} color="#8b5cf6" />
              </div>
              <div>
                <div className="kpi-label">Internal Transfers</div>
                <div className="kpi-value" style={{ color: '#8b5cf6' }}>{fmtNPR(summary?.internal_transfers)}</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon" style={{ background: parseFloat(summary?.net_cash_flow ?? 0) >= 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)' }}>
                <DollarSign size={24} color={parseFloat(summary?.net_cash_flow ?? 0) >= 0 ? '#10b981' : '#ef4444'} />
              </div>
              <div>
                <div className="kpi-label">Net Cash Flow</div>
                <div className="kpi-value" style={{ color: parseFloat(summary?.net_cash_flow ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                  {fmtNPR(summary?.net_cash_flow)}
                </div>
              </div>
            </div>
          </div>

          {budget && (
            <div className="card">
              <div className="page-header"><div><h3>Monthly Plan</h3><p className="page-subtitle">Consumption excludes investments and internal transfers.</p></div><Link to="/budget" className="btn-ghost">View Plan</Link></div>
              <div className="stat-grid">
                <div className="stat-item"><div className="stat-label">Planned Consumption</div><div className="stat-value">{fmtNPR(budget.planned_consumption)}</div></div>
                <div className="stat-item"><div className="stat-label">Actual Consumption</div><div className="stat-value">{fmtNPR(budget.actual_consumption)}</div></div>
                <div className="stat-item"><div className="stat-label">Planned Saving</div><div className="stat-value">{fmtNPR(budget.planned_saving)}</div></div>
                <div className="stat-item"><div className="stat-label">Actual Saving</div><div className="stat-value">{fmtNPR(budget.actual_saving)}</div></div>
              </div>
            </div>
          )}
          
          {/* ── Monthly Trend ─────────────────────────────────────── */}
          <div className="card">
            <h3>Monthly Trend</h3>
            <div style={{ height: 300, marginTop: '1.5rem', opacity: loading ? 0.5 : 1 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthlyTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="month" stroke="var(--text-secondary)" tick={{fontSize: 12}} />
                  <YAxis stroke="var(--text-secondary)" tick={{fontSize: 12}} tickFormatter={(v) => (v/1000)+'k'} />
                  <RechartsTooltip 
                      formatter={(v: any) => fmtNPR(v)}
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8 }}
                  />
                  <Legend />
                  <Bar dataKey="income" name="Income" fill="#10b981" radius={[4,4,0,0]} />
                  <Bar dataKey="spending" name="Spending" fill="#ef4444" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── Analysis Row ─────────────────────────────────────── */}
          <div className="two-col" style={{ opacity: loading ? 0.5 : 1 }}>
            
            {/* Spending Category pie */}
            <div className="card">
              <h3>Spending by Category</h3>
              {spendingCats.length > 0 ? (
                <>
                  <div style={{ height: 240, marginTop: '1rem' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={spendingCats} cx="50%" cy="50%" innerRadius={55} outerRadius={95}
                          paddingAngle={3} dataKey="amount" nameKey="category">
                          {spendingCats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                        </Pie>
                        <RechartsTooltip
                          formatter={(v: any) => fmtNPR(v)}
                          contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13 }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div style={{ marginTop: '0.75rem' }}>
                    {spendingCats.slice(0, 6).map((cat, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS[i % COLORS.length] }} />
                          <span style={{ fontSize: '0.85rem' }}>{cat.category}</span>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block' }}>{fmtNPR(cat.amount)}</span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{cat.percentage}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                   No spending matches filters.
                </div>
              )}
            </div>
            
            {/* Income & Accounts */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div className="card">
                  <h3>Income by Category</h3>
                  {incomeCats.length > 0 ? (
                      <div style={{ marginTop: '1rem' }}>
                        {incomeCats.slice(0, 5).map((cat, i) => (
                          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}>
                            <span style={{ fontSize: '0.85rem' }}>{cat.category}</span>
                            <div style={{ textAlign: 'right' }}>
                              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#10b981', display: 'block' }}>{fmtNPR(cat.amount)}</span>
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{cat.percentage}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                  ) : (
                      <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>No income matches filters.</div>
                  )}
                </div>
                
                <div className="card">
                  <h3>Spending by Account</h3>
                  {spendingByAcc.length > 0 ? (
                      <div style={{ marginTop: '1rem' }}>
                        {spendingByAcc.map((acc, i) => (
                          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}>
                            <span style={{ fontSize: '0.85rem' }}>{acc.account_name} ({acc.institution})</span>
                            <div style={{ textAlign: 'right' }}>
                              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#ef4444', display: 'block' }}>{fmtNPR(acc.amount)}</span>
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{acc.percentage}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                  ) : (
                      <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>No spending matches filters.</div>
                  )}
                </div>
            </div>

          </div>

          {/* ── Recent transactions & Account Balances ────────────────── */}
          <div className="two-col" style={{ opacity: loading ? 0.5 : 1 }}>
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3>Filtered Transactions</h3>
                  <Link to="/transactions" style={{ fontSize: '0.82rem', color: 'var(--accent-primary)' }}>View all →</Link>
                </div>
                <div className="recent-txns-list">
                  {recent.length === 0 ? (
                    <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>No transactions found.</div>
                  ) : recent.map(t => {
                    const amount = parseFloat(t.amount);
                    const kind = t.transaction_kind || 'UNKNOWN';
                    return (
                      <div key={t.id} className="recent-txn-row">
                        <div style={{
                          width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                          background: KIND_COLORS[kind]
                        }} />
                        <div className="rtxn-desc">
                          <div className="rtxn-main">{t.description_raw}</div>
                          <div className="rtxn-date">{t.transaction_date} · <span style={{ color: KIND_COLORS[kind] }}>{KIND_LABELS[kind]}</span>{t.category ? ` · ${t.category}` : ''}</div>
                        </div>
                        <div className={`rtxn-amount ${amount >= 0 ? 'positive' : 'negative'}`}>
                          {amount >= 0 ? '+' : ''}{fmt(amount)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              
              <div className="card">
                  <h3>Account Balances</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
                    {accounts.length > 0 ? accounts.map(acc => (
                      <div key={acc.account_id} className="account-row">
                        <div>
                          <div className="acct-name">{acc.account_name}</div>
                          <div className="acct-inst">{acc.institution}</div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div className="acct-balance">{fmtNPR(acc.latest_balance)}</div>
                          {acc.latest_balance_date && <div className="acct-date">as of {acc.latest_balance_date}</div>}
                        </div>
                      </div>
                    )) : (
                      <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>No accounts found.</div>
                    )}
                  </div>
                  
                  {/* Summary breakdown */}
                  {summary && (
                    <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                      <h3 style={{ marginBottom: '0.75rem' }}>Misc Breakdown (Filtered)</h3>
                      {[
                        { label: 'Refunds', value: summary.refunds, color: '#06b6d4' },
                        { label: 'Bank Fees', value: summary.bank_fees, color: '#f59e0b' },
                        { label: 'Tax', value: summary.tax, color: '#f97316' },
                        { label: 'Transactions', value: summary.transaction_count, color: 'var(--text-primary)', noFmt: true },
                      ].map(({ label, value, color, noFmt }) => (
                        <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', fontSize: '0.85rem' }}>
                          <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                          <span style={{ color, fontWeight: 600 }}>{noFmt ? value : fmtNPR(value)}</span>
                        </div>
                      ))}
                    </div>
                  )}
              </div>
          </div>
        </>
      )}
    </div>
  );
};

