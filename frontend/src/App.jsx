import { useState, useEffect, useMemo, useCallback, useRef } from 'react'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtValue(v) {
  if (!v) return '$0'
  const n = Math.abs(v)
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (n >= 1e9)  return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6)  return `$${(n / 1e6).toFixed(0)}M`
  if (n >= 1e3)  return `$${(n / 1e3).toFixed(0)}K`
  return `$${n}`
}

function fmtShares(n) {
  if (!n) return '0'
  n = Math.abs(n)
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return String(Math.round(n))
}

function timeAgo(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now - d
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`
  return `${Math.floor(months / 12)}y ago`
}

// ─── Colors / Badges ─────────────────────────────────────────────────────────

const ACTION_COLOR = {
  NEW:       '#58a6ff',
  INCREASED: '#3fb950',
  REDUCED:   '#f85149',
  EXITED:    '#f85149',
  UNCHANGED: '#8b949e',
}

const ACTION_BG = {
  NEW:       'rgba(88,166,255,0.12)',
  INCREASED: 'rgba(63,185,80,0.12)',
  REDUCED:   'rgba(248,81,73,0.12)',
  EXITED:    'rgba(248,81,73,0.12)',
  UNCHANGED: 'rgba(139,148,158,0.1)',
}

const ACTION_LABEL = {
  NEW:       'NEW',
  INCREASED: 'BUY',
  REDUCED:   'SELL',
  EXITED:    'EXIT',
  UNCHANGED: '—',
}

function ActionBadge({ action }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 6px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 700,
      fontFamily: 'var(--font-mono)',
      color: ACTION_COLOR[action] || '#8b949e',
      background: ACTION_BG[action] || 'transparent',
      letterSpacing: '0.05em',
      minWidth: 36,
      textAlign: 'center',
    }}>
      {ACTION_LABEL[action] || action}
    </span>
  )
}

function PutCallBadge({ putCall }) {
  if (!putCall) return null
  const color = putCall === 'PUT' ? '#f85149' : '#3fb950'
  return (
    <span style={{
      display: 'inline-block',
      padding: '0 4px',
      borderRadius: 3,
      fontSize: 10,
      fontWeight: 700,
      fontFamily: 'var(--font-mono)',
      color,
      border: `1px solid ${color}`,
      marginLeft: 4,
      opacity: 0.8,
    }}>
      {putCall}
    </span>
  )
}

function Avatar({ label, size = 32, title }) {
  const colors = [
    ['#1f3a5f', '#58a6ff'],
    ['#1a3d2e', '#3fb950'],
    ['#3d1a1f', '#f85149'],
    ['#2d2a1a', '#d29922'],
    ['#2a1a3d', '#bc8cff'],
  ]
  const idx = (label.charCodeAt(0) + label.charCodeAt(1)) % colors.length
  const [bg, fg] = colors[idx]
  return (
    <div
      title={title}
      style={{
        width: size, height: size,
        borderRadius: '50%',
        background: bg,
        color: fg,
        fontFamily: 'var(--font-mono)',
        fontWeight: 700,
        fontSize: size * 0.35,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
        border: `1px solid ${fg}33`,
        cursor: title ? 'help' : 'default',
      }}>
      {label.slice(0, 2)}
    </div>
  )
}

// ─── Sparkline (native SVG, no deps) ─────────────────────────────────────────

function Sparkline({ values, quarters, width = 110, height = 26, color = '#58a6ff', format }) {
  if (!values || values.length === 0) return null
  const max = Math.max(...values, 1)
  const n = values.length
  const stepX = n > 1 ? width / (n - 1) : 0
  // Reserve a small top/bottom margin so the line never clips
  const pad = height * 0.12
  const usableH = height - pad * 2
  const y = (v) => height - pad - (v / max) * usableH

  const pts = values.map((v, i) => `${(i * stepX).toFixed(1)},${y(v).toFixed(1)}`)
  const linePath = `M ${pts.join(' L ')}`
  const areaPath = `${linePath} L ${(width).toFixed(1)},${height} L 0,${height} Z`

  const lastIdx = n - 1
  const lastVal = values[lastIdx]
  const lastX   = lastIdx * stepX
  const lastY   = y(lastVal)

  // Native browser tooltip listing each non-zero point
  const fmt = format || fmtValue
  const tooltip = quarters
    ? values
        .map((v, i) => (v > 0 ? `${quarters[i]}: ${fmt(v)}` : null))
        .filter(Boolean)
        .join('\n')
    : ''

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <title>{tooltip}</title>
      <path d={areaPath} fill={color} fillOpacity={0.15} />
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
      {lastVal > 0 && (
        <circle cx={lastX} cy={lastY} r={2.2} fill={color} />
      )}
    </svg>
  )
}

// ─── Loading / Error ──────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>⟳</div>
      <div>Loading data...</div>
    </div>
  )
}

function ErrorMsg({ msg }) {
  return (
    <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>⚠</div>
      <div>{msg}</div>
      <div style={{ color: 'var(--text-muted)', marginTop: 8, fontSize: 12 }}>
        Make sure data/frontend/ JSON files have been generated by running the scraper.
      </div>
    </div>
  )
}

// ─── Feed Tab ─────────────────────────────────────────────────────────────────

function FeedTab({ changelog, investors }) {
  const [filter, setFilter] = useState('ALL')
  const [investorFilter, setInvestorFilter] = useState('ALL')
  const [visible, setVisible] = useState(100)

  const filtered = useMemo(() => {
    return changelog.filter(e => {
      if (filter !== 'ALL' && e.action !== filter) return false
      if (investorFilter !== 'ALL' && e.investor_id !== investorFilter) return false
      return true
    })
  }, [changelog, filter, investorFilter])

  const shown = filtered.slice(0, visible)

  const actionFilters = [
    { key: 'ALL',       label: 'All' },
    { key: 'NEW',       label: 'New' },
    { key: 'INCREASED', label: 'Bought' },
    { key: 'REDUCED',   label: 'Sold' },
    { key: 'EXITED',    label: 'Exited' },
  ]

  const invOptions = [
    { id: 'ALL', name: 'All Investors' },
    ...investors.filter(i => i.latest_quarter),
  ]

  return (
    <div>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, padding: '12px 16px', flexWrap: 'wrap', borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {actionFilters.map(f => (
            <button
              key={f.key}
              onClick={() => { setFilter(f.key); setVisible(100) }}
              style={{
                padding: '4px 12px',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: filter === f.key ? 600 : 400,
                background: filter === f.key ? 'var(--surface2)' : 'transparent',
                color: filter === f.key ? 'var(--text)' : 'var(--text-muted)',
                border: filter === f.key ? '1px solid var(--border)' : '1px solid transparent',
                transition: 'all 0.15s',
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
        <select
          value={investorFilter}
          onChange={e => { setInvestorFilter(e.target.value); setVisible(100) }}
          style={{
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
            borderRadius: 6,
            padding: '4px 8px',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          {invOptions.map(i => (
            <option key={i.id} value={i.id}>{i.id === 'ALL' ? 'All Investors' : i.name}</option>
          ))}
        </select>
        <span style={{ color: 'var(--text-muted)', fontSize: 12, alignSelf: 'center', marginLeft: 'auto' }}>
          {filtered.length.toLocaleString()} moves
        </span>
      </div>

      {/* Entries */}
      <div>
        {shown.map((e, i) => (
          <FeedEntry key={i} entry={e} />
        ))}
        {visible < filtered.length && (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <button
              onClick={() => setVisible(v => v + 100)}
              style={{
                padding: '8px 24px',
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--text)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Load more ({filtered.length - visible} remaining)
            </button>
          </div>
        )}
        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
            No entries match the selected filters.
          </div>
        )}
      </div>
    </div>
  )
}

function FeedEntry({ entry }) {
  const color = ACTION_COLOR[entry.action] || '#8b949e'
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '40px 1fr',
      gap: '0 12px',
      padding: '10px 16px',
      borderBottom: '1px solid var(--border)',
      transition: 'background 0.1s',
    }}
    onMouseEnter={e => e.currentTarget.style.background = 'var(--surface)'}
    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <Avatar label={entry.avatar || entry.investor_id} size={36} />
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>{entry.investor}</span>
          <ActionBadge action={entry.action} />
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color, fontSize: 14 }}>
            {entry.ticker}
          </span>
          <PutCallBadge putCall={entry.put_call} />
          <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 'auto' }}>
            {entry.quarter} · {timeAgo(entry.time)}
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>
          {entry.detail}
          {entry.stock_name && entry.stock_name !== entry.ticker && (
            <span style={{ marginLeft: 6, opacity: 0.6 }}>({entry.stock_name})</span>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Conviction Tab ───────────────────────────────────────────────────────────

function ConvictionTab({ conviction, investors, holdings }) {
  const [search, setSearch] = useState('')
  const [visible, setVisible] = useState(50)
  const [expanded, setExpanded] = useState(null)
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [metric, setMetric] = useState('weight')   // 'value' | 'shares' | 'weight'

  const nameToId = useMemo(() => {
    const m = {}
    for (const inv of (investors || [])) m[inv.name] = inv.id
    return m
  }, [investors])

  // Lazy-load position_history.json on the first row expand. ~5MB; cached.
  const ensureHistoryLoaded = useCallback(() => {
    if (history || historyLoading) return
    setHistoryLoading(true)
    const base = import.meta.env.BASE_URL
    fetch(`${base}data/position_history.json`)
      .then(r => r.json())
      .then(d => { setHistory(d); setHistoryLoading(false) })
      .catch(err => { console.error('history load failed', err); setHistoryLoading(false) })
  }, [history, historyLoading])

  const handleToggle = useCallback((ticker) => {
    setExpanded(prev => prev === ticker ? null : ticker)
    ensureHistoryLoaded()
  }, [ensureHistoryLoaded])

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase()
    if (!q) return conviction
    return conviction.filter(c =>
      c.ticker.includes(q) || c.name.toUpperCase().includes(q)
    )
  }, [conviction, search])

  return (
    <div>
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <input
          placeholder="Search ticker or company..."
          value={search}
          onChange={e => { setSearch(e.target.value); setVisible(50) }}
          style={{
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '6px 12px',
            color: 'var(--text)',
            fontSize: 13,
            width: 240,
            outline: 'none',
          }}
        />
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          {filtered.length.toLocaleString()} tickers · cross-investor holdings
        </span>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
            SPARKLINE:
          </span>
          <div style={{ display: 'flex', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, padding: 2 }}>
            {[
              { key: 'shares', label: 'Shares', title: 'Split-adjusted share count (pure buy/sell signal)' },
              { key: 'value',  label: '$ Value', title: 'Position value (mixed with price moves)' },
              { key: 'weight', label: 'Weight %', title: 'Portfolio weight (conviction relative to whole book)' },
            ].map(opt => (
              <button
                key={opt.key}
                title={opt.title}
                onClick={() => setMetric(opt.key)}
                style={{
                  padding: '4px 10px',
                  borderRadius: 4,
                  fontSize: 12,
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 600,
                  background: metric === opt.key ? 'var(--bg)' : 'transparent',
                  color: metric === opt.key ? 'var(--text)' : 'var(--text-muted)',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
              {['#', 'Ticker', 'Company', 'Holders', 'Total Value', 'New?'].map(h => (
                <th key={h} style={{ padding: '8px 16px', textAlign: 'left', fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, visible).map((c, i) => (
              <ConvictionRow
                key={c.ticker}
                rank={i + 1}
                data={c}
                isExpanded={expanded === c.ticker}
                onToggle={() => handleToggle(c.ticker)}
                nameToId={nameToId}
                holdings={holdings}
                history={history}
                historyLoading={historyLoading}
                metric={metric}
              />
            ))}
          </tbody>
        </table>
        {visible < filtered.length && (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <button
              onClick={() => setVisible(v => v + 50)}
              style={{
                padding: '8px 24px',
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--text)',
                fontSize: 13,
              }}
            >
              Load more
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function ConvictionRow({ rank, data, isExpanded, onToggle, nameToId, holdings, history, historyLoading, metric }) {
  const topHolders = data.holders.slice(0, 5)
  return (
    <>
      <tr
        onClick={onToggle}
        style={{
          borderBottom: '1px solid var(--border)',
          cursor: 'pointer',
          background: isExpanded ? 'var(--surface)' : 'transparent',
        }}
        onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = 'var(--surface)' }}
        onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = 'transparent' }}
      >
        <td style={{ padding: '10px 16px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          <span style={{ marginRight: 6, color: 'var(--text-muted)' }}>{isExpanded ? '▾' : '▸'}</span>
          {rank}
        </td>
        <td style={{ padding: '10px 16px' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--blue)', fontSize: 14 }}>
            {data.ticker}
          </span>
        </td>
        <td style={{ padding: '10px 16px', color: 'var(--text-muted)', fontSize: 13 }}>
          {data.name}
        </td>
        <td style={{ padding: '10px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              color: data.holder_count >= 5 ? 'var(--green)' : data.holder_count >= 3 ? 'var(--yellow)' : 'var(--text)',
              marginRight: 6,
            }}>
              {data.holder_count}
            </span>
            <div style={{ display: 'flex', gap: 3 }}>
              {topHolders.map(name => (
                <Avatar
                  key={name}
                  label={name.split(' ').map(w => w[0]).join('').slice(0, 2)}
                  size={20}
                  title={name}
                />
              ))}
              {data.holders.length > 5 && (
                <span
                  title={data.holders.slice(5).join(', ')}
                  style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center', cursor: 'help' }}
                >
                  +{data.holders.length - 5}
                </span>
              )}
            </div>
          </div>
        </td>
        <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {fmtValue(data.total_value)}
        </td>
        <td style={{ padding: '10px 16px' }}>
          {data.any_new && (
            <span style={{ color: 'var(--blue)', fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>NEW</span>
          )}
        </td>
      </tr>
      {isExpanded && (
        <ConvictionExpansionRow
          data={data}
          nameToId={nameToId}
          holdings={holdings}
          history={history}
          historyLoading={historyLoading}
          metric={metric}
        />
      )}
    </>
  )
}

// Sparkline value-formatter per metric mode
const METRIC_FMT = {
  value:  (v) => fmtValue(v),
  shares: (v) => fmtShares(v) + ' sh',
  weight: (v) => `${v.toFixed(1)}%`,
}
const METRIC_KEY = { value: 'v', shares: 's', weight: 'w' }
const METRIC_LABEL = { value: '$ Value', shares: 'Shares (split-adj)', weight: 'Weight %' }

function ConvictionExpansionRow({ data, nameToId, holdings, history, historyLoading, metric }) {
  // Sparkline lookup: build id -> {values per metric, quarters} from history payload
  const sparkLookup = useMemo(() => {
    if (!history) return null
    const series = history.tickers?.[data.ticker] || []
    const arrKey = METRIC_KEY[metric] || 'v'
    const m = {}
    for (const s of series) {
      m[s.id] = { values: s[arrKey] || [], quarters: history.quarters }
    }
    return m
  }, [history, data.ticker, metric])

  const fmt = METRIC_FMT[metric] || fmtValue
  const hasSplit = history?.splits?.[data.ticker]?.length > 0

  // Build per-holder details by looking up each holder's position in this ticker.
  const rows = data.holders.map(name => {
    const id = nameToId?.[name]
    const inv = id && holdings?.[id]
    const matches = inv?.holdings?.filter(h => h.ticker === data.ticker) || []
    // Aggregate over multiple rows (e.g. common stock + CALL/PUT options)
    const totalShares = matches.reduce((s, h) => s + (h.shares || 0), 0)
    const totalValue  = matches.reduce((s, h) => s + (h.value  || 0), 0)
    const totalWeight = matches.reduce((s, h) => s + (h.weight || 0), 0)
    const isNew       = matches.some(h => h.is_new)
    const putCall     = matches.find(h => h.put_call)?.put_call
    const changePct   = matches.find(h => h.change_pct != null)?.change_pct
    return { name, id, quarter: inv?.quarter, totalShares, totalValue, totalWeight, isNew, putCall, changePct }
  }).sort((a, b) => b.totalValue - a.totalValue)

  return (
    <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
      <td colSpan={6} style={{ padding: '0 16px 14px 32px' }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', padding: '8px 0 6px' }}>
          {rows.length} holders · sorted by position size
          {hasSplit && (
            <span style={{ marginLeft: 12, color: 'var(--yellow)', textTransform: 'none', letterSpacing: 0 }}>
              ⚠ {data.ticker} had a stock split — share counts are split-adjusted
            </span>
          )}
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ color: 'var(--text-muted)', fontSize: 11, textAlign: 'left' }}>
              <th style={{ padding: '4px 8px', fontWeight: 600 }}>Investor</th>
              <th style={{ padding: '4px 8px', fontWeight: 600 }}>Trajectory · {METRIC_LABEL[metric] || ''}</th>
              <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'right' }}>Shares</th>
              <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'right' }}>Value</th>
              <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'right' }}>Weight</th>
              <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'right' }}>QoQ</th>
              <th style={{ padding: '4px 8px', fontWeight: 600 }}>Flag</th>
              <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'right' }}>Quarter</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const spark = sparkLookup?.[r.id]
              // Color trend: green if rising into latest, red if falling, blue baseline
              let sparkColor = '#58a6ff'
              if (spark && spark.values.length >= 2) {
                const last = spark.values[spark.values.length - 1]
                const prev = spark.values[spark.values.length - 2]
                if (last > prev) sparkColor = '#3fb950'
                else if (last < prev) sparkColor = '#f85149'
              }
              return (
                <tr key={r.name} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '6px 8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Avatar
                        label={r.name.split(' ').map(w => w[0]).join('').slice(0, 2)}
                        size={20}
                        title={r.name}
                      />
                      <span>{r.name}</span>
                    </div>
                  </td>
                  <td style={{ padding: '6px 8px' }}>
                    {spark
                      ? <Sparkline values={spark.values} quarters={spark.quarters} color={sparkColor} format={fmt} />
                      : <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                          {historyLoading ? 'loading…' : '—'}
                        </span>
                    }
                  </td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}>
                    {fmtShares(r.totalShares)}
                  </td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}>
                    {fmtValue(r.totalValue)}
                  </td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right', color: 'var(--text-muted)' }}>
                    {r.totalWeight ? `${r.totalWeight.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{
                    padding: '6px 8px',
                    fontFamily: 'var(--font-mono)',
                    textAlign: 'right',
                    color: r.changePct == null ? 'var(--text-muted)' : r.changePct >= 0 ? 'var(--green)' : 'var(--red)',
                  }}>
                    {r.changePct == null ? '—' : `${r.changePct >= 0 ? '+' : ''}${r.changePct.toFixed(1)}%`}
                  </td>
                  <td style={{ padding: '6px 8px' }}>
                    {r.isNew && <span style={{ color: 'var(--blue)', fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)', marginRight: 6 }}>NEW</span>}
                    {r.putCall && <PutCallBadge putCall={r.putCall} />}
                  </td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right', color: 'var(--text-muted)', fontSize: 12 }}>
                    {r.quarter || '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </td>
    </tr>
  )
}

// ─── Investors Tab ────────────────────────────────────────────────────────────

function InvestorsTab({ investors, holdings }) {
  const [selected, setSelected] = useState(null)
  const panelRef = useRef(null)

  const active = investors.filter(i => i.latest_quarter)
  const pending = investors.filter(i => !i.latest_quarter)

  // Smooth-scroll the drill-down into view whenever a new investor is opened.
  // Wait one frame so the panel has been rendered before scrolling.
  useEffect(() => {
    if (!selected || !panelRef.current) return
    requestAnimationFrame(() => {
      panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [selected])

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12, marginBottom: 24 }}>
        {active.map(inv => (
          <InvestorCard
            key={inv.id}
            investor={inv}
            isSelected={selected === inv.id}
            onClick={() => setSelected(selected === inv.id ? null : inv.id)}
          />
        ))}
      </div>

      {/* Drill-down panel -- scroll-margin-top offsets the sticky header */}
      {selected && holdings[selected] && (
        <div ref={panelRef} style={{ scrollMarginTop: 70 }}>
          <HoldingsPanel
            investor={investors.find(i => i.id === selected)}
            data={holdings[selected]}
            onClose={() => setSelected(null)}
          />
        </div>
      )}

      {pending.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 8, fontFamily: 'var(--font-mono)' }}>
            NO DATA AVAILABLE
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {pending.map(inv => (
              <div key={inv.id} style={{
                padding: '6px 12px',
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--text-muted)',
                fontSize: 13,
              }}>
                <Avatar label={inv.avatar || inv.name} size={20} />
                <span style={{ marginLeft: 6 }}>{inv.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function InvestorCard({ investor, isSelected, onClick }) {
  const inv = investor
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--surface)',
        border: `1px solid ${isSelected ? 'var(--blue)' : 'var(--border)'}`,
        borderRadius: 8,
        padding: 16,
        cursor: 'pointer',
        transition: 'border-color 0.15s, background 0.15s',
      }}
      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.borderColor = 'var(--text-muted)' }}
      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.borderColor = 'var(--border)' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <Avatar label={inv.avatar || inv.name} size={40} />
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{inv.name}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{inv.fund}</div>
        </div>
        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 15, color: 'var(--green)' }}>
            {fmtValue(inv.total_value)}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{inv.latest_quarter}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
        <Stat label="Holdings" value={inv.num_holdings?.toLocaleString()} />
        <Stat label="New" value={inv.num_new} color="var(--blue)" />
      </div>

      {/* Top holdings bar */}
      {inv.top_holdings?.length > 0 && (
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 4, fontFamily: 'var(--font-mono)' }}>TOP HOLDINGS</div>
          {inv.top_holdings.slice(0, 3).map((h, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--blue)', minWidth: 60 }}>
                {h.ticker}
              </span>
              {h.put_call && <PutCallBadge putCall={h.put_call} />}
              <div style={{ flex: 1, height: 4, background: 'var(--surface2)', borderRadius: 2 }}>
                <div style={{ height: '100%', width: `${Math.min(h.weight, 100)}%`, background: 'var(--blue)', borderRadius: 2, opacity: 0.7 }} />
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', minWidth: 36, textAlign: 'right' }}>
                {h.weight?.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 10, color: isSelected ? 'var(--blue)' : 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
        {isSelected ? '▲ Hide holdings' : '▼ View all holdings'}
      </div>
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div>
      <div style={{ color: color || 'var(--text)', fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 18 }}>{value ?? '—'}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{label}</div>
    </div>
  )
}

function HoldingsPanel({ investor, data, onClose }) {
  const [search, setSearch] = useState('')
  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase()
    if (!q) return data.holdings
    return data.holdings.filter(h =>
      h.ticker?.toUpperCase().includes(q) || h.name?.toUpperCase().includes(q)
    )
  }, [data.holdings, search])

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      marginBottom: 16,
      overflow: 'hidden',
    }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <Avatar label={investor.avatar || investor.name} size={28} />
        <div>
          <span style={{ fontWeight: 600 }}>{investor.name}</span>
          <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 8 }}>
            {data.quarter} · {data.num_holdings?.toLocaleString()} holdings
            {data.num_holdings > 200 && ' (showing top 200 by value)'}
          </span>
        </div>
        <input
          placeholder="Filter..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            marginLeft: 'auto',
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '4px 10px',
            color: 'var(--text)',
            fontSize: 12,
            width: 160,
            outline: 'none',
          }}
        />
        <button
          onClick={onClose}
          style={{ color: 'var(--text-muted)', fontSize: 20, padding: '0 4px', lineHeight: 1 }}
        >
          ×
        </button>
      </div>

      <div style={{ overflowX: 'auto', maxHeight: 400, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--surface)', zIndex: 1 }}>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Ticker', 'Name', 'Shares', 'Value', 'Weight', 'Change', 'Type'].map(h => (
                <th key={h} style={{ padding: '6px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((h, i) => (
              <HoldingRow key={i} h={h} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function HoldingRow({ h }) {
  const isNew = h.is_new
  const changePct = h.change_pct
  let changeColor = 'var(--text-muted)'
  let changeStr = '—'
  if (changePct !== null && changePct !== undefined) {
    changeColor = changePct > 0 ? 'var(--green)' : 'var(--red)'
    changeStr = `${changePct > 0 ? '+' : ''}${changePct.toFixed(1)}%`
  }

  return (
    <tr
      style={{ borderBottom: '1px solid var(--border)' }}
      onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <td style={{ padding: '7px 12px' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: isNew ? 'var(--blue)' : 'var(--text)', fontSize: 13 }}>
          {h.ticker}
        </span>
        {isNew && <span style={{ marginLeft: 4, fontSize: 10, color: 'var(--blue)', fontFamily: 'var(--font-mono)' }}>NEW</span>}
      </td>
      <td style={{ padding: '7px 12px', color: 'var(--text-muted)', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {h.name}
      </td>
      <td style={{ padding: '7px 12px', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
        {fmtShares(h.shares)}
      </td>
      <td style={{ padding: '7px 12px', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
        {fmtValue(h.value)}
      </td>
      <td style={{ padding: '7px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 60, height: 3, background: 'var(--surface2)', borderRadius: 2 }}>
            <div style={{ height: '100%', width: `${Math.min(h.weight || 0, 100)}%`, background: 'var(--blue)', borderRadius: 2 }} />
          </div>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
            {(h.weight || 0).toFixed(1)}%
          </span>
        </div>
      </td>
      <td style={{ padding: '7px 12px', fontFamily: 'var(--font-mono)', fontSize: 12, color: changeColor }}>
        {changeStr}
      </td>
      <td style={{ padding: '7px 12px' }}>
        <PutCallBadge putCall={h.put_call} />
      </td>
    </tr>
  )
}

// ─── Calendar Tab ─────────────────────────────────────────────────────────────

const FILING_DEADLINES = [
  { label: 'Q3 2024', quarter_end: '2024-09-30', deadline: '2024-11-14', filed: true },
  { label: 'Q4 2024', quarter_end: '2024-12-31', deadline: '2025-02-14', filed: true },
  { label: 'Q1 2025', quarter_end: '2025-03-31', deadline: '2025-05-15', filed: true },
  { label: 'Q2 2025', quarter_end: '2025-06-30', deadline: '2025-08-14', filed: true },
  { label: 'Q3 2025', quarter_end: '2025-09-30', deadline: '2025-11-14', filed: true },
  { label: 'Q4 2025', quarter_end: '2025-12-31', deadline: '2026-02-14', filed: false },
  { label: 'Q1 2026', quarter_end: '2026-03-31', deadline: '2026-05-15', filed: false },
  { label: 'Q2 2026', quarter_end: '2026-06-30', deadline: '2026-08-14', filed: false },
  { label: 'Q3 2026', quarter_end: '2026-09-30', deadline: '2026-11-14', filed: false },
  { label: 'Q4 2026', quarter_end: '2026-12-31', deadline: '2027-02-14', filed: false },
]

function useCountdown(targetDate) {
  const [remaining, setRemaining] = useState('')

  useEffect(() => {
    function update() {
      const now = new Date()
      const target = new Date(targetDate + 'T23:59:59')
      const diff = target - now
      if (diff <= 0) { setRemaining('FILING WINDOW OPEN'); return }
      const d = Math.floor(diff / 86400000)
      const h = Math.floor((diff % 86400000) / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      if (d > 0) setRemaining(`${d}d ${h}h ${m}m`)
      else if (h > 0) setRemaining(`${h}h ${m}m ${s}s`)
      else setRemaining(`${m}m ${s}s`)
    }
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [targetDate])

  return remaining
}

function CalendarTab() {
  const now = new Date()
  const nextDeadline = FILING_DEADLINES.find(d => new Date(d.deadline) >= now && !d.filed)
  const countdown = useCountdown(nextDeadline?.deadline || '2099-12-31')

  return (
    <div style={{ padding: 16 }}>
      {/* Countdown hero */}
      {nextDeadline && (
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: 24,
          marginBottom: 20,
          textAlign: 'center',
        }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-mono)', marginBottom: 8, letterSpacing: '0.1em' }}>
            NEXT 13F FILING DEADLINE
          </div>
          <div style={{ fontSize: 36, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--yellow)', marginBottom: 4 }}>
            {countdown}
          </div>
          <div style={{ color: 'var(--text)', fontSize: 16, fontWeight: 600 }}>
            {nextDeadline.label} · Due {nextDeadline.deadline}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
            Quarter ended {nextDeadline.quarter_end} · 45-day filing window
          </div>
        </div>
      )}

      {/* Timeline */}
      <div style={{ display: 'grid', gap: 8 }}>
        {FILING_DEADLINES.map((d, i) => {
          const deadlineDate = new Date(d.deadline)
          const isPast = deadlineDate < now
          const isNext = d === nextDeadline
          return (
            <div key={i} style={{
              display: 'grid',
              gridTemplateColumns: '100px 1fr auto',
              gap: 12,
              alignItems: 'center',
              padding: '10px 16px',
              background: isNext ? 'rgba(210,153,34,0.08)' : 'var(--surface)',
              border: `1px solid ${isNext ? 'var(--yellow)' : 'var(--border)'}`,
              borderRadius: 6,
              opacity: isPast && d.filed ? 0.5 : 1,
            }}>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: isNext ? 'var(--yellow)' : 'var(--text)', fontSize: 14 }}>
                  {d.label}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                  {d.quarter_end}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 13 }}>13F-HR filing deadline</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Due: {d.deadline}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                {d.filed ? (
                  <span style={{ color: 'var(--green)', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700 }}>FILED</span>
                ) : isPast ? (
                  <span style={{ color: 'var(--yellow)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>FILING...</span>
                ) : isNext ? (
                  <span style={{ color: 'var(--yellow)', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700 }}>UPCOMING</span>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>FUTURE</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 20, padding: 16, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.8 }}>
          <div style={{ color: 'var(--text)', fontWeight: 600, marginBottom: 8 }}>About 13F Filings</div>
          <div>· Institutional investors with over $100M in AUM must file Form 13F with the SEC</div>
          <div>· Filings are due within 45 days of each quarter end</div>
          <div>· Only long equity positions are disclosed (no short positions, bonds, or private holdings)</div>
          <div>· Data is delayed ~45 days from the quarter end date</div>
          <div>· Options (PUT/CALL) are disclosed but indicate position hedges, not directional bets</div>
        </div>
      </div>
    </div>
  )
}

// ─── Header ───────────────────────────────────────────────────────────────────

function Header({ activeTab, setActiveTab, investorCount, lastUpdated }) {
  const TABS = [
    { key: 'feed',       label: 'Feed',       icon: '⚡' },
    { key: 'conviction', label: 'Conviction',  icon: '🎯' },
    { key: 'investors',  label: 'Investors',   icon: '🏛' },
    { key: 'calendar',   label: 'Calendar',    icon: '📅' },
  ]

  return (
    <header style={{
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '10px 0' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 16, color: 'var(--green)' }}>
              13F TRACKER
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              {investorCount} superinvestors · SEC 13F filings
            </div>
          </div>
          <nav style={{ display: 'flex', gap: 2, marginLeft: 'auto' }}>
            {TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: activeTab === tab.key ? 600 : 400,
                  background: activeTab === tab.key ? 'var(--surface2)' : 'transparent',
                  color: activeTab === tab.key ? 'var(--text)' : 'var(--text-muted)',
                  border: activeTab === tab.key ? '1px solid var(--border)' : '1px solid transparent',
                  transition: 'all 0.15s',
                }}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>
    </header>
  )
}

// ─── App Root ─────────────────────────────────────────────────────────────────

export default function App() {
  const [tab, setTab] = useState('feed')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const base = import.meta.env.BASE_URL
    Promise.all([
      fetch(`${base}data/changelog.json`).then(r => r.json()),
      fetch(`${base}data/conviction.json`).then(r => r.json()),
      fetch(`${base}data/investors_summary.json`).then(r => r.json()),
      fetch(`${base}data/latest_holdings.json`).then(r => r.json()),
    ])
      .then(([changelog, conviction, investors, holdings]) => {
        setData({ changelog, conviction, investors, holdings })
        setLoading(false)
      })
      .catch(err => {
        setError(err.message || 'Failed to load data')
        setLoading(false)
      })
  }, [])

  const activeInvestors = data ? data.investors.filter(i => i.latest_quarter) : []

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <Header
        activeTab={tab}
        setActiveTab={setTab}
        investorCount={activeInvestors.length}
        lastUpdated={data?.changelog?.[0]?.time}
      />
      <main style={{ maxWidth: 1200, margin: '0 auto' }}>
        {loading && <Spinner />}
        {error && <ErrorMsg msg={error} />}
        {data && (
          <>
            {tab === 'feed' && (
              <FeedTab changelog={data.changelog} investors={data.investors} />
            )}
            {tab === 'conviction' && (
              <ConvictionTab conviction={data.conviction} investors={data.investors} holdings={data.holdings} />
            )}
            {tab === 'investors' && (
              <InvestorsTab investors={data.investors} holdings={data.holdings} />
            )}
            {tab === 'calendar' && (
              <CalendarTab />
            )}
          </>
        )}
      </main>
    </div>
  )
}
