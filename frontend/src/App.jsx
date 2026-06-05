import React, { useState, useEffect } from 'react'
import { Activity, Sparkles, Send, Award, AlertTriangle, Play, HelpCircle } from 'lucide-react'

// Backend API connection
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [isOnline, setIsOnline] = useState(true)

  // Suggestion card questions
  const suggestions = [
    {
      title: 'Checkout Anomaly',
      question: 'Why did conversion drop in February?',
      metric: 'Conversion Rate',
      period: 'Feb 2026'
    },
    {
      title: 'Regional Revenue Shock',
      question: 'Why did revenue decrease in Bangalore during late April?',
      metric: 'Revenue',
      period: 'Apr 2026'
    },
    {
      title: 'Category Volume Dip',
      question: 'Why did corporate office supplies orders drop in October?',
      metric: 'Orders Count',
      period: 'Oct 2025'
    },
    {
      title: 'Bangalore Orders Check',
      question: 'Why did orders drop in Bangalore?',
      metric: 'Orders Count',
      period: 'General'
    },
    {
      title: 'Units Sold Snapshot',
      question: 'What were units sold in April 2026?',
      metric: 'Units Sold',
      period: 'Apr 2026'
    }
  ]

  // Query health endpoint on startup
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then(res => res.json())
      .then(data => {
        setIsOnline(data.status === 'healthy' || data.status === 'degraded')
      })
      .catch(() => {
        setIsOnline(false)
      })
  }, [])

  const handleSubmit = async (qText) => {
    const finalQ = qText || question
    if (!finalQ.trim()) return

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await fetch(`${API_BASE}/api/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: finalQ })
      })

      if (!response.ok) {
        throw new Error('Failed to run investigation. Please try again.')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message || 'An error occurred.')
    } finally {
      setLoading(false)
    }
  }

  const handleSuggestClick = (suggestionText) => {
    setQuestion(suggestionText)
    handleSubmit(suggestionText)
  }

  return (
    <div className="container">
      {/* App Header */}
      <header className="header-card">
        <h1 className="brand-title">
          <Activity size={24} />
          AI Root Cause Investigator
        </h1>
        <div className={`status-badge ${isOnline ? '' : 'offline'}`}>
          <div className="status-dot"></div>
          {isOnline ? 'System Online' : 'System Offline'}
        </div>
      </header>

      {/* Predefined suggestion prompts */}
      <section>
        <h3 className="suggestions-title">
          <Sparkles size={16} color="#3b82f6" />
          Predefined Root Cause Investigation Templates
        </h3>
        <div className="suggestions-grid">
          {suggestions.map((s, idx) => (
            <div 
              key={idx} 
              className="suggestion-card"
              onClick={() => handleSuggestClick(s.question)}
            >
              <h4>{s.title}</h4>
              <p>"{s.question}"</p>
              <div style={{ marginTop: '0.8rem', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#64748b' }}>
                <span>{s.metric}</span>
                <span>{s.period}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Console Input Card */}
      <main className="console-card">
        <h3 className="section-title">Investigator Console</h3>
        <form 
          onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
          className="input-group"
        >
          <input 
            type="text"
            className="console-input"
            placeholder="e.g., Why did conversion drop in February? or What were units sold in April 2026?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={loading}
          />
          <button 
            type="submit" 
            className="submit-btn"
            disabled={loading || !question.trim()}
          >
            <Send size={16} />
            Investigate
          </button>
        </form>

        {error && (
          <div style={{ color: '#f43f5e', background: 'rgba(244, 63, 94, 0.1)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(244, 63, 94, 0.2)', fontSize: '0.9rem' }}>
            <strong>Error:</strong> {error}
          </div>
        )}
      </main>

      {/* Loading State */}
      {loading && (
        <div className="loading-wrapper">
          <div className="loader-glow"></div>
          <p className="loading-text">Orchestrating AI Agent Network & Running SQL aggregates...</p>
        </div>
      )}

      {/* Results Section */}
      {result && !loading && (
        <section className="report-container">
          <h3 className="section-title">Root Cause Investigation Report</h3>
          
          {/* Summary Card */}
          <div className="summary-card">
            <p className="summary-text">
              {result.summary}
            </p>
          </div>

          <div className="report-grid">
            {/* Contributors Section */}
            <div className="contributors-card">
              <h4 style={{ marginBottom: '1rem', fontWeight: 600, color: '#f8fafc', fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle size={18} color="#f43f5e" />
                Key Negative Contributors (Dimension Breakdown)
              </h4>
              
              {result.contributors && result.contributors.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table className="contributors-table">
                    <thead>
                      <tr>
                        <th>Dimension</th>
                        <th>Value</th>
                        <th>Impact</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.contributors.map((c, i) => (
                        <tr key={i}>
                          <td><span className="badge-dim">{c.dimension}</span></td>
                          <td style={{ fontWeight: 500 }}>{c.value}</td>
                          <td>
                            <span className="impact-text negative">
                              {c.impact}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', textAlign: 'center', padding: '1.5rem 0' }}>
                  No significant negative contributors detected for this query range.
                </p>
              )}
            </div>

            {/* Confidence Score Gauge */}
            <div className="confidence-card">
              <h4 style={{ fontWeight: 600, color: '#f8fafc', fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Award size={18} color="#3b82f6" />
                Confidence Score
              </h4>
              <div 
                className="gauge-circle"
                style={{ '--deg': `${(result.confidence || 0.0) * 360}deg` }}
              >
                <div className="gauge-value">
                  {Math.round((result.confidence || 0) * 100)}%
                </div>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.5rem' }}>
                Statistical Confidence
              </p>
            </div>
          </div>

          {/* Recommendations Card */}
          <div className="recommendations-card">
            <h4 style={{ marginBottom: '1.2rem', fontWeight: 600, color: '#f8fafc', fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sparkles size={18} color="#fbbf24" />
              Actionable Business Recommendations
            </h4>
            <div className="rec-list">
              {result.recommendations && result.recommendations.map((rec, i) => (
                <div key={i} className="rec-item">
                  <div className="rec-num">{i + 1}</div>
                  <div className="rec-text">{rec}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

export default App
