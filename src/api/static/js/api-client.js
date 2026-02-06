/**
 * Shared API Client for Lust Rentals Tax Reporting
 * Centralizes all API calls with consistent error handling and caching.
 */

class TaxReportingAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.cache = new Map();
        this.cacheExpiry = 5 * 60 * 1000; // 5 minutes default cache
    }

    /**
     * Make a fetch request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        const mergedOptions = { ...defaultOptions, ...options };
        if (mergedOptions.body && typeof mergedOptions.body === 'object') {
            mergedOptions.body = JSON.stringify(mergedOptions.body);
        }

        try {
            const response = await fetch(url, mergedOptions);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new APIError(
                    errorData.detail || `Request failed with status ${response.status}`,
                    response.status,
                    errorData
                );
            }

            return await response.json();
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            throw new APIError(error.message || 'Network error', 0, null);
        }
    }

    /**
     * GET request with optional caching
     */
    async get(endpoint, { useCache = false, cacheKey = null } = {}) {
        const key = cacheKey || endpoint;

        if (useCache) {
            const cached = this.cache.get(key);
            if (cached && Date.now() - cached.timestamp < this.cacheExpiry) {
                return cached.data;
            }
        }

        const data = await this.request(endpoint);

        if (useCache) {
            this.cache.set(key, { data, timestamp: Date.now() });
        }

        return data;
    }

    /**
     * POST request
     */
    async post(endpoint, body) {
        return this.request(endpoint, { method: 'POST', body });
    }

    /**
     * PUT request
     */
    async put(endpoint, body) {
        return this.request(endpoint, { method: 'PUT', body });
    }

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    /**
     * Clear cache (all or specific key)
     */
    clearCache(key = null) {
        if (key) {
            this.cache.delete(key);
        } else {
            this.cache.clear();
        }
    }

    // =========================================================================
    // Properties API
    // =========================================================================

    async getProperties(useCache = true) {
        const result = await this.get('/review/properties', { useCache });
        return Array.isArray(result) ? result : result.data || result;
    }

    // =========================================================================
    // Categories API
    // =========================================================================

    async getCategories(useCache = true) {
        const result = await this.get('/review/categories', { useCache });
        return Array.isArray(result) ? result : result.data || result;
    }

    // =========================================================================
    // Income API
    // =========================================================================

    async getAllIncome({ page = 1, limit = 0, search = null, property = null } = {}) {
        const params = new URLSearchParams();
        if (page > 1) params.append('page', page);
        if (limit > 0) params.append('limit', limit);
        if (search) params.append('search', search);
        if (property) params.append('property', property);

        const queryString = params.toString();
        const endpoint = `/review/income/all${queryString ? `?${queryString}` : ''}`;
        const result = await this.get(endpoint);

        // Handle both paginated and legacy array response
        return {
            data: result.data || result,
            page: result.page || 1,
            limit: result.limit || (result.data || result).length,
            totalCount: result.total_count || (result.data || result).length,
            hasMore: result.has_more || false
        };
    }

    async getIncomeForReview() {
        const result = await this.get('/review/income');
        return Array.isArray(result) ? result : result.data || result;
    }

    async updateIncome(transactionId, data) {
        return this.put(`/review/income/${transactionId}`, data);
    }

    async updateIncomeOverride(transactionId, data) {
        return this.post(`/review/income/${transactionId}`, data);
    }

    async bulkUpdateIncome(updates) {
        return this.post('/review/bulk/income', { updates });
    }

    async deleteIncome(transactionId) {
        return this.delete(`/review/income/${transactionId}`);
    }

    // =========================================================================
    // Expenses API
    // =========================================================================

    async getAllExpenses({ page = 1, limit = 0, search = null, category = null, property = null } = {}) {
        const params = new URLSearchParams();
        if (page > 1) params.append('page', page);
        if (limit > 0) params.append('limit', limit);
        if (search) params.append('search', search);
        if (category) params.append('category', category);
        if (property) params.append('property', property);

        const queryString = params.toString();
        const endpoint = `/review/expenses/all${queryString ? `?${queryString}` : ''}`;
        const result = await this.get(endpoint);

        // Handle both paginated and legacy array response
        return {
            data: result.data || result,
            page: result.page || 1,
            limit: result.limit || (result.data || result).length,
            totalCount: result.total_count || (result.data || result).length,
            hasMore: result.has_more || false
        };
    }

    async getExpensesForReview() {
        const result = await this.get('/review/expenses');
        return Array.isArray(result) ? result : result.data || result;
    }

    async updateExpense(transactionId, data) {
        return this.put(`/review/expense/${transactionId}`, data);
    }

    async updateExpenseOverride(transactionId, data) {
        return this.post(`/review/expenses/${transactionId}`, data);
    }

    async bulkUpdateExpenses(updates) {
        return this.post('/review/bulk/expenses', { updates });
    }

    async deleteExpense(transactionId) {
        return this.delete(`/review/expense/${transactionId}`);
    }

    // =========================================================================
    // Processing API
    // =========================================================================

    async getLatestTransactionFile() {
        return this.get('/files/latest-transaction');
    }

    async processBank(filePath, year = 2025) {
        return this.post('/process/bank', {
            bank_file_path: filePath,
            year: year
        });
    }

    // =========================================================================
    // Database API
    // =========================================================================

    async getDatabaseStatus() {
        return this.get('/database/status');
    }
}

/**
 * Custom error class for API errors
 */
class APIError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

// Export for use in modules or create global instance
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TaxReportingAPI, APIError };
} else {
    // Create global instance
    window.TaxReportingAPI = TaxReportingAPI;
    window.APIError = APIError;
}
