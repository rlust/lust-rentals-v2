document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-global-nav]');
    if (!nav) return;

    const toggle = nav.querySelector('.nav-toggle');
    const menu = nav.querySelector('.nav-menu');
    const dropdowns = nav.querySelectorAll('.nav-dropdown');

    const closeDropdowns = () => {
        dropdowns.forEach((dropdown) => {
            dropdown.classList.remove('open');
            const button = dropdown.querySelector('.nav-dropdown-toggle');
            if (button) {
                button.setAttribute('aria-expanded', 'false');
            }
        });
    };

    if (toggle && menu) {
        toggle.addEventListener('click', () => {
            const isOpen = menu.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            if (!isOpen) {
                closeDropdowns();
            }
        });
    }

    dropdowns.forEach((dropdown) => {
        const button = dropdown.querySelector('.nav-dropdown-toggle');
        if (!button) return;

        button.addEventListener('click', (event) => {
            event.preventDefault();
            const isOpen = dropdown.classList.toggle('open');
            button.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });
    });

    document.addEventListener('click', (event) => {
        if (!nav.contains(event.target)) {
            if (menu) {
                menu.classList.remove('is-open');
            }
            closeDropdowns();
        }
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > 900 && menu) {
            menu.classList.remove('is-open');
            toggle?.setAttribute('aria-expanded', 'false');
            closeDropdowns();
        }
    });
});
