export function SiteHeader() {
  return (
    <header className="topo">
      <div className="container">
        <a className="marca" href="/">
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
            <circle cx="14" cy="14" r="12.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="14" cy="14" r="7.5" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.45" />
            <path d="M14 14 L14 1.5 A12.5 12.5 0 0 1 24.8 7.75 Z" fill="var(--primary)" />
            <circle cx="14" cy="14" r="2" fill="currentColor" />
          </svg>
          Radar Público
        </a>
        {/* "Sobre os dados", "API" e o menu do celular entram quando essas páginas existirem. */}
        <nav className="nav" aria-label="Principal">
          <a href="/" aria-current="page">
            Buscar
          </a>
        </nav>
      </div>
    </header>
  )
}
