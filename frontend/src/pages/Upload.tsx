import React, { useState } from 'react';

export const Upload: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState('NABIL');
  const [accountId, setAccountId] = useState(''); // Empty default for automatic inference
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source', source);
    formData.append('account_id', accountId);

    try {
      const response = await fetch('http://localhost:8000/api/imports/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.detail || 'Upload failed');
      }

      const data = await response.json();
      setResult(data);
      
      // Auto-run classification and transfer matching after upload
      await fetch('http://localhost:8000/api/transactions/run-classification', { method: 'POST' });
      await fetch('http://localhost:8000/api/transactions/match-transfers', { method: 'POST' });
      
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="card max-w-2xl">
        <h2>Import Statement</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
          Upload your financial statements to consolidate your transactions.
        </p>

        <form onSubmit={handleUpload}>
          <div className="form-group">
            <label>Account ID (Optional - will infer from statement if blank)</label>
            <input 
              type="text" 
              value={accountId} 
              onChange={(e) => setAccountId(e.target.value)}
              placeholder="Leave blank to auto-detect/create account"
            />
          </div>

          <div className="form-group">
            <label>Statement Source</label>
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="NABIL">Nabil Bank (PDF)</option>
              <option value="ESEWA">eSewa Wallet (XLS)</option>
              <option value="STANDARD_CHARTERED">Standard Chartered Bank (PDF)</option>
            </select>
          </div>

          <div className="form-group">
            <div className={`file-upload-wrapper ${file ? 'has-file' : ''}`}>
              <div className="file-upload-btn">
                <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                {file ? file.name : 'Click or drag file to upload'}
              </div>
              <input type="file" onChange={handleFileChange} required />
            </div>
          </div>

          <button type="submit" className="btn" disabled={!file || isUploading} style={{ width: '100%' }}>
            {isUploading ? (
              <><span className="loader" style={{ marginRight: '8px', width: '16px', height: '16px', borderWidth: '2px' }}></span> Processing...</>
            ) : 'Upload Statement'}
          </button>
        </form>
      </div>

      {error && (
        <div className="result-banner error mt-4 max-w-2xl">
          <h3 style={{ color: 'var(--error)' }}>Import Failed</h3>
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="result-banner success mt-4 max-w-2xl">
          <h3 style={{ color: 'var(--success)' }}>Import Successful</h3>
          
          <div className="stat-grid">
            <div className="stat-item">
              <div className="stat-label">Transactions Inserted</div>
              <div className="stat-value">{result.rows_inserted}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Duplicates Skipped</div>
              <div className="stat-value">{result.duplicate_rows}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Total Deposits</div>
              <div className="stat-value" style={{ color: 'var(--success)' }}>
                +{result.total_credit} {result.currency}
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Total Withdrawals</div>
              <div className="stat-value" style={{ color: 'var(--error)' }}>
                -{result.total_debit} {result.currency}
              </div>
            </div>
          </div>
          
          {result.reconciliation_status === 'FAILED' && (
            <div style={{ marginTop: '1rem', color: 'var(--error)' }}>
              <strong>Warning:</strong> Statement reconciliation failed. Difference: {result.reconciliation_difference} {result.currency}
            </div>
          )}
          
          <p style={{ marginTop: '1.5rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Period: {result.period_from} to {result.period_to}
          </p>
        </div>
      )}
    </div>
  );
};
