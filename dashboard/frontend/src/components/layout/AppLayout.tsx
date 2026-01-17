/**
 * AppLayout component.
 * 
 * TailAdmin-style layout with collapsible sidebar, header, and main content area.
 */
import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import './AppLayout.css';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();

  // Auto-collapse sidebar on mobile
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  }, [location.pathname]);

  return (
    <div className="app-layout">
      {/* Sidebar Overlay (mobile) */}
      {sidebarOpen && (
        <div 
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`app-sidebar ${sidebarOpen ? 'open' : ''} ${sidebarCollapsed ? 'collapsed' : ''}`}>
        {/* Sidebar Header */}
        <div className="sidebar-header">
          <NavLink to="/" className="sidebar-logo">
            <div className="logo-icon">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C13.1 2 14 2.9 14 4C14 5.1 13.1 6 12 6C10.9 6 10 5.1 10 4C10 2.9 10.9 2 12 2Z" fill="currentColor"/>
                <path d="M21 9H15V22H13V16H11V22H9V9H3V7H21V9Z" fill="currentColor"/>
                <path opacity="0.3" d="M6 9C5.45 9 5 9.45 5 10V11C5 13.76 7.24 16 10 16H14C16.76 16 19 13.76 19 11V10C19 9.45 18.55 9 18 9H6Z" fill="currentColor"/>
              </svg>
            </div>
            {!sidebarCollapsed && <span className="logo-text">DeltaWash</span>}
          </NavLink>

          <button 
            className="sidebar-collapse-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path 
                d={sidebarCollapsed 
                  ? "M6 10L10 6M6 10L10 14M6 10H14" 
                  : "M14 10L10 6M14 10L10 14M14 10H6"
                } 
                stroke="currentColor" 
                strokeWidth="1.5" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <div className="nav-section">
            {!sidebarCollapsed && <span className="nav-section-title">Menu</span>}
            
            <ul className="nav-list">
              <li>
                <NavLink 
                  to="/" 
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                  end
                >
                  <span className="nav-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3.33334 10.8333V16.6667C3.33334 17.1269 3.70643 17.5 4.16668 17.5H8.33334V12.5H11.6667V17.5H15.8333C16.2936 17.5 16.6667 17.1269 16.6667 16.6667V10.8333" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M1.66666 10L9.41 3.33333C9.75557 3.04444 10.2444 3.04444 10.59 3.33333L18.3333 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </span>
                  {!sidebarCollapsed && <span className="nav-text">Overview</span>}
                </NavLink>
              </li>
            </ul>
          </div>

          <div className="nav-section">
            {!sidebarCollapsed && <span className="nav-section-title">Analytics</span>}
            
            <ul className="nav-list">
              <li>
                <NavLink 
                  to="/" 
                  className="nav-link"
                >
                  <span className="nav-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3.33334 17.5V7.5L10 2.5L16.6667 7.5V17.5H12.5V11.6667H7.50001V17.5H3.33334Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </span>
                  {!sidebarCollapsed && <span className="nav-text">Units</span>}
                </NavLink>
              </li>
                            <li>
                              <NavLink 
                                to="/devices/47378190-96da-1dac-72ff-5d2a386ecbe0"
                                className="nav-link"
                              >
                                <span className="nav-icon">                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M6.66666 2.5V5M13.3333 2.5V5M2.91666 8.5H17.0833M4.16666 3.75H15.8333C16.7538 3.75 17.5 4.49619 17.5 5.41667V15.8333C17.5 16.7538 16.7538 17.5 15.8333 17.5H4.16666C3.24619 17.5 2.5 16.7538 2.5 15.8333V5.41667C2.5 4.49619 3.24619 3.75 4.16666 3.75Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <rect x="5" y="10.8333" width="3.33333" height="3.33333" rx="0.5" stroke="currentColor" strokeWidth="1.5"/>
                    </svg>
                  </span>
                  {!sidebarCollapsed && <span className="nav-text">Devices</span>}
                </NavLink>
              </li>
            </ul>
          </div>
        </nav>

        {/* Sidebar Footer */}
        {!sidebarCollapsed && (
          <div className="sidebar-footer">
            <div className="sidebar-info">
              <span className="sidebar-info-text">Hand Hygiene Compliance</span>
            </div>
          </div>
        )}
      </aside>

      {/* Main Content Area */}
      <div className="app-main">
        {/* Header */}
        <header className="app-header">
          <div className="header-left">
            <button 
              className="sidebar-toggle"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle sidebar"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M4 6H20M4 12H20M4 18H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>

          <div className="header-right">
            <div className="header-status">
              <span className="status-indicator online"></span>
              <span className="status-text">System Online</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="app-content">
          {children}
        </main>
      </div>
    </div>
  );
};
