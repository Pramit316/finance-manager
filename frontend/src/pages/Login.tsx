/**
 * Login page for Supabase Auth.
 *
 * Single-user personal finance app — only one account
 * is created in Supabase Auth dashboard.
 */

import React, { useState, type FormEvent } from 'react';
import { Eye, EyeOff, LockKeyhole, Mail } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import logo from '../assets/branding/fintrack f logo.png';

export const Login: React.FC = () => {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const result = await signIn(email, password);
    if (result.error) {
      setError(result.error);
    }
    setLoading(false);
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <img className="login-logo" src={logo} alt="FinTrack" />
          <h1>FinTrack</h1>
          <p>Personal Finance Tracker</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          <div className="form-group login-field">
            <label htmlFor="login-email">Email</label>
            <div className="login-input-wrap"><Mail size={17} /><input id="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required autoComplete="email" autoFocus /></div>
          </div>

          <div className="form-group login-field">
            <label htmlFor="login-password">Password</label>
            <div className="login-input-wrap"><LockKeyhole size={17} /><input id="login-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" required autoComplete="current-password" /><button type="button" className="password-toggle" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
          </div>

          <button
            type="submit"
            className="btn"
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? (
              <>
                <span
                  className="loader"
                  style={{ marginRight: '8px', width: '16px', height: '16px', borderWidth: '2px' }}
                />
                Signing in…
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
