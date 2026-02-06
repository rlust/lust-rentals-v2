/**
 * Shared UI Components for Lust Rentals Tax Reporting
 * Provides consistent toast notifications, modals, loading indicators, and utilities.
 */

// =========================================================================
// Toast Notifications
// =========================================================================

class ToastManager {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create container if it doesn't exist
        if (!document.getElementById('toast-container')) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('toast-container');
        }
    }

    show(message, type = 'info', duration = 4000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icon = this.getIcon(type);
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
        `;

        this.container.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('toast-show');
        });

        // Auto-remove
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('toast-show');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        return toast;
    }

    getIcon(type) {
        const icons = {
            success: '&#10004;',
            error: '&#10008;',
            warning: '&#9888;',
            info: '&#8505;'
        };
        return icons[type] || icons.info;
    }

    success(message, duration) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = 6000) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration) {
        return this.show(message, 'info', duration);
    }
}

// =========================================================================
// Modal Dialog
// =========================================================================

class Modal {
    constructor(options = {}) {
        this.title = options.title || '';
        this.content = options.content || '';
        this.onConfirm = options.onConfirm || (() => {});
        this.onCancel = options.onCancel || (() => {});
        this.confirmText = options.confirmText || 'Confirm';
        this.cancelText = options.cancelText || 'Cancel';
        this.showCancel = options.showCancel !== false;
        this.element = null;
    }

    show() {
        this.element = document.createElement('div');
        this.element.className = 'modal-overlay';
        this.element.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-header">
                    <h3 class="modal-title">${this.title}</h3>
                    <button class="modal-close" data-action="close">&times;</button>
                </div>
                <div class="modal-body">${this.content}</div>
                <div class="modal-footer">
                    ${this.showCancel ? `<button class="btn btn-secondary" data-action="cancel">${this.cancelText}</button>` : ''}
                    <button class="btn btn-primary" data-action="confirm">${this.confirmText}</button>
                </div>
            </div>
        `;

        this.element.addEventListener('click', (e) => {
            const action = e.target.dataset.action;
            if (action === 'confirm') {
                this.onConfirm();
                this.close();
            } else if (action === 'cancel' || action === 'close') {
                this.onCancel();
                this.close();
            } else if (e.target === this.element) {
                this.onCancel();
                this.close();
            }
        });

        document.body.appendChild(this.element);

        // Trigger animation
        requestAnimationFrame(() => {
            this.element.classList.add('modal-show');
        });

        return this;
    }

    close() {
        if (this.element) {
            this.element.classList.remove('modal-show');
            setTimeout(() => this.element.remove(), 300);
        }
    }

    static confirm(message, title = 'Confirm') {
        return new Promise((resolve) => {
            new Modal({
                title,
                content: `<p>${message}</p>`,
                confirmText: 'Yes',
                cancelText: 'No',
                onConfirm: () => resolve(true),
                onCancel: () => resolve(false)
            }).show();
        });
    }

    static alert(message, title = 'Alert') {
        return new Promise((resolve) => {
            new Modal({
                title,
                content: `<p>${message}</p>`,
                confirmText: 'OK',
                showCancel: false,
                onConfirm: () => resolve()
            }).show();
        });
    }
}

// =========================================================================
// Loading Indicator
// =========================================================================

class LoadingIndicator {
    constructor() {
        this.overlay = null;
        this.counter = 0;
    }

    show(message = 'Loading...') {
        this.counter++;

        if (!this.overlay) {
            this.overlay = document.createElement('div');
            this.overlay.className = 'loading-overlay';
            this.overlay.innerHTML = `
                <div class="loading-content">
                    <div class="loading-spinner"></div>
                    <p class="loading-message">${message}</p>
                </div>
            `;
            document.body.appendChild(this.overlay);
        } else {
            this.overlay.querySelector('.loading-message').textContent = message;
        }

        requestAnimationFrame(() => {
            this.overlay.classList.add('loading-show');
        });
    }

    hide() {
        this.counter = Math.max(0, this.counter - 1);

        if (this.counter === 0 && this.overlay) {
            this.overlay.classList.remove('loading-show');
            setTimeout(() => {
                if (this.overlay && this.counter === 0) {
                    this.overlay.remove();
                    this.overlay = null;
                }
            }, 300);
        }
    }

