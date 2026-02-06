/**
 * Global Navigation Component for Lust Rentals Tax Reporting
 * Creates a consistent navigation bar across all pages
 */

class GlobalNavigation {
    constructor(options = {}) {
        this.currentPage = options.currentPage || this.detectCurrentPage();
        this.containerSelector = options.container || 'body';
        this.insertPosition = options.insertPosition || 'prepend';
    }

    detectCurrentPage() {
        const path = window.location.pathname;
        if (path === '/' || path === '/dashboard' || path === '/dashboard-v2') return 'dashboard';
        if (path === '/review-enhanced' || path === '/review-v3') return 'review';
        if (path === '/review') return 'review-classic';
        if (path === '/transactions') return 'transactions';
        if (path === '/properties-ui') return 'properties';
        return '';
    }

    getNavHTML() {
        return `
        <nav class="global-nav" id="globalNav">
            <div class="nav-header">
                <a href="/dashboard-v2" class="nav-brand">
                    <span class="nav-brand-icon">&#127969;</span>
                    <span>
                        <span class="nav-brand-text">Lust Rentals</span>
                        <span class="nav-brand-sub">Tax Reporting</span>
                    </span>
                </a>
                <button class="nav-toggle" onclick="GlobalNavigation.toggleMenu()" aria-label="Toggle navigation">
                    &#9776;
                </button>
            </div>
            <div class="nav-menu" id="navMenu">
                <div class="nav-group">
                    <span class="nav-group-label">Main</span>
                    <a href="/dashboard-v2" class="nav-link ${this.currentPage === 'dashboard' ? 'active' : ''}">
                        <span class="nav-link-icon">&#128200;</span>
                        Dashboard
                    </a>
                </div>

                <div class="nav-divider"></div>

                <div class="nav-group">
                    <span class="nav-group-label">Review</span>
                    <a href="/review-enhanced" class="nav-link ${this.currentPage === 'review' ? 'active' : ''}">
                        <span class="nav-link-icon">&#10024;</span>
                        Review Transactions
                    </a>
                    <a href="/review" class="nav-link ${this.currentPage === 'review-classic' ? 'active' : ''}">
                        <span class="nav-link-icon">&#128269;</span>
                        Classic Review
                    </a>
                </div>

                <div class="nav-divider"></div>

                <div class="nav-group">
                    <span class="nav-group-label">Manage</span>
                    <a href="/transactions" class="nav-link ${this.currentPage === 'transactions' ? 'active' : ''}">
                        <span class="nav-link-icon">&#128188;</span>
                        Transactions
                    </a>
                    <a href="/properties-ui" class="nav-link ${this.currentPage === 'properties' ? 'active' : ''}">
                        <span class="nav-link-icon">&#127970;</span>
                        Properties
                    </a>
                </div>

                <div class="nav-divider"></div>

                <div class="nav-group">
                    <span class="nav-group-label">Tools</span>
                    <a href="/docs" class="nav-link" target="_blank">
                        <span class="nav-link-icon">&#128218;</span>
                        API Docs
                    </a>
                </div>
            </div>
        </nav>
        `;
    }

    render() {
        const container = document.querySelector(this.containerSelector);
        if (!container) {
            console.error('Navigation container not found:', this.containerSelector);
            return;
        }

        const navHTML = this.getNavHTML();

        if (this.insertPosition === 'prepend') {
            container.insertAdjacentHTML('afterbegin', navHTML);
        } else if (this.insertPosition === 'append') {
            container.insertAdjacentHTML('beforeend', navHTML);
        } else {
            const target = document.querySelector(this.insertPosition);
            if (target) {
                target.insertAdjacentHTML('beforebegin', navHTML);
            }
        }
    }

    static toggleMenu() {
        const menu = document.getElementById('navMenu');
        if (menu) {
            menu.classList.toggle('open');
        }
    }
}

// Auto-initialize when DOM is ready if data attribute is present
document.addEventListener('DOMContentLoaded', () => {
    const autoInit = document.querySelector('[data-nav-auto-init]');
    if (autoInit) {
        const nav = new GlobalNavigation({
            container: autoInit.dataset.navContainer || '.container',
            currentPage: autoInit.dataset.navCurrentPage
        });
        nav.render();
    }
});

// Export for manual initialization
window.GlobalNavigation = GlobalNavigation;
