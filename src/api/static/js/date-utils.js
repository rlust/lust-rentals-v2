/**
 * Date Utilities for Lust Rentals Tax Reporting
 * Provides consistent date parsing, formatting, and manipulation.
 */

class DateUtils {
    /**
     * Parse a date string from various formats into a Date object
     * Handles: ISO 8601, MM/DD/YYYY, YYYY-MM-DD, and timestamp formats
     */
    static parse(dateString) {
        if (!dateString) return null;

        // Already a Date object
        if (dateString instanceof Date) {
            return isNaN(dateString.getTime()) ? null : dateString;
        }

        // Convert to string
        const str = String(dateString).trim();

        // Try parsing as timestamp
        if (/^\d+$/.test(str)) {
            const ts = parseInt(str, 10);
            // Handle seconds vs milliseconds
            const date = new Date(ts > 9999999999 ? ts : ts * 1000);
            return isNaN(date.getTime()) ? null : date;
        }

        // Try ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
            const date = new Date(str);
            return isNaN(date.getTime()) ? null : date;
        }

        // Try MM/DD/YYYY format
        const mdyMatch = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
        if (mdyMatch) {
            const [, month, day, year] = mdyMatch;
            const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
            return isNaN(date.getTime()) ? null : date;
        }

        // Try M/D/YY format
        const shortMatch = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2})$/);
        if (shortMatch) {
            const [, month, day, year] = shortMatch;
            const fullYear = parseInt(year) + (parseInt(year) > 50 ? 1900 : 2000);
            const date = new Date(fullYear, parseInt(month) - 1, parseInt(day));
            return isNaN(date.getTime()) ? null : date;
        }

        // Fallback to native parsing
        const date = new Date(str);
        return isNaN(date.getTime()) ? null : date;
    }

    /**
     * Format a date for display (e.g., "Jan 15, 2025")
     */
    static formatDisplay(date, options = {}) {
        const parsed = this.parse(date);
        if (!parsed) return '';

        const defaultOptions = {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        };

        return parsed.toLocaleDateString('en-US', { ...defaultOptions, ...options });
    }

    /**
     * Format a date for input fields (YYYY-MM-DD)
     */
    static formatForInput(date) {
        const parsed = this.parse(date);
        if (!parsed) return '';

        const year = parsed.getFullYear();
        const month = String(parsed.getMonth() + 1).padStart(2, '0');
        const day = String(parsed.getDate()).padStart(2, '0');

        return `${year}-${month}-${day}`;
    }

    /**
     * Format a date for API communication (ISO 8601)
     */
    static formatForAPI(date) {
        const parsed = this.parse(date);
        if (!parsed) return '';

        return parsed.toISOString();
    }

    /**
     * Format a date as MM/DD/YYYY
     */
    static formatUSDate(date) {
        const parsed = this.parse(date);
        if (!parsed) return '';

        const month = String(parsed.getMonth() + 1).padStart(2, '0');
        const day = String(parsed.getDate()).padStart(2, '0');
        const year = parsed.getFullYear();

        return `${month}/${day}/${year}`;
    }

    /**
     * Format a date with time (e.g., "Jan 15, 2025 3:45 PM")
     */
    static formatDateTime(date) {
        const parsed = this.parse(date);
        if (!parsed) return '';

        return parsed.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }

    /**
     * Get relative time string (e.g., "2 hours ago", "in 3 days")
     */
    static formatRelative(date) {
        const parsed = this.parse(date);
        if (!parsed) return '';

        const now = new Date();
        const diffMs = now - parsed;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);
        const diffWeek = Math.floor(diffDay / 7);
        const diffMonth = Math.floor(diffDay / 30);
        const diffYear = Math.floor(diffDay / 365);

        const isFuture = diffMs < 0;
        const abs = (val) => Math.abs(val);

        if (abs(diffSec) < 60) {
            return isFuture ? 'in a moment' : 'just now';
        }
        if (abs(diffMin) < 60) {
            const mins = abs(diffMin);
            return isFuture ? `in ${mins} minute${mins === 1 ? '' : 's'}` : `${mins} minute${mins === 1 ? '' : 's'} ago`;
        }
        if (abs(diffHour) < 24) {
            const hours = abs(diffHour);
            return isFuture ? `in ${hours} hour${hours === 1 ? '' : 's'}` : `${hours} hour${hours === 1 ? '' : 's'} ago`;
        }
        if (abs(diffDay) < 7) {
            const days = abs(diffDay);
            return isFuture ? `in ${days} day${days === 1 ? '' : 's'}` : `${days} day${days === 1 ? '' : 's'} ago`;
        }
        if (abs(diffWeek) < 4) {
            const weeks = abs(diffWeek);
            return isFuture ? `in ${weeks} week${weeks === 1 ? '' : 's'}` : `${weeks} week${weeks === 1 ? '' : 's'} ago`;
        }
        if (abs(diffMonth) < 12) {
            const months = abs(diffMonth);
            return isFuture ? `in ${months} month${months === 1 ? '' : 's'}` : `${months} month${months === 1 ? '' : 's'} ago`;
        }

        const years = abs(diffYear);
        return isFuture ? `in ${years} year${years === 1 ? '' : 's'}` : `${years} year${years === 1 ? '' : 's'} ago`;
    }

    /**
     * Check if a date is valid
     */
    static isValid(date) {
        return this.parse(date) !== null;
    }

    /**
     * Check if date is today
     */
    static isToday(date) {
        const parsed = this.parse(date);
        if (!parsed) return false;

        const today = new Date();
        return parsed.toDateString() === today.toDateString();
    }

    /**
     * Check if date is in the past
     */
    static isPast(date) {
        const parsed = this.parse(date);
        if (!parsed) return false;

        return parsed < new Date();
    }

    /**
     * Check if date is in the future
     */
    static isFuture(date) {
        const parsed = this.parse(date);
        if (!parsed) return false;

        return parsed > new Date();
    }

    /**
     * Get the start of day
     */
    static startOfDay(date) {
        const parsed = this.parse(date);
        if (!parsed) return null;

        const result = new Date(parsed);
        result.setHours(0, 0, 0, 0);
        return result;
    }

    /**
     * Get the end of day
     */
    static endOfDay(date) {
        const parsed = this.parse(date);
        if (!parsed) return null;

        const result = new Date(parsed);
        result.setHours(23, 59, 59, 999);
        return result;
    }

    /**
     * Add days to a date
     */
    static addDays(date, days) {
        const parsed = this.parse(date);
        if (!parsed) return null;

        const result = new Date(parsed);
        result.setDate(result.getDate() + days);
        return result;
    }

    /**
     * Get difference in days between two dates
     */
    static diffInDays(date1, date2) {
        const d1 = this.parse(date1);
        const d2 = this.parse(date2);

        if (!d1 || !d2) return null;

        const diffMs = d2 - d1;
        return Math.floor(diffMs / (1000 * 60 * 60 * 24));
    }

    /**
     * Get the current year
     */
    static currentYear() {
        return new Date().getFullYear();
    }

    /**
     * Get first day of month
     */
    static startOfMonth(date) {
        const parsed = this.parse(date);
        if (!parsed) return null;

        return new Date(parsed.getFullYear(), parsed.getMonth(), 1);
    }

    /**
     * Get last day of month
     */
    static endOfMonth(date) {
        const parsed = this.parse(date);
        if (!parsed) return null;

        return new Date(parsed.getFullYear(), parsed.getMonth() + 1, 0);
    }

    /**
     * Get first day of year
     */
    static startOfYear(date) {
        const parsed = this.parse(date);
        if (!parsed) return null;

        return new Date(parsed.getFullYear(), 0, 1);
    }

    /**
     * Get last day of year
     */
    static endOfYear(date) {
        const parsed = this.parse(date);
        if (!parsed) return null;

        return new Date(parsed.getFullYear(), 11, 31);
    }
}

// Export for use in modules or make available globally
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DateUtils };
} else {
    window.DateUtils = DateUtils;
}
