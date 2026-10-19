import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// IBM Plex servida pelo próprio site (sem Google Fonts), só o subconjunto latino,
// nos pesos usados em docs/DESIGN.md (700 é o da marca no topo).
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-sans/latin-700.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
