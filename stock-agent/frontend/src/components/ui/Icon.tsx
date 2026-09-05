/** Minimal line icons -- no icon library dependency for a handful of
 * glyphs. Extracted from `IntelligencePage` so `SideNav`/`TopBar` and any
 * future page can share the same set. */
export function Icon({ path, className = 'h-4 w-4' }: { path: string; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className={className}>
      <path d={path} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export const ICON = {
  core: 'M4 12 L12 4 L20 12 M6 10 V19 H18 V10',
  overview: 'M4 19 V10 M10 19 V5 M16 19 V13 M22 19 H2',
  pulse: 'M3 12 H8 L10 6 L14 18 L16 12 H21',
  sectors: 'M12 3 L20 7.5 V16.5 L12 21 L4 16.5 V7.5 Z M12 3 V21 M4 7.5 L12 12 L20 7.5',
  screener: 'M4 5 H20 M7 5 L7 12 L12 19 L12 12 M17 5 L17 12',
  watchlist: 'M12 4 L14.5 9.5 L20.5 10.3 L16 14.3 L17.2 20.2 L12 17.2 L6.8 20.2 L8 14.3 L3.5 10.3 L9.5 9.5 Z',
  portfolio: 'M4 19 V10 M10 19 V5 M16 19 V13 M22 19 H2',
  archive: 'M3 7 H21 V21 H3 Z M3 7 L5 3 H19 L21 7 M10 12 H14',
  settings: 'M12 15 A3 3 0 1 0 12 9 A3 3 0 1 0 12 15 Z M19 12 A7 7 0 0 0 18.6 10.4 L20.5 8.5 L18.5 6.5 L16.6 8.4 A7 7 0 0 0 15 8 L14.5 5 H9.5 L9 8 A7 7 0 0 0 7.4 8.6 L5.5 6.7 L3.5 8.7 L5.4 10.6 A7 7 0 0 0 5 12 A7 7 0 0 0 5.4 13.6 L3.5 15.5 L5.5 17.5 L7.4 15.6 A7 7 0 0 0 9 16.2 L9.5 19 H14.5 L15 16.2 A7 7 0 0 0 16.6 15.6 L18.5 17.5 L20.5 15.5 L18.6 13.6 A7 7 0 0 0 19 12 Z',
  lock: 'M6 10.5 H18 V19.5 H6 Z M8.5 10.5 V7 A3.5 3.5 0 0 1 15.5 7 V10.5',
  search: 'M11 4 A7 7 0 1 0 11 18 A7 7 0 1 0 11 4 Z M20 20 L16 16',
  bell: 'M6 9 A6 6 0 0 1 18 9 C18 14 20 15 20 15 H4 C4 15 6 14 6 9 Z M10 18 A2 2 0 0 0 14 18',
  send: 'M4 12 L20 4 L14 20 L11 13 L4 12 Z',
  menu: 'M4 7 H20 M4 12 H20 M4 17 H20',
} as const
