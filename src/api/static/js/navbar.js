document.addEventListener('DOMContentLoaded', () => {
    const STORAGE_KEY = 'lust-rentals-theme';
    const toggle = document.querySelector('[data-theme-toggle]');
    const icon = toggle?.querySelector('[data-theme-icon]');
    const label = toggle?.querySelector('[data-theme-label]');

    const setTheme = (theme) => {
        const normalized = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', normalized);
        if (toggle) {
            const isDark = normalized === 'dark';
            toggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
            toggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
            if (icon) {
                icon.textContent = isDark ? '🌙' : '☀️';
            }
            if (label) {
                label.textContent = isDark ? 'Dark' : 'Light';
            }
        }
    };

    const stored = localStorage.getItem(STORAGE_KEY);
    setTheme(stored || 'light');

    toggle?.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        localStorage.setItem(STORAGE_KEY, next);
        setTheme(next);
    });
});
