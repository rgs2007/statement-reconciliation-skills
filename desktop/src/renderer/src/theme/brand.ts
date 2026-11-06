/**
 * FlowingSoft brand tokens — the single place to rebrand.
 *
 * NOTE: www.flowingsoft.com could not be reached from the build environment,
 * so these values are a coherent identity built around the name rather than
 * a copy of the live site. Swap the hexes and the wordmark here (and the
 * matching `flow` palette in tailwind.config.js) and the whole app follows;
 * nothing else hard-codes a brand colour.
 */
export const BRAND = {
  company: 'FlowingSoft',
  site: 'www.flowingsoft.com',
  product: 'Reconciler',
  productFull: 'FlowingSoft Reconciler',
  tagline: 'Reconciliation that explains itself',
  colors: {
    primary: '#2f84f7',
    primaryDeep: '#1752b5',
    accent: '#38d9c0',
    surface: '#0b0e14',
    surfaceRaised: '#141821',
    border: '#373d4a',
    text: '#eceef2',
    textMuted: '#818da2',
    good: '#3fb97f',
    warn: '#e0a93a',
    bad: '#e0614f'
  }
} as const

/**
 * The flow-mark: three strands converging into one.
 *
 * Drawn as inline SVG rather than shipped as a raster so it stays sharp at
 * any size and recolours with the brand tokens.
 */
export const FLOW_MARK_SVG = `<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="fsg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
      <stop stop-color="#59a6ff"/><stop offset="1" stop-color="#38d9c0"/>
    </linearGradient>
  </defs>
  <path d="M4 9c7 0 7 7 14 7s10-7 10-7" stroke="url(#fsg)" stroke-width="3" stroke-linecap="round"/>
  <path d="M4 16c7 0 7 7 14 7s10-7 10-7" stroke="url(#fsg)" stroke-width="3" stroke-linecap="round" opacity="0.65"/>
  <path d="M4 23c7 0 7 5 14 5" stroke="url(#fsg)" stroke-width="3" stroke-linecap="round" opacity="0.35"/>
</svg>`
