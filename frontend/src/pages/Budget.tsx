import React, { useEffect, useState } from 'react';
import { Plus, Save } from 'lucide-react';
import { API } from '../config';
import { authFetch } from '../lib/api';
const money = (value: string | number | null | undefined) => `NPR ${new Intl.NumberFormat('en-NP', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0))}`;
type Allocation = { category: string; planned_amount: string; allocation_type: string };

export const Budget: React.FC = () => {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [budget, setBudget] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [income, setIncome] = useState('45000');
  const [saving, setSaving] = useState('');
  const [allocations, setAllocations] = useState<Allocation[]>([
    { category: 'Lunch', planned_amount: '1600', allocation_type: 'CONSUMPTION' },
    { category: 'Ghar Kharcha', planned_amount: '3000', allocation_type: 'CONSUMPTION' },
    { category: 'Mero Kharcha', planned_amount: '5000', allocation_type: 'CONSUMPTION' },
    { category: 'Miscellaneous', planned_amount: '3000', allocation_type: 'CONSUMPTION' },
    { category: 'Investment', planned_amount: '5000', allocation_type: 'INVESTMENT' },
  ]);
  const [message, setMessage] = useState('');

  const load = async () => {
    const res = await authFetch(`${API}/api/budgets/${year}/${month}`);
    if (res.ok) { const data = await res.json(); setBudget(data); setIncome(data.expected_income); setSaving(data.planned_saving || ''); setAllocations(data.allocations); }
    else setBudget(null);
    const comparisonRes = await authFetch(`${API}/api/analytics/budget?year=${year}&month=${month}`);
    setComparison(comparisonRes.ok ? await comparisonRes.json() : null);
  };
  useEffect(() => { load(); }, [year, month]);

  const save = async () => {
    const payload = { year, month, expected_income: income, planned_saving: saving || null, allocations };
    const res = await authFetch(budget ? `${API}/api/budgets/${budget.id}` : `${API}/api/budgets`, { method: budget ? 'PATCH' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (res.ok) { setMessage('Plan saved'); await load(); } else setMessage('Could not save plan');
  };
  const updateAllocation = (index: number, field: keyof Allocation, value: string) => setAllocations(items => items.map((item, i) => i === index ? { ...item, [field]: value } : item));

  return <div className="page-container">
    <div className="page-header"><div><h2>Monthly Plan</h2><p className="page-subtitle">Plan consumption and wealth allocation separately.</p></div><button className="btn" onClick={save}><Save size={16} /> Save Plan</button></div>
    <div className="filters-bar"><div className="filter-group"><select value={year} onChange={e => setYear(Number(e.target.value))}>{[year - 1, year, year + 1].map(y => <option key={y}>{y}</option>)}</select><select value={month} onChange={e => setMonth(Number(e.target.value))}>{Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{new Date(2000, i).toLocaleString('default', { month: 'long' })}</option>)}</select></div></div>
    <div className="card"><div className="form-grid"><div className="form-group"><label>Expected income</label><input type="number" min="0" step="0.01" value={income} onChange={e => setIncome(e.target.value)} /></div><div className="form-group"><label>Planned saving (optional)</label><input type="number" min="0" step="0.01" value={saving} onChange={e => setSaving(e.target.value)} placeholder="Derived from allocations" /></div></div><h3>Allocations</h3>{allocations.map((item, index) => <div key={index} className="form-grid" style={{ alignItems: 'end' }}><div className="form-group"><label>Category</label><input type="text" value={item.category} onChange={e => updateAllocation(index, 'category', e.target.value)} /></div><div className="form-group"><label>Planned amount</label><input type="number" min="0" step="0.01" value={item.planned_amount} onChange={e => updateAllocation(index, 'planned_amount', e.target.value)} /></div><div className="form-group"><label>Allocation type</label><select value={item.allocation_type} onChange={e => updateAllocation(index, 'allocation_type', e.target.value)}><option value="CONSUMPTION">Consumption</option><option value="INVESTMENT">Investment</option></select></div><button className="icon-btn" title="Remove allocation" onClick={() => setAllocations(items => items.filter((_, i) => i !== index))}><Plus size={16} style={{ transform: 'rotate(45deg)' }} /></button></div>)}<button className="btn-ghost" onClick={() => setAllocations(items => [...items, { category: '', planned_amount: '0', allocation_type: 'CONSUMPTION' }])}><Plus size={15} /> Add allocation</button></div>
    {message && <div className="result-banner success">{message}</div>}
    {comparison && <><div className="stat-grid">{[['Planned Income', comparison.planned_income], ['Actual Income', comparison.actual_income], ['Planned Consumption', comparison.planned_consumption], ['Actual Consumption', comparison.actual_consumption], ['Planned Investment', comparison.planned_investment], ['Actual Investment', comparison.actual_investment], ['Planned Saving', comparison.planned_saving], ['Actual Saving', comparison.actual_saving]].map(([label, value]) => <div className="stat-item" key={String(label)}><div className="stat-label">{label}</div><div className="stat-value">{money(value as string)}</div></div>)}</div><div className="card"><h3>Planned vs actual</h3><div className="table-scroll"><table className="txn-table"><thead><tr><th>Category</th><th>Planned</th><th>Actual</th><th>Variance</th><th>Used</th><th>Status</th></tr></thead><tbody>{comparison.allocations.map((item: any) => <tr key={item.category}><td>{item.category}</td><td>{money(item.planned)}</td><td>{money(item.actual)}</td><td className={item.variance > 0 ? 'negative' : 'positive'}>{money(item.variance)}</td><td>{item.percentage_used == null ? '—' : `${item.percentage_used.toFixed(1)}%`}</td><td>{item.status}</td></tr>)}</tbody></table></div></div></>}
  </div>;
};