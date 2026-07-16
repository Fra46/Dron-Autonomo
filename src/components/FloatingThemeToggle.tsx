import { useTheme } from '@/contexts/ThemeContext'

export default function FloatingThemeToggle() {
  const { theme, toggleTheme } = useTheme()

  return (
    <button
      className="floating-theme-toggle"
      onClick={toggleTheme}
      aria-label="Cambiar tema"
      title={`Cambiar a modo ${theme === 'dark' ? 'claro' : 'oscuro'}`}
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  )
}
