import { NavLink, Outlet } from 'react-router-dom'
import { paths } from '../routes/paths'

const SETTINGS_NAV = [
  { label: 'Data Sources', to: paths.settings('data-sources') },
  { label: 'Data Quality', to: paths.settings('data-quality') },
  { label: 'Model Performance', to: paths.settings('model-performance') },
  { label: 'System', to: paths.settings('system') },
]

export function SettingsLayout() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 pb-32 pt-8 sm:px-6">
      <h1 className="text-xl font-bold">Settings</h1>
      <nav aria-label="Settings sections" className="flex gap-1 border-b border-[var(--color-border)]">
        {SETTINGS_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `shrink-0 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'border-[var(--color-accent)] text-[var(--color-text)]'
                  : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="flex flex-col gap-6">
        <Outlet />
      </div>
    </main>
  )
}
