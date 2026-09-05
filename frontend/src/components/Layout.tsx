import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, List, Upload, FileText, WalletCards, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Layout: React.FC = () => {
  const { signOut, user } = useAuth();

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-icon">₨</div>
          <div>
            <h2 className="sidebar-title">FinTrack</h2>
            <p className="sidebar-subtitle">Personal Tracker</p>
          </div>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <LayoutDashboard size={20} />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/transactions" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <List size={20} />
            <span>Transactions</span>
          </NavLink>
          <NavLink to="/imports" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <FileText size={20} />
            <span>Imports</span>
          </NavLink>
          <NavLink to="/upload" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Upload size={20} />
            <span>Upload</span>
          </NavLink>
          <NavLink to="/budget" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <WalletCards size={20} />
            <span>Monthly Plan</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          {user && (
            <button className="sign-out-btn" onClick={signOut} title={user.email ?? ''}>
              <LogOut size={16} />
              Sign Out
            </button>
          )}
          <div className="sidebar-version">v0.3.0 · Production</div>
        </div>
      </aside>

      <main className="main-content">
        <div className="content-scroll">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

