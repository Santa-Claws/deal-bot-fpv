<!--
  Product detail page

  Shows full product info with:
  - Price history chart
  - Specs
  - Store link
  - Similar products
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import PriceChart from '$lib/components/PriceChart.svelte';
	import { getProduct, getPriceHistory, type PriceHistory } from '$lib/api';

	$: productId = parseInt($page.params.id);

	let product: Record<string, unknown> | null = null;
	let priceHistory: PriceHistory | null = null;
	let loading = true;
	let error = '';
	let historyDays = 30;

	async function loadData() {
		loading = true;
		error = '';
		try {
			[product, priceHistory] = await Promise.all([
				getProduct(productId),
				getPriceHistory(productId, historyDays),
			]);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load product';
		} finally {
			loading = false;
		}
	}

	onMount(loadData);
</script>

<svelte:head>
	<title>{product ? String(product.title) : 'Product'} - FPV Deal Finder</title>
</svelte:head>

{#if loading}
	<div class="animate-pulse space-y-6">
		<div class="h-8 bg-dark-700 rounded w-1/2"></div>
		<div class="grid grid-cols-2 gap-6">
			<div class="aspect-square bg-dark-700 rounded-xl"></div>
			<div class="space-y-4">
				<div class="h-6 bg-dark-700 rounded"></div>
				<div class="h-4 bg-dark-700 rounded w-3/4"></div>
				<div class="h-10 bg-dark-700 rounded w-1/3"></div>
			</div>
		</div>
	</div>

{:else if error}
	<div class="card p-8 text-center">
		<p class="text-red-400">{error}</p>
		<a href="/" class="btn-ghost mt-3 inline-block">← Back to Search</a>
	</div>

{:else if product}
	<div class="space-y-6">
		<!-- Breadcrumb -->
		<nav class="text-sm text-gray-500">
			<a href="/" class="hover:text-electric-blue transition-colors">Search</a>
			<span class="mx-2">→</span>
			{#if product.category}
				<span class="capitalize">{String(product.category).replace('_', ' ')}</span>
				<span class="mx-2">→</span>
			{/if}
			<span class="text-gray-300 truncate">{String(product.title)}</span>
		</nav>

		<div class="grid md:grid-cols-2 gap-6">
			<!-- Product image -->
			<div class="card p-6 flex items-center justify-center">
				{#if product.image_url}
					<img
						src={String(product.image_url)}
						alt={String(product.title)}
						class="max-w-full max-h-80 object-contain"
					/>
				{:else}
					<div class="text-8xl">🔧</div>
				{/if}
			</div>

			<!-- Product details -->
			<div class="space-y-4">
				<div>
					<span class="text-sm text-gray-500">{String(product.store)}</span>
					<h1 class="text-xl font-bold text-gray-100 mt-1">{String(product.title)}</h1>
				</div>

				<!-- Price -->
				<div class="flex items-baseline gap-3">
					<span class="text-3xl font-bold text-electric-blue">
						${product.current_price ? Number(product.current_price).toFixed(2) : 'N/A'}
					</span>
					{#if product.original_price && Number(product.original_price) > Number(product.current_price)}
						<span class="text-lg text-gray-500 line-through">
							${Number(product.original_price).toFixed(2)}
						</span>
						<span class="text-electric-green font-bold">
							{Math.round(((Number(product.original_price) - Number(product.current_price)) / Number(product.original_price)) * 100)}% off
						</span>
					{/if}
				</div>

				<!-- Stock status -->
				<div class="flex items-center gap-2">
					<div class="w-2 h-2 rounded-full {product.in_stock ? 'bg-electric-green' : 'bg-red-500'}"></div>
					<span class="text-sm {product.in_stock ? 'text-electric-green' : 'text-red-400'}">
						{product.in_stock ? 'In Stock' : 'Out of Stock'}
					</span>
				</div>

				<!-- Specs -->
				{#if product.specs && Object.keys(product.specs).length > 0}
					<div class="card p-4">
						<h3 class="text-sm font-semibold text-gray-400 mb-3">Specifications</h3>
						<div class="grid grid-cols-2 gap-2">
							{#each Object.entries(product.specs) as [key, value]}
								<div>
									<span class="text-xs text-gray-600 capitalize">{key.replace('_', ' ')}</span>
									<div class="text-sm text-gray-300 font-mono">{value}</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Buy button -->
				<a
					href={String(product.url)}
					target="_blank"
					rel="noopener noreferrer"
					class="btn-primary inline-flex items-center gap-2 w-full justify-center"
				>
					View on {String(product.store)}
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
					</svg>
				</a>
			</div>
		</div>

		<!-- Price history chart -->
		{#if priceHistory && priceHistory.data_points.length > 0}
			<div class="card p-6">
				<div class="flex items-center justify-between mb-4">
					<h2 class="text-lg font-semibold text-gray-200">Price History</h2>
					<div class="flex gap-2">
						{#each [7, 30, 90] as days}
							<button
								on:click={() => { historyDays = days; loadData(); }}
								class="text-xs px-2 py-1 rounded transition-colors
								       {historyDays === days
									       ? 'bg-electric-blue text-dark-900 font-bold'
									       : 'text-gray-500 hover:text-gray-300'}"
							>
								{days}d
							</button>
						{/each}
					</div>
				</div>
				<PriceChart history={priceHistory} />
			</div>
		{/if}
	</div>
{/if}
