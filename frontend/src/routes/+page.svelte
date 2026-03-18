<!--
  Home / Search page

  This is the main entry point - a PCPartPicker-style search interface
  with an AI-powered search bar and filtered product grid.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import ProductCard from '$lib/components/ProductCard.svelte';
	import { searchProducts, type Product, type SearchResponse } from '$lib/api';

	let query = '';
	let results: SearchResponse | null = null;
	let loading = false;
	let error = '';

	// Filter state
	let selectedCategory = '';
	let selectedStore = '';
	let maxPrice = '';
	let inStockOnly = false;
	let dealsOnly = false;
	let sort = 'price:asc';

	// Available filter options
	const categories = [
		{ value: '', label: 'All Categories' },
		{ value: 'motors', label: '🔧 Motors' },
		{ value: 'escs', label: '⚡ ESCs' },
		{ value: 'flight_controllers', label: '🧠 Flight Controllers' },
		{ value: 'frames', label: '🏗️ Frames' },
		{ value: 'stacks', label: '📦 Stacks' },
		{ value: 'vtx', label: '📡 VTX' },
		{ value: 'cameras', label: '📷 Cameras' },
		{ value: 'props', label: '🌀 Props' },
		{ value: 'batteries', label: '🔋 Batteries' },
	];

	const stores = [
		{ value: '', label: 'All Stores' },
		{ value: 'NewBeeDrone', label: 'NewBeeDrone' },
		{ value: 'PyroDrone', label: 'PyroDrone' },
		{ value: 'RaceDayQuads', label: 'RaceDayQuads' },
		{ value: 'GetFPV', label: 'GetFPV' },
		{ value: 'GEPRC', label: 'GEPRC' },
		{ value: 'HDZero', label: 'HDZero' },
	];

	const sortOptions = [
		{ value: 'price:asc', label: 'Price: Low to High' },
		{ value: 'price:desc', label: 'Price: High to Low' },
	];

	async function doSearch(searchQuery = query) {
		loading = true;
		error = '';
		query = searchQuery;

		try {
			results = await searchProducts({
				q: query || undefined,
				category: selectedCategory || undefined,
				store: selectedStore || undefined,
				max_price: maxPrice ? parseFloat(maxPrice) : undefined,
				in_stock: inStockOnly || undefined,
				deals_only: dealsOnly || undefined,
				sort,
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Search failed';
		} finally {
			loading = false;
		}
	}

	// Trigger search when filters change
	function applyFilters() {
		doSearch();
	}

	// Load initial results on page load
	onMount(() => {
		doSearch('');
	});
</script>

<svelte:head>
	<title>FPV Deal Finder - Search</title>
</svelte:head>

<div class="space-y-6">
	<!-- Hero search bar -->
	<div class="text-center space-y-3 py-4">
		<h1 class="text-2xl font-bold text-gray-100">
			Find FPV Deals
		</h1>
		<p class="text-gray-500 text-sm">
			AI-powered search across {stores.length - 1} stores · Updated every 6 hours
		</p>
		<div class="max-w-2xl mx-auto">
			<SearchBar
				bind:value={query}
				{loading}
				on:search={(e) => doSearch(e.detail.query)}
			/>
		</div>
	</div>

	<div class="flex gap-6">
		<!-- Sidebar filters -->
		<aside class="w-56 flex-shrink-0 hidden md:block">
			<div class="card p-4 space-y-4 sticky top-20">
				<h2 class="text-sm font-semibold text-gray-300">Filters</h2>

				<!-- Category -->
				<div class="filter-section">
					<label class="text-xs text-gray-500 block mb-2">Category</label>
					<select
						bind:value={selectedCategory}
						on:change={applyFilters}
						class="w-full bg-dark-700 text-gray-300 text-sm border border-dark-500
						       rounded-lg px-3 py-2 focus:outline-none focus:border-electric-blue"
					>
						{#each categories as cat}
							<option value={cat.value}>{cat.label}</option>
						{/each}
					</select>
				</div>

				<!-- Store -->
				<div class="filter-section">
					<label class="text-xs text-gray-500 block mb-2">Store</label>
					<select
						bind:value={selectedStore}
						on:change={applyFilters}
						class="w-full bg-dark-700 text-gray-300 text-sm border border-dark-500
						       rounded-lg px-3 py-2 focus:outline-none focus:border-electric-blue"
					>
						{#each stores as store}
							<option value={store.value}>{store.label}</option>
						{/each}
					</select>
				</div>

				<!-- Max price -->
				<div class="filter-section">
					<label class="text-xs text-gray-500 block mb-2">Max Price</label>
					<div class="relative">
						<span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
						<input
							type="number"
							bind:value={maxPrice}
							on:change={applyFilters}
							placeholder="Any"
							min="0"
							class="w-full bg-dark-700 text-gray-300 text-sm border border-dark-500
							       rounded-lg pl-7 pr-3 py-2 focus:outline-none focus:border-electric-blue"
						/>
					</div>
				</div>

				<!-- Checkboxes -->
				<div class="space-y-2">
					<label class="flex items-center gap-2 cursor-pointer">
						<input
							type="checkbox"
							bind:checked={inStockOnly}
							on:change={applyFilters}
							class="rounded border-dark-500 bg-dark-700 text-electric-blue
							       focus:ring-electric-blue focus:ring-opacity-30"
						/>
						<span class="text-sm text-gray-400">In stock only</span>
					</label>
					<label class="flex items-center gap-2 cursor-pointer">
						<input
							type="checkbox"
							bind:checked={dealsOnly}
							on:change={applyFilters}
							class="rounded border-dark-500 bg-dark-700 text-electric-blue
							       focus:ring-electric-blue focus:ring-opacity-30"
						/>
						<span class="text-sm text-gray-400">Deals only</span>
					</label>
				</div>

				<!-- Sort -->
				<div>
					<label class="text-xs text-gray-500 block mb-2">Sort By</label>
					<select
						bind:value={sort}
						on:change={applyFilters}
						class="w-full bg-dark-700 text-gray-300 text-sm border border-dark-500
						       rounded-lg px-3 py-2 focus:outline-none focus:border-electric-blue"
					>
						{#each sortOptions as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
				</div>

				<!-- Clear filters -->
				{#if selectedCategory || selectedStore || maxPrice || inStockOnly || dealsOnly}
					<button
						on:click={() => {
							selectedCategory = '';
							selectedStore = '';
							maxPrice = '';
							inStockOnly = false;
							dealsOnly = false;
							applyFilters();
						}}
						class="w-full text-xs text-gray-500 hover:text-electric-blue transition-colors py-1"
					>
						Clear all filters
					</button>
				{/if}
			</div>
		</aside>

		<!-- Results area -->
		<div class="flex-1 min-w-0">
			<!-- Results header -->
			{#if results}
				<div class="flex items-center justify-between mb-4">
					<p class="text-sm text-gray-500">
						{#if query}
							<span class="text-gray-300">{results.total}</span> results for
							<span class="text-electric-blue">"{query}"</span>
						{:else}
							<span class="text-gray-300">{results.total}</span> products
						{/if}
						{#if results.processing_time_ms}
							<span class="text-gray-600"> · {results.processing_time_ms}ms</span>
						{/if}
					</p>

					<!-- AI parsed filters indicator -->
					{#if Object.keys(results.parsed_filters).length > 0 && query}
						<div class="text-xs text-gray-600 flex items-center gap-1">
							<span class="text-electric-blue">AI</span>
							<span>parsed your query</span>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Error state -->
			{#if error}
				<div class="card p-6 text-center">
					<p class="text-red-400">{error}</p>
					<button on:click={() => doSearch()} class="btn-ghost mt-3 text-sm">
						Try Again
					</button>
				</div>

			<!-- Loading skeleton -->
			{:else if loading && !results}
				<div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
					{#each Array(8) as _}
						<div class="card p-4 animate-pulse">
							<div class="aspect-square bg-dark-700 rounded-lg mb-3"></div>
							<div class="h-4 bg-dark-700 rounded mb-2"></div>
							<div class="h-3 bg-dark-700 rounded w-3/4 mb-2"></div>
							<div class="h-5 bg-dark-700 rounded w-1/2"></div>
						</div>
					{/each}
				</div>

			<!-- Empty state -->
			{:else if results && results.hits.length === 0}
				<div class="card p-12 text-center">
					<div class="text-4xl mb-4">🔍</div>
					<h3 class="text-lg font-medium text-gray-300 mb-2">No products found</h3>
					<p class="text-gray-500 text-sm mb-4">
						Try a different search or clear your filters.
					</p>
					{#if !results.total}
						<p class="text-xs text-gray-600">
							The database might be empty. Try running a scrape first:
							<code class="bg-dark-700 px-1 rounded text-electric-blue">
								docker exec fpv-celery-worker celery -A app.scrapers.runner call scrape_store --args '["NewBeeDrone"]'
							</code>
						</p>
					{/if}
				</div>

			<!-- Product grid -->
			{:else if results}
				<div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
					{#each results.hits as product (product.id)}
						<ProductCard {product} />
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>