    forceHide() {
        this.counter = 0;
        this.hide();
    }

    updateMessage(message) {
        if (this.overlay) {
            this.overlay.querySelector('.loading-message').textContent = message;
        }
    }
}

// =========================================================================
// Utility Functions
// =========================================================================

/**
 * Debounce function - delays execution until after wait ms have elapsed
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function - limits execution to once per wait ms
 */
function throttle(func, wait = 100) {
    let lastTime = 0;
    return function executedFunction(...args) {
        const now = Date.now();
        if (now - lastTime >= wait) {
            lastTime = now;
            func(...args);
        }
    };
}

/**
 * Format currency value
 */
function formatCurrency(value, currency = 'USD') {
    const num = parseFloat(value) || 0;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(num);
}

/**
 * Format number with commas
 */
function formatNumber(value, decimals = 0) {
    const num = parseFloat(value) || 0;
    return num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        const success = document.execCommand('copy');
        document.body.removeChild(textarea);
        return success;
    }
}

/**
 * Save scroll position and restore later
 */
class ScrollPositionManager {
    constructor(element = window) {
        this.element = element;
        this.position = { x: 0, y: 0 };
    }

    save() {
        if (this.element === window) {
            this.position = { x: window.scrollX, y: window.scrollY };
        } else {
            this.position = { x: this.element.scrollLeft, y: this.element.scrollTop };
        }
        return this.position;
    }

    restore() {
        if (this.element === window) {
            window.scrollTo(this.position.x, this.position.y);
        } else {
            this.element.scrollLeft = this.position.x;
            this.element.scrollTop = this.position.y;
        }
    }
}

// =========================================================================
// Form Validation Helpers
// =========================================================================

class FormValidator {
    constructor(rules = {}) {
        this.rules = rules;
        this.errors = {};
    }

    addRule(field, validator, message) {
        if (!this.rules[field]) {
            this.rules[field] = [];
        }
        this.rules[field].push({ validator, message });
        return this;
    }

    validate(data) {
        this.errors = {};
        let isValid = true;

        for (const [field, fieldRules] of Object.entries(this.rules)) {
            const value = data[field];

            for (const rule of fieldRules) {
                if (!rule.validator(value, data)) {
                    if (!this.errors[field]) {
                        this.errors[field] = [];
                    }
                    this.errors[field].push(rule.message);
                    isValid = false;
                }
            }
        }

        return isValid;
    }

    getErrors() {
        return this.errors;
    }

    getFirstError(field) {
        return this.errors[field]?.[0] || null;
    }

    // Common validators
    static required(value) {
        return value !== null && value !== undefined && String(value).trim() !== '';
    }

    static minLength(min) {
        return (value) => String(value || '').length >= min;
    }

    static maxLength(max) {
        return (value) => String(value || '').length <= max;
    }

    static pattern(regex) {
        return (value) => regex.test(String(value || ''));
    }

    static number(value) {
        return !isNaN(parseFloat(value)) && isFinite(value);
    }

    static positive(value) {
        return FormValidator.number(value) && parseFloat(value) > 0;
    }

    static date(value) {
        const d = new Date(value);
        return d instanceof Date && !isNaN(d);
    }
}

// =========================================================================
// Global Instances
// =========================================================================

// Create global instances for immediate use
const toast = new ToastManager();
const loading = new LoadingIndicator();

// Export for use in modules or make available globally
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ToastManager,
        Modal,
        LoadingIndicator,
        FormValidator,
        ScrollPositionManager,
        debounce,
        throttle,
        formatCurrency,
        formatNumber,
        escapeHtml,
        copyToClipboard,
        toast,
        loading
    };
} else {
    // Make available globally
    window.ToastManager = ToastManager;
    window.Modal = Modal;
    window.LoadingIndicator = LoadingIndicator;
    window.FormValidator = FormValidator;
    window.ScrollPositionManager = ScrollPositionManager;
    window.debounce = debounce;
    window.throttle = throttle;
    window.formatCurrency = formatCurrency;
    window.formatNumber = formatNumber;
    window.escapeHtml = escapeHtml;
    window.copyToClipboard = copyToClipboard;
    window.toast = toast;
    window.loading = loading;
}
