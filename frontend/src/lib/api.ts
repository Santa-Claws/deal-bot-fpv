/**
 * Typed API client for the FPV Deal Finder backend.
 *
 * All API calls go through this module so we have:
 * - Type safety (TypeScript interfaces)
 * - Centralized error handling
 * - Easy to update base URL
 */

// Read the API URL from environment variable
// Set PUBLIC_API_URL in docker-compose.yml or .env
const API_BASE = import.meta.env.PUBLIC_API_URL || 'http://localhost:8000';

// ── TypeScript interfaces ──────────────────────────────────

export interface Product {
	id: string;
	store: string;
	title: string;
	url: string;
	image_url: string | null;
	price: number;
	original_price: number | null;
	category: string | null;
	in_stock: boolean;
	is_deal: boolean;
	discount_percent: number | null;
}

export interface SearchResponse {
	hits: Product[];
	total: number;
	query: string;
	parsed_filters: Record<string, unknown>;
	processing_time_ms: number;
}

export interface Deal {
	id: number;
	deal_type: string;
	deal_score: number;
	discount_percent: number | null;
	detected_at: string;
	product: {
		id: number;
		title: string;
		url: string;
		image_url: string | null;
		category: string | null;
		store: string;
		current_price: number;
		original_price: number | null;
	};
}

export interface DealsResponse {
	deals: Deal[];
	page: number;
	per_page: number;
}

export interface PriceDataPoint {
	price: number;
	original_price: number | null;
	in_stock: boolean;
	date: string;
}

export interface PriceHistory {
	product_id: number;
	product_title: string;
	days: number;
	data_points: PriceDataPoint[];
	stats: {
		current: number;
		min: number;
		max: number;
		avg: number;
		all_time_low: boolean;
	};
}

export interface NotificationSettings {
	discord_webhook_url: string | null;
	min_deal_score: number;
	categories: string[] | null;
	max_price: number | null;
	enabled: boolean;
}

// ── API functions ──────────────────────────────────────────

/**
 * Generic fetch wrapper with error handling.
 */
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`, {
		headers: {
			'Content-Type': 'application/json',
			...options?.headers,
		},
		...options,
	});

	if (!response.ok) {
		const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
		throw new Error(error.detail || `HTTP ${response.status}`);
	}

	return response.json();
}

/**
 * Search for products using natural language or filters.
 */
export async function searchProducts(params: {
	q?: string;
	category?: string;
	store?: string;
	min_price?: number;
	max_price?: number;
	in_stock?: boolean;
	deals_only?: boolean;
	sort?: string;
	page?: number;
	per_page?: number;
}): Promise<SearchResponse> {
	const url = new URL(`${API_BASE}/api/products/search`);
	Object.entries(params).forEach(([key, value]) => {
		if (value !== undefined && value !== null && value !== '') {
			url.searchParams.set(key, String(value));
		}
	});

	const response = await fetch(url.toString());
	if (!response.ok) throw new Error(`Search failed: ${response.status}`);
	return response.json();
}

/**
 * Get current deals feed.
 */
export async function getDeals(params: {
	category?: string;
	store?: string;
	min_score?: number;
	deal_type?: string;
	page?: number;
	per_page?: number;
} = {}): Promise<DealsResponse> {
	const url = new URL(`${API_BASE}/api/deals/`);
	Object.entries(params).forEach(([key, value]) => {
		if (value !== undefined) url.searchParams.set(key, String(value));
	});

	const response = await fetch(url.toString());
	if (!response.ok) throw new Error('Failed to fetch deals');
	return response.json();
}

/**
 * Get a single product's details.
 */
export async function getProduct(id: number): Promise<Product> {
	return apiFetch(`/api/products/${id}`);
}

/**
 * Get price history for a product.
 */
export async function getPriceHistory(productId: number, days = 30): Promise<PriceHistory> {
	return apiFetch(`/api/products/${productId}/history?days=${days}`);
}

/**
 * Get notification settings.
 */
export async function getNotificationSettings(): Promise<NotificationSettings> {
	return apiFetch('/api/notifications/settings');
}

/**
 * Update notification settings.
 */
export async function updateNotificationSettings(settings: NotificationSettings): Promise<void> {
	return apiFetch('/api/notifications/settings', {
		method: 'PUT',
		body: JSON.stringify(settings),
	});
}

/**
 * Send a test Discord notification.
 */
export async function sendTestNotification(webhookUrl?: string): Promise<{ status: string }> {
	return apiFetch('/api/notifications/test', {
		method: 'POST',
		body: JSON.stringify({ webhook_url: webhookUrl || null }),
	});
}

/**
 * Health check.
 */
export async function checkHealth(): Promise<{ status: string }> {
	return apiFetch('/health');
}
