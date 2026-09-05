import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, List, Upload, FileText, WalletCards } from 'lucide-react';

export const Layout: React.FC = () => {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-icon">₨</div>
          <div>
            <h2 className="sidebar-title">Finance AI</h2>
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
          <div className="sidebar-version">v0.2.0 · Phase 2</div>
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
