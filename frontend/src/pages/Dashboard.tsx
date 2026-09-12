import React, { useEffect, useState, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { TrendingUp, TrendingDown, DollarSign, ArrowLeftRight, AlertCircle, Filter, Check, X } from 'lucide-react';
import { Cell, ResponsiveContainer, Tooltip as RechartsTooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import { Link } from 'react-router-dom';
import { API } from '../config';
import { authFetch } from '../lib/api';
import { bsInputValue, bsToAd, currentBsMonthRange, formatDualDate } from '../lib/dateUtils';
import { AnimatedNumber } from '../components/AnimatedNumber';

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
  const [balanceAccounts, setBalanceAccounts] = useState<any[]>([]);
  const [recent, setRecent] = useState<any[]>([]);
  const [unknownCount, setUnknownCount] = useState(0);
  const [dbCategories, setDbCategories] = useState<string[]>([]);
  const [budget, setBudget] = useState<any>(null);
  const [planComparison, setPlanComparison] = useState<any>(null);
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [comparison, setComparison] = useState<any>(null);
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [categoryDraft, setCategoryDraft] = useState('');
  const [savingCategory, setSavingCategory] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<any>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [trendExpanded, setTrendExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestGeneration = useRef(0);

  // Filters
  const [accountId, setAccountId] = useState('');
  const [source, setSource] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [calendarMode, setCalendarMode] = useState<'AD' | 'BS'>('AD');
  const [bsFromInput, setBsFromInput] = useState('');
  const [bsToInput, setBsToInput] = useState('');
  const [activePreset, setActivePreset] = useState('all');
  const [kindFilter, setKindFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const fetchAll = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setLoading(true);
    setError(null);
    
    const params = new URLSearchParams();
    if (accountId) params.append('account_id', accountId);
    if (source) params.append('source', source);
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (kindFilter) params.append('transaction_kind', kindFilter);
    if (categoryFilter) params.append('category', categoryFilter);

    try {
      const qs = params.toString();
      const q = qs ? `?${qs}` : '';
      const balanceParams = new URLSearchParams(params);
      if (!balanceParams.has('date_to') && dateTo) balanceParams.set('date_to', dateTo);
      const now = new Date();
      const budgetParams = new URLSearchParams(params);
      budgetParams.set('year', String(now.getFullYear()));
      budgetParams.set('month', String(now.getMonth() + 1));

      const [
        summaryRes, spendCatRes, incCatRes, spendAccRes, 
        trendRes, unkRes, accsRes, balanceAccsRes, recentRes, catsRes, comparisonRes, budgetRes, planRes
      ] = await Promise.all([
        authFetch(`${API}/api/analytics/summary${q}`),
        authFetch(`${API}/api/analytics/categories${q}`),
        authFetch(`${API}/api/analytics/income-categories${q}`),
        authFetch(`${API}/api/analytics/spending-by-account${q}`),
        authFetch(`${API}/api/analytics/monthly-trend${q}`),
        authFetch(`${API}/api/analytics/unknown-count${q}`),
        authFetch(`${API}/api/analytics/accounts`),
        authFetch(`${API}/api/analytics/accounts?${balanceParams.toString()}`),
        authFetch(`${API}/api/transactions/${q}${qs ? '&' : '?'}page=1&page_size=10`),
        authFetch(`${API}/api/analytics/distinct-categories`),
        authFetch(`${API}/api/analytics/comparison${q}`),
        authFetch(`${API}/api/analytics/budget?${budgetParams.toString()}`),
        authFetch(`${API}/api/analytics/plan-comparison${q}`),
      ]);

      if (!summaryRes.ok) throw new Error(`Summary: ${summaryRes.status}`);
      if (generation !== requestGeneration.current) return;

      setSummary(await summaryRes.json());
      setSpendingCats((await spendCatRes.json()).categories || []);
      setIncomeCats((await incCatRes.json()).categories || []);
      setSpendingByAcc((await spendAccRes.json()).accounts || []);
      setMonthlyTrend((await trendRes.json()).months || []);
      setUnknownCount((await unkRes.json()).count || 0);
      if (generation !== requestGeneration.current) return;
      setAccounts(await accsRes.json());
      setBalanceAccounts(await balanceAccsRes.json());
      setRecent((await recentRes.json()).transactions || []);
      setDbCategories((await catsRes.json()).categories || []);
      setBudget(budgetRes.ok ? await budgetRes.json() : null);
      setComparison(comparisonRes.ok ? await comparisonRes.json() : null);
      setPlanComparison(planRes.ok ? await planRes.json() : null);
      
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [accountId, source, dateFrom, dateTo, kindFilter, categoryFilter]);

  const updateCategory = async (transactionId: string) => {
    setSavingCategory(transactionId);
    try {
      const response = await authFetch(`${API}/api/transactions/${transactionId}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: categoryDraft }),
      });
      if (!response.ok) throw new Error((await response.json()).detail || 'Could not update category');
      const updated = await response.json();
      setRecent(current => current.map(txn => txn.id === transactionId ? { ...txn, category: updated.category } : txn));
      setDrilldown((current: any) => current ? { ...current, transactions: current.transactions.map((txn: any) => txn.id === transactionId ? { ...txn, category: updated.category } : txn) } : current);
      setEditingCategory(null);
      await fetchAll();
    } catch (err: any) {
      setError(err.message || 'Could not update category');
    } finally {
      setSavingCategory(null);
    }
  };

  const openDrilldown = async (metric: string, extra: Record<string, string> = {}) => {
    setDrilldownLoading(true);
    try {
      const drillParams = new URLSearchParams(paramsForFilters());
      drillParams.set('metric', metric);
      Object.entries(extra).forEach(([key, value]) => drillParams.set(key, value));
      const response = await authFetch(`${API}/api/analytics/drilldown?${drillParams.toString()}`);
      if (!response.ok) throw new Error('Could not load dashboard detail');
      setDrilldown(await response.json());
    } catch (err: any) { setError(err.message); }
    finally { setDrilldownLoading(false); }
  };

  const paramsForFilters = () => {
    const params = new URLSearchParams();
    if (accountId) params.set('account_id', accountId);
    if (source) params.set('source', source);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (kindFilter) params.set('transaction_kind', kindFilter);
    if (categoryFilter) params.set('category', categoryFilter);
    return params;
  };

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    if (!drilldown) return;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrilldown(null);
    };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [drilldown]);

  const totalBalance = balanceAccounts.reduce((total, account) => total + parseFloat(account.latest_balance ?? 0), 0);
  const categoryChartData = spendingCats.map(category => ({
    ...category,
    amount: Number(category.amount) || 0,
  }));
  
  const toDateInput = (date: Date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const setDatePreset = (preset: string) => {
    const today = new Date();
    const todayValue = toDateInput(today);
    setActivePreset(preset);
    
    if (preset === 'all') {
        setDateFrom('');
        setDateTo('');
    } else if (preset === 'today') {
        setDateFrom(todayValue);
        setDateTo(todayValue);
    } else if (preset === '7days' || preset === '30days') {
        const days = preset === '7days' ? 6 : 29;
        const first = new Date(today);
        first.setDate(today.getDate() - days);
        setDateFrom(toDateInput(first));
        setDateTo(todayValue);
    } else if (preset === 'month') {
        const first = new Date(today.getFullYear(), today.getMonth(), 1);
        setDateFrom(toDateInput(first));
        setDateTo(todayValue);
    } else if (preset === 'bsmonth') {
      const range = currentBsMonthRange(today);
      setDateFrom(range.from);
      setDateTo(range.to);
    } else if (preset === 'lastmonth') {
        const first = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const last = new Date(today.getFullYear(), today.getMonth(), 0);
        setDateFrom(toDateInput(first));
        setDateTo(toDateInput(last));
    } else if (preset === 'year') {
        const first = new Date(today.getFullYear(), 0, 1);
        setDateFrom(toDateInput(first));
        setDateTo(todayValue);
    }
  };

  const datePresets = [
    ['all', 'All Time'], ['today', 'Today'], ['7days', 'Last 7 Days'], ['30days', 'Last 30 Days'], ['bsmonth', 'This Nepali Month'],
    ['month', 'This Month'], ['lastmonth', 'Last Month'], ['year', 'This Year'], ['custom', 'Custom Range'],
  ];

  const switchCalendarMode = (mode: 'AD' | 'BS') => {
    setCalendarMode(mode);
    if (mode === 'BS') {
      setBsFromInput(dateFrom ? bsInputValue(dateFrom) : '');
      setBsToInput(dateTo ? bsInputValue(dateTo) : '');
    }
  };

  const updateDateFrom = (value: string) => {
    try {
      if (calendarMode === 'BS') {
        setBsFromInput(value);
        if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(value)) setDateFrom(bsToAd(value));
      } else {
        setDateFrom(value);
      }
      setActivePreset('custom');
    } catch { }
  };

  const updateDateTo = (value: string) => {
    try {
      if (calendarMode === 'BS') {
        setBsToInput(value);
        if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(value)) setDateTo(bsToAd(value));
      } else {
        setDateTo(value);
      }
      setActivePreset('custom');
    } catch { }
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
      <div className="dashboard-hero">
        <div>
          <span className="eyebrow">FINTRACK / OVERVIEW</span>
          <h1>Financial command center</h1>
          <p className="page-subtitle">A clear view of your money, movement, and momentum.</p>
        </div>
        <div className="dashboard-hero-meta"><span className="status-dot" /> Live account intelligence</div>
      </div>
    
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
          
          {datePresets.map(([value, label]) => (
            <button key={value} className={`btn-ghost filter-preset ${activePreset === value ? 'active' : ''}`} onClick={() => setDatePreset(value)}>
              {label}
            </button>
          ))}

          {activePreset === 'custom' && (
            <div className="hybrid-date-picker">
              <div className="calendar-mode-toggle" role="group" aria-label="Calendar input mode">
                <button className={calendarMode === 'AD' ? 'active' : ''} onClick={() => switchCalendarMode('AD')}>AD</button>
                <button className={calendarMode === 'BS' ? 'active' : ''} onClick={() => switchCalendarMode('BS')}>BS</button>
              </div>
              <div className="date-range-fields">
                <label>Start Date
                  <input
                    type={calendarMode === 'AD' ? 'date' : 'text'}
                    placeholder={calendarMode === 'BS' ? 'YYYY-MM-DD' : undefined}
                    value={calendarMode === 'AD' ? dateFrom : bsFromInput}
                    onChange={e => updateDateFrom(e.target.value)}
                  />
                  {dateFrom && <small>{formatDualDate(dateFrom)}</small>}
                </label>
                <span className="date-range-separator">to</span>
                <label>End Date
                  <input
                    type={calendarMode === 'AD' ? 'date' : 'text'}
                    placeholder={calendarMode === 'BS' ? 'YYYY-MM-DD' : undefined}
                    value={calendarMode === 'AD' ? dateTo : bsToInput}
                    min={calendarMode === 'AD' ? (dateFrom || undefined) : undefined}
                    onChange={e => updateDateTo(e.target.value)}
                  />
                  {dateTo && <small>{formatDualDate(dateTo)}</small>}
                </label>
              </div>
            </div>
          )}
          
          <select value={accountId} onChange={e => setAccountId(e.target.value)} className="filter-select">
            <option value="">All Accounts</option>
            {accounts.map(a => <option key={a.account_id} value={a.account_id}>{a.account_name}</option>)}
          </select>
          
          <select value={source} onChange={e => setSource(e.target.value)} className="filter-select">
            <option value="">All Sources</option>
            <option value="NABIL">Nabil</option>
            <option value="ESEWA">eSewa</option>
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

          {(accountId || source || kindFilter || categoryFilter || dateFrom || dateTo || activePreset !== 'all') && (
            <button className="btn-ghost" onClick={() => {
              setAccountId(''); setSource(''); setKindFilter(''); setCategoryFilter('');
              setDateFrom(''); setDateTo(''); setActivePreset('all');
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
            <button className="kpi-card kpi-balance dashboard-clickable" onClick={() => openDrilldown('balance')}>
              <div className="kpi-icon" style={{ background: 'rgba(79,142,247,0.15)' }}>
                <DollarSign size={24} color="#4f8ef7" />
              </div>
              <div>
                <div className="kpi-label">Total Balance</div>
                <div className="kpi-value"><AnimatedNumber value={totalBalance} format={fmtNPR} /></div>
              </div>
            </button>

            <button className="kpi-card dashboard-clickable" onClick={() => openDrilldown('income')}>
              <div className="kpi-icon" style={{ background: 'rgba(16,185,129,0.15)' }}>
                <TrendingUp size={24} color="#10b981" />
              </div>
              <div>
                <div className="kpi-label">Total Income</div>
                <div className="kpi-value positive"><AnimatedNumber value={summary?.total_income} format={fmtNPR} /></div>
              </div>
            </button>

            <button className="kpi-card dashboard-clickable" onClick={() => openDrilldown('spending')}>
              <div className="kpi-icon" style={{ background: 'rgba(239,68,68,0.15)' }}>
                <TrendingDown size={24} color="#ef4444" />
              </div>
              <div>
                <div className="kpi-label">Total Spending</div>
                <div className="kpi-value negative"><AnimatedNumber value={summary?.total_spending} format={fmtNPR} /></div>
              </div>
            </button>

            <button className="kpi-card dashboard-clickable" onClick={() => openDrilldown('transfers')}>
              <div className="kpi-icon" style={{ background: 'rgba(139,92,246,0.15)' }}>
                <ArrowLeftRight size={24} color="#8b5cf6" />
              </div>
              <div>
                <div className="kpi-label">Internal Transfers</div>
                <div className="kpi-value" style={{ color: '#8b5cf6' }}><AnimatedNumber value={summary?.internal_transfers} format={fmtNPR} /></div>
              </div>
            </button>

            <button className="kpi-card dashboard-clickable" onClick={() => openDrilldown('spending')}>
              <div className="kpi-icon" style={{ background: parseFloat(summary?.net_cash_flow ?? 0) >= 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)' }}>
                <DollarSign size={24} color={parseFloat(summary?.net_cash_flow ?? 0) >= 0 ? '#10b981' : '#ef4444'} />
              </div>
              <div>
                <div className="kpi-label">Net Cash Flow</div>
                <div className="kpi-value" style={{ color: parseFloat(summary?.net_cash_flow ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                  <AnimatedNumber value={summary?.net_cash_flow} format={fmtNPR} />
                </div>
              </div>
            </button>
          </div>

          <div className="dashboard-analysis-grid">
            <div className="card money-flow-card">
              <div className="section-kicker">MONEY FLOW</div>
              <h3>Income to savings</h3>
              <div className="money-flow-path">
                <div><span>Income</span><strong className="positive">{fmtNPR(summary?.total_income)}</strong></div>
                <span className="flow-arrow">→</span>
                <div><span>Expenses</span><strong className="negative">{fmtNPR(summary?.total_spending)}</strong></div>
                <span className="flow-arrow">→</span>
                <div><span>Net / savings</span><strong className={parseFloat(summary?.net_cash_flow ?? 0) >= 0 ? 'positive' : 'negative'}>{fmtNPR(summary?.net_cash_flow)}</strong></div>
              </div>
            </div>
            {comparison?.available && (
              <div className="card comparison-card">
                <div className="section-kicker">PERIOD COMPARISON</div>
                <h3>{comparison.current_period.from} to {comparison.current_period.to}</h3>
                <div className="comparison-stats">
                  <span>Expenses <strong className={parseFloat(comparison.current.total_spending) - parseFloat(comparison.previous.total_spending) > 0 ? 'negative' : 'positive'}>{fmtNPR(parseFloat(comparison.current.total_spending) - parseFloat(comparison.previous.total_spending))}</strong></span>
                  <span>Income <strong className={parseFloat(comparison.current.total_income) - parseFloat(comparison.previous.total_income) >= 0 ? 'positive' : 'negative'}>{fmtNPR(parseFloat(comparison.current.total_income) - parseFloat(comparison.previous.total_income))}</strong></span>
                  <span>Net flow <strong>{fmtNPR(parseFloat(comparison.current.net_cash_flow) - parseFloat(comparison.previous.net_cash_flow))}</strong></span>
                </div>
              </div>
            )}
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

          {planComparison?.available && (
            <button className="card plan-summary-card dashboard-clickable" onClick={() => setPlanModalOpen(true)}>
              <div className="section-kicker">PLAN VS ACTUAL</div>
              <div className="plan-summary-grid">
                <div><span>Planned</span><strong>{fmtNPR(Number(planComparison.planned_spending) + Number(planComparison.planned_investment))}</strong></div>
                <div><span>Actual</span><strong>{fmtNPR(planComparison.actual_spending)}</strong></div>
                <div><span>{Number(planComparison.difference) >= 0 ? 'Remaining' : 'Over budget'}</span><strong className={Number(planComparison.difference) >= 0 ? 'positive' : 'negative'}>{fmtNPR(Math.abs(planComparison.difference))}</strong></div>
                <div><span>Used</span><strong>{planComparison.budget_utilization == null ? '—' : `${Number(planComparison.budget_utilization).toFixed(1)}%`}</strong></div>
              </div>
            </button>
          )}
          
          {/* ── Monthly Trend ─────────────────────────────────────── */}
          <div className="card monthly-trend-card">
            <button className="section-toggle" onClick={() => setTrendExpanded(value => !value)}><h3>Monthly Trend</h3><span>{trendExpanded ? 'Collapse' : 'Expand'}</span></button>
            {trendExpanded && <div style={{ height: 260, marginTop: '1rem', opacity: loading ? 0.5 : 1 }}>
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
            </div>}
          </div>

          {/* ── Analysis Row ─────────────────────────────────────── */}
          <div className="two-col" style={{ opacity: loading ? 0.5 : 1 }}>
            
            {/* Spending Category pie */}
            <div className="card category-analysis-card">
              <h3>Spending by Category</h3>
              {spendingCats.length > 0 ? (
                <>
                  <div className="category-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={categoryChartData} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="category" width={92} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                        <Bar dataKey="amount" fill="#4f8ef7" radius={[0, 4, 4, 0]} barSize={18}>
                          {categoryChartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                        </Bar>
                        <RechartsTooltip
                          formatter={(v: any) => fmtNPR(v)}
                          contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13 }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div style={{ marginTop: '0.75rem' }}>
                    {spendingCats.slice(0, 6).map((cat, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS[i % COLORS.length] }} />
                          <button className="category-drilldown-button" onClick={() => openDrilldown('category', { drilldown_category: cat.category })}>{cat.category}</button>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block' }}>{fmtNPR(cat.amount)}</span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{cat.percentage}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {comparison?.category_changes?.length > 0 && (
                    <div className="category-comparison-list">
                      <div className="section-kicker">VS PREVIOUS PERIOD</div>
                      {comparison.category_changes.slice(0, 5).map((item: any) => (
                        <div key={item.category} className="category-change-row">
                          <span>{item.category}</span>
                          <strong className={parseFloat(item.difference) > 0 ? 'negative' : 'positive'}>
                            {parseFloat(item.difference) > 0 ? '+' : ''}{fmtNPR(item.difference)}
                          </strong>
                        </div>
                      ))}
                    </div>
                  )}
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
                            <button className="category-drilldown-button" onClick={() => openDrilldown('account', { drilldown_account_id: acc.account_id })}>{acc.account_name} ({acc.institution})</button>
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
                    const account = accounts.find(item => item.account_id === t.account_id);
                    const isEditing = editingCategory === t.id;
                    return (
                      <div key={t.id} className="recent-txn-row">
                        <div style={{
                          width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                          background: KIND_COLORS[kind]
                        }} />
                        <div className="rtxn-desc">
                          <div className="rtxn-main">{t.description_raw}</div>
                          <div className="rtxn-date">{t.transaction_date} · {account?.account_name || 'Account'} · <span style={{ color: KIND_COLORS[kind] }}>{KIND_LABELS[kind]}</span></div>
                          <div className="dashboard-category-editor">
                            {isEditing ? (
                              <>
                                <select value={categoryDraft} onChange={e => setCategoryDraft(e.target.value)} className="inline-category-select">
                                  <option value="">Uncategorized</option>
                                  {dbCategories.map(category => <option key={category} value={category}>{category}</option>)}
                                </select>
                                <button className="icon-btn success" title="Save category" disabled={savingCategory === t.id} onClick={() => updateCategory(t.id)}><Check size={14} /></button>
                                <button className="icon-btn" title="Cancel" onClick={() => setEditingCategory(null)}><X size={14} /></button>
                              </>
                            ) : (
                              <button className="category-edit-trigger" onClick={() => { setEditingCategory(t.id); setCategoryDraft(t.category || ''); }}>
                                {t.category || 'Uncategorized'}
                              </button>
                            )}
                          </div>
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
                      <button key={acc.account_id} className="account-row account-drilldown-button" onClick={() => openDrilldown('account', { drilldown_account_id: acc.account_id })}>
                        <div>
                          <div className="acct-name">{acc.account_name}</div>
                          <div className="acct-inst">{acc.institution}</div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div className="acct-balance">{fmtNPR(acc.latest_balance)}</div>
                          {acc.latest_balance_date && <div className="acct-date">as of {acc.latest_balance_date}</div>}
                        </div>
                      </button>
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
      {drilldown && createPortal((
        <div className="modal-backdrop" onClick={() => setDrilldown(null)}>
          <section className="card dashboard-drilldown" onClick={event => event.stopPropagation()}>
            <div className="drilldown-header">
              <div><div className="section-kicker">FILTERED DETAIL</div><h2>{drilldown.metric === 'spending' ? 'Total Spending' : drilldown.metric === 'income' ? 'Total Income' : drilldown.metric === 'transfers' ? 'Internal Transfers' : drilldown.metric === 'category' ? 'Category Spending' : 'Account Detail'}</h2></div>
              <button className="icon-btn" title="Close detail" onClick={() => setDrilldown(null)}><X size={18} /></button>
            </div>
            {drilldownLoading ? <div className="table-loading"><div className="loader" /></div> : <>
              <div className="drilldown-stat-grid">
                <div><span>Total</span><strong>{fmtNPR(drilldown.total)}</strong></div>
                <div><span>Transactions</span><strong>{drilldown.count}</strong></div>
                <div><span>Average</span><strong>{fmtNPR(drilldown.average)}</strong></div>
                <div><span>Largest</span><strong>{fmtNPR(drilldown.largest)}</strong></div>
                <div><span>Average / day</span><strong>{fmtNPR(drilldown.average_daily)}</strong></div>
              </div>
              {drilldown.accounts?.length > 0 && <div className="drilldown-category-list">
                {drilldown.accounts.map((account: any) => <div key={account.account_id}><span>{account.account_name} ({account.institution})</span><strong>{fmtNPR(account.latest_balance)}</strong></div>)}
              </div>}
              {comparison?.available && ['spending', 'income'].includes(drilldown.metric) && <p className="page-subtitle">Previous equivalent period: {fmtNPR(drilldown.metric === 'spending' ? comparison.previous.total_spending : comparison.previous.total_income)}. Change: {fmtNPR((drilldown.metric === 'spending' ? comparison.current.total_spending - comparison.previous.total_spending : comparison.current.total_income - comparison.previous.total_income))}</p>}
              {drilldown.categories?.length > 0 && <div className="drilldown-category-list">
                {drilldown.categories.map((item: any) => <div key={item.category}><span>{item.category}</span><strong>{fmtNPR(item.amount)} <small>{item.percentage.toFixed(1)}%</small></strong></div>)}
              </div>}
              <h3 className="drilldown-transactions-title">Which transactions created this number?</h3>
              <div className="drilldown-transactions">
                {drilldown.transactions?.map((transaction: any) => (
                  <div key={transaction.id} className="drilldown-transaction-row">
                    <span>{transaction.transaction_date}</span><span className="drilldown-description">{transaction.description_raw}</span><strong className={parseFloat(transaction.amount) >= 0 ? 'positive' : 'negative'}>{fmtNPR(transaction.amount)}</strong>
                    <select value={transaction.category || ''} onChange={event => { setCategoryDraft(event.target.value); setEditingCategory(transaction.id); }} className="inline-category-select">
                      <option value="">Uncategorized</option>{dbCategories.map(category => <option key={category} value={category}>{category}</option>)}
                    </select>
                    {editingCategory === transaction.id && <button className="icon-btn success" title="Save category" disabled={savingCategory === transaction.id} onClick={() => updateCategory(transaction.id)}><Check size={14} /></button>}
                  </div>
                ))}
              </div>
            </>}
          </section>
        </div>
      ), document.body)}
      {planModalOpen && planComparison && createPortal((
        <div className="modal-backdrop" onClick={() => setPlanModalOpen(false)}>
          <section className="card dashboard-drilldown plan-analysis-modal" onClick={event => event.stopPropagation()}>
            <div className="drilldown-header">
              <div><div className="section-kicker">PLAN VS ACTUAL</div><h2>{planComparison.period_from} to {planComparison.period_to}</h2></div>
              <button className="icon-btn" title="Close plan analysis" onClick={() => setPlanModalOpen(false)}><X size={18} /></button>
            </div>
            <div className="drilldown-stat-grid">
              <div><span>Expected income</span><strong>{fmtNPR(planComparison.expected_income)}</strong></div>
              <div><span>Planned spending</span><strong>{fmtNPR(planComparison.planned_spending)}</strong></div>
              <div><span>Actual spending</span><strong>{fmtNPR(planComparison.actual_spending)}</strong></div>
              <div><span>Planned investment</span><strong>{fmtNPR(planComparison.planned_investment)}</strong></div>
              <div><span>Actual investment</span><strong>{fmtNPR(planComparison.actual_investment)}</strong></div>
              <div><span>Planned saving</span><strong>{fmtNPR(planComparison.planned_saving)}</strong></div>
              <div><span>Actual remaining</span><strong>{fmtNPR(planComparison.actual_remaining)}</strong></div>
              <div><span>Unplanned spending</span><strong className="negative">{fmtNPR(planComparison.unplanned_spending)}</strong></div>
              <div><span>Uncategorized</span><strong>{fmtNPR(planComparison.uncategorized_spending)}</strong></div>
              <div><span>Plan used</span><strong>{planComparison.budget_utilization == null ? '—' : `${Number(planComparison.budget_utilization).toFixed(1)}%`}</strong></div>
            </div>
            <div className="plan-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={planComparison.categories} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                  <XAxis type="number" hide /><YAxis type="category" dataKey="category" width={100} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <RechartsTooltip formatter={(value: any) => fmtNPR(value)} /><Legend />
                  <Bar dataKey="planned" name="Planned" fill="#4f8ef7" barSize={10} />
                  <Bar dataKey="actual" name="Actual" fill="#ef4444" barSize={10} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="plan-category-breakdown">
              {planComparison.categories.map((item: any) => (
                <button key={item.category} className="plan-category-row" onClick={() => openDrilldown('category', { drilldown_category: item.category })}>
                  <span><strong>{item.category}</strong><small>{item.status === 'UNPLANNED' ? 'Unplanned spending' : item.status === 'OVER_BUDGET' ? 'Over budget' : item.status === 'NO_SPENDING' ? 'No spending yet' : item.status === 'NEAR_LIMIT' ? 'Near limit' : 'On track'}</small></span>
                  <span>{fmtNPR(item.planned)} planned · {fmtNPR(item.actual)} actual · {item.utilization == null ? '—' : `${Number(item.utilization).toFixed(1)}%`}</span>
                </button>
              ))}
            </div>
          </section>
        </div>
      ), document.body)}
    </div>
  );
};

