<!--
  Home / Search page

  PyroDrone-inspired layout:
  - Category browse bar (horizontal pills)
  - Per-category subcategory filters (stator size, amperage, etc.)
  - Infinite scroll product grid
  - Sidebar filters
-->
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import ProductCard from '$lib/components/ProductCard.svelte';
	import { searchProducts, type Product, type SearchResponse } from '$lib/api';

	let query = '';
	let allHits: Product[] = [];
	let total = 0;
	let loading = false;
	let loadingMore = false;
	let error = '';
	let currentPage = 1;
	let hasMore = false;
	let processingTimeMs = 0;
	let parsedFilters: Record<string, unknown> = {};

	const PER_PAGE = 24;

	// Filter state
	let selectedCategory = '';
	let selectedStore = '';
	let maxPrice = '';
	let inStockOnly = false;
	let dealsOnly = false;
	let sort = 'price:asc';

	// Subcategory filter state
	let selectedStator = '';
	let selectedKV = '';
	let selectedAmperage = '';
	let selectedFrameSize = '';
	let selectedPropSize = '';

	// Infinite scroll sentinel
	let sentinel: HTMLDivElement;
	let observer: IntersectionObserver;

	// Category browse bar config — mirrors PyroDrone's category nav
	const categories = [
		{ value: '', label: 'All', icon: '🛒' },
		{ value: 'motors', label: 'Motors', icon: '🔧' },
		{ value: 'escs', label: 'ESCs', icon: '⚡' },
		{ value: 'flight_controllers', label: 'Flight Controllers', icon: '🧠' },
		{ value: 'stacks', label: 'Stacks', icon: '📦' },
		{ value: 'frames', label: 'Frames', icon: '🏗️' },
		{ value: 'vtx', label: 'VTX', icon: '📡' },
		{ value: 'cameras', label: 'Cameras', icon: '📷' },
		{ value: 'props', label: 'Props', icon: '🌀' },
		{ value: 'batteries', label: 'Batteries', icon: '🔋' },
		{ value: 'antennas', label: 'Antennas', icon: '📶' },
		{ value: 'accessories', label: 'Accessories', icon: '🔩' },
	];

	// Subcategory options per category (PyroDrone-style sub-filters)
	const statorSizes = ['1202', '1404', '1507', '2004', '2205', '2207', '2207.5', '2306', '2306.5', '2402', '2804'];
	const kvRanges = [
		{ label: 'Any KV', value: '' },
		{ label: '< 1000 KV', value: 'low' },
		{ label: '1000–1800 KV', value: 'mid' },
		{ label: '1800–2500 KV', value: 'high' },
		{ label: '2500+ KV', value: 'ultra' },
	];
	const amperages = ['20A', '30A', '45A', '55A', '60A', '80A', '100A'];
	const frameSizes = ['2"', '2.5"', '3"', '3.5"', '4"', '5"', '6"', '7"', '10"'];
	const propSizes = ['1.6"', '2"', '2.5"', '3"', '3.5"', '4"', '4.5"', '5"', '5.1"', '6"'];

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

	// Build the effective search query including subcategory filters as keywords
	function buildEffectiveQuery(): string {
		const parts: string[] = [];
		if (query) parts.push(query);
		if (selectedStator) parts.push(selectedStator);
		if (selectedAmperage) parts.push(selectedAmperage.replace('A', 'A'));
		if (selectedFrameSize) parts.push(selectedFrameSize);
		if (selectedPropSize) parts.push(selectedPropSize);
		if (selectedKV === 'low') parts.push('800kv 900kv');
		else if (selectedKV === 'mid') parts.push('1400kv 1500kv 1600kv 1700kv 1800kv');
		else if (selectedKV === 'high') parts.push('1900kv 2000kv 2100kv 2200kv 2300kv 2400kv');
		else if (selectedKV === 'ultra') parts.push('2500kv 2600kv 2700kv 3000kv');
		return parts.join(' ');
	}

	async function doSearch(page = 1) {
		if (page === 1) {
			loading = true;
			allHits = [];
		} else {
			loadingMore = true;
		}
		error = '';

		try {
			const effectiveQ = buildEffectiveQuery();
			const resp = await searchProducts({
				q: effectiveQ || undefined,
				category: selectedCategory || undefined,
				store: selectedStore || undefined,
				max_price: maxPrice ? parseFloat(maxPrice) : undefined,
				in_stock: inStockOnly || undefined,
				deals_only: dealsOnly || undefined,
				sort,
				page,
				per_page: PER_PAGE,
			});

			if (page === 1) {
				allHits = resp.hits;
			} else {
				allHits = [...allHits, ...resp.hits];
			}

			total = resp.total;
			processingTimeMs = resp.processing_time_ms;
			parsedFilters = resp.parsed_filters;
			currentPage = page;
			hasMore = allHits.length < resp.total && resp.hits.length === PER_PAGE;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Search failed';
		} finally {
			loading = false;
			loadingMore = false;
		}
	}

	function resetAndSearch() {
		currentPage = 1;
		doSearch(1);
	}

	function selectCategory(cat: string) {
		selectedCategory = cat;
		selectedStator = '';
		selectedKV = '';
		selectedAmperage = '';
		selectedFrameSize = '';
		selectedPropSize = '';
		resetAndSearch();
	}

	function loadMore() {
		if (!loadingMore && hasMore) {
			doSearch(currentPage + 1);
		}
	}

	// Set up IntersectionObserver for infinite scroll
	function setupObserver() {
		if (observer) observer.disconnect();
		observer = new IntersectionObserver(
			(entries) => {
				if (entries[0].isIntersecting && hasMore && !loadingMore && !loading) {
					loadMore();
				}
			},
			{ rootMargin: '200px' }
		);
		if (sentinel) observer.observe(sentinel);
	}

	onMount(() => {
		doSearch(1);
		setupObserver();
	});

	onDestroy(() => {
		if (observer) observer.disconnect();
	});

	// Re-observe sentinel whenever hits change
	$: if (sentinel && observer) {
		observer.observe(sentinel);
	}
</script>

<svelte:head>
	<title>FPV Deal Finder - Search</title>
</svelte:head>

<div class="space-y-4">
	<!-- Search bar -->
	<div class="text-center space-y-3 py-4">
		<h1 class="text-2xl font-bold text-gray-100">Find FPV Deals</h1>
		<p class="text-gray-500 text-sm">
			AI-powered search across {stores.length - 1} stores · Updated every 6 hours
		</p>
		<div class="max-w-2xl mx-auto">
			<SearchBar
				bind:value={query}
				{loading}
				on:search={() => resetAndSearch()}
			/>
			<p class="text-xs text-gray-600 mt-2">
				Try: "2207 motor under $30" · "best ESC 4in1 deals" · "5 inch freestyle frame"
			</p>
		</div>
	</div>

	<!-- Category browse bar (PyroDrone style) -->
	<div class="overflow-x-auto pb-1 -mx-1 px-1">
		<div class="flex gap-2 min-w-max">
			{#each categories as cat}
				<button
					on:click={() => selectCategory(cat.value)}
					class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all
					       {selectedCategory === cat.value
					         ? 'bg-electric-blue text-dark-900'
					         : 'bg-dark-700 text-gray-400 hover:bg-dark-600 hover:text-gray-200'}"
				>
					<span>{cat.icon}</span>
					<span>{cat.label}</span>
				</button>
			{/each}
		</div>
	</div>

	<!-- Subcategory filters (shown when a category is active) -->
	{#if selectedCategory === 'motors'}
		<div class="card p-4 space-y-3">
			<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Motor Filters</h3>
			<div class="space-y-3">
				<!-- Stator size -->
				<div>
					<p class="text-xs text-gray-500 mb-2">Stator Size</p>
					<div class="flex flex-wrap gap-2">
						<button
							on:click={() => { selectedStator = ''; resetAndSearch(); }}
							class="px-2.5 py-1 rounded text-xs font-medium transition-all
							       {selectedStator === '' ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
						>Any</button>
						{#each statorSizes as size}
							<button
								on:click={() => { selectedStator = size; resetAndSearch(); }}
								class="px-2.5 py-1 rounded text-xs font-medium transition-all
								       {selectedStator === size ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
							>{size}</button>
						{/each}
					</div>
				</div>
				<!-- KV range -->
				<div>
					<p class="text-xs text-gray-500 mb-2">KV Range</p>
					<div class="flex flex-wrap gap-2">
						{#each kvRanges as kv}
							<button
								on:click={() => { selectedKV = kv.value; resetAndSearch(); }}
								class="px-2.5 py-1 rounded text-xs font-medium transition-all
								       {selectedKV === kv.value ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
							>{kv.label}</button>
						{/each}
					</div>
				</div>
			</div>
		</div>

	{:else if selectedCategory === 'escs'}
		<div class="card p-4 space-y-3">
			<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">ESC Filters</h3>
			<div>
				<p class="text-xs text-gray-500 mb-2">Amperage Rating</p>
				<div class="flex flex-wrap gap-2">
					<button
						on:click={() => { selectedAmperage = ''; resetAndSearch(); }}
						class="px-2.5 py-1 rounded text-xs font-medium transition-all
						       {selectedAmperage === '' ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
					>Any</button>
					{#each amperages as amp}
						<button
							on:click={() => { selectedAmperage = amp; resetAndSearch(); }}
							class="px-2.5 py-1 rounded text-xs font-medium transition-all
							       {selectedAmperage === amp ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
						>{amp}</button>
					{/each}
				</div>
			</div>
		</div>

	{:else if selectedCategory === 'frames'}
		<div class="card p-4 space-y-3">
			<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Frame Filters</h3>
			<div>
				<p class="text-xs text-gray-500 mb-2">Size</p>
				<div class="flex flex-wrap gap-2">
					<button
						on:click={() => { selectedFrameSize = ''; resetAndSearch(); }}
						class="px-2.5 py-1 rounded text-xs font-medium transition-all
						       {selectedFrameSize === '' ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
					>Any</button>
					{#each frameSizes as size}
						<button
							on:click={() => { selectedFrameSize = size; resetAndSearch(); }}
							class="px-2.5 py-1 rounded text-xs font-medium transition-all
							       {selectedFrameSize === size ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
						>{size}</button>
					{/each}
				</div>
			</div>
		</div>

	{:else if selectedCategory === 'props'}
		<div class="card p-4 space-y-3">
			<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Prop Filters</h3>
			<div>
				<p class="text-xs text-gray-500 mb-2">Size</p>
				<div class="flex flex-wrap gap-2">
					<button
						on:click={() => { selectedPropSize = ''; resetAndSearch(); }}
						class="px-2.5 py-1 rounded text-xs font-medium transition-all
						       {selectedPropSize === '' ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
					>Any</button>
					{#each propSizes as size}
						<button
							on:click={() => { selectedPropSize = size; resetAndSearch(); }}
							class="px-2.5 py-1 rounded text-xs font-medium transition-all
							       {selectedPropSize === size ? 'bg-electric-blue text-dark-900' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
						>{size}</button>
					{/each}
				</div>
			</div>
		</div>
	{/if}

	<div class="flex gap-6">
		<!-- Sidebar filters -->
		<aside class="w-52 flex-shrink-0 hidden md:block">
			<div class="card p-4 space-y-4 sticky top-20">
				<h2 class="text-sm font-semibold text-gray-300">Filters</h2>

				<!-- Store -->
				<div class="filter-section">
					<label class="text-xs text-gray-500 block mb-2">Store</label>
					<select
						bind:value={selectedStore}
						on:change={resetAndSearch}
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
							on:change={resetAndSearch}
							placeholder="Any"
							min="0"
							class="w-full bg-dark-700 text-gray-300 text-sm border border-dark-500
							       rounded-lg pl-7 pr-3 py-2 focus:outline-none focus:border-electric-blue"
						/>
					</div>
				</div>

				<!-- Price range quick picks -->
				<div class="filter-section">
					<p class="text-xs text-gray-500 mb-2">Quick Price</p>
					<div class="grid grid-cols-2 gap-1">
						{#each [['Under $25', '25'], ['Under $50', '50'], ['Under $100', '100'], ['Under $200', '200']] as [label, val]}
							<button
								on:click={() => { maxPrice = maxPrice === val ? '' : val; resetAndSearch(); }}
								class="text-xs px-2 py-1.5 rounded transition-all
								       {maxPrice === val ? 'bg-electric-blue text-dark-900 font-medium' : 'bg-dark-700 text-gray-400 hover:bg-dark-600'}"
							>{label}</button>
						{/each}
					</div>
				</div>

				<!-- Checkboxes -->
				<div class="space-y-2">
					<label class="flex items-center gap-2 cursor-pointer">
						<input
							type="checkbox"
							bind:checked={inStockOnly}
							on:change={resetAndSearch}
							class="rounded border-dark-500 bg-dark-700 text-electric-blue
							       focus:ring-electric-blue focus:ring-opacity-30"
						/>
						<span class="text-sm text-gray-400">In stock only</span>
					</label>
					<label class="flex items-center gap-2 cursor-pointer">
						<input
							type="checkbox"
							bind:checked={dealsOnly}
							on:change={resetAndSearch}
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
						on:change={resetAndSearch}
						class="w-full bg-dark-700 text-gray-300 text-sm border border-dark-500
						       rounded-lg px-3 py-2 focus:outline-none focus:border-electric-blue"
					>
						{#each sortOptions as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
				</div>

				<!-- Clear filters -->
				{#if selectedCategory || selectedStore || maxPrice || inStockOnly || dealsOnly || selectedStator || selectedKV || selectedAmperage || selectedFrameSize || selectedPropSize}
					<button
						on:click={() => {
							selectedCategory = '';
							selectedStore = '';
							maxPrice = '';
							inStockOnly = false;
							dealsOnly = false;
							selectedStator = '';
							selectedKV = '';
							selectedAmperage = '';
							selectedFrameSize = '';
							selectedPropSize = '';
							resetAndSearch();
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
			<div class="flex items-center justify-between mb-4 min-h-[24px]">
				<p class="text-sm text-gray-500">
					{#if loading && allHits.length === 0}
						<span class="text-gray-600">Searching…</span>
					{:else if total > 0}
						Showing <span class="text-gray-300">{allHits.length}</span> of
						<span class="text-gray-300">{total}</span>
						{selectedCategory ? selectedCategory.replace('_', ' ') : 'products'}
						{#if query}
							for <span class="text-electric-blue">"{query}"</span>
						{/if}
						{#if processingTimeMs}
							<span class="text-gray-600"> · {processingTimeMs}ms</span>
						{/if}
					{:else if !loading}
						<span class="text-gray-600">No results</span>
					{/if}
				</p>

				{#if Object.keys(parsedFilters).length > 0 && query}
					<div class="text-xs text-gray-600 flex items-center gap-1">
						<svg class="w-3 h-3 text-electric-blue" fill="currentColor" viewBox="0 0 24 24">
							<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
						</svg>
						<span class="text-electric-blue">AI</span> parsed
					</div>
				{/if}
			</div>

			<!-- Error state -->
			{#if error}
				<div class="card p-6 text-center">
					<p class="text-red-400">{error}</p>
					<button on:click={() => doSearch(1)} class="btn-ghost mt-3 text-sm">Try Again</button>
				</div>

			<!-- Loading skeleton (first load only) -->
			{:else if loading && allHits.length === 0}
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
			{:else if !loading && allHits.length === 0}
				<div class="card p-12 text-center">
					<div class="text-4xl mb-4">🔍</div>
					<h3 class="text-lg font-medium text-gray-300 mb-2">No products found</h3>
					<p class="text-gray-500 text-sm">Try a different search or clear your filters.</p>
				</div>

			<!-- Product grid -->
			{:else}
				<div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
					{#each allHits as product (product.id)}
						<ProductCard {product} />
					{/each}

					<!-- Loading more skeletons -->
					{#if loadingMore}
						{#each Array(4) as _}
							<div class="card p-4 animate-pulse">
								<div class="aspect-square bg-dark-700 rounded-lg mb-3"></div>
								<div class="h-4 bg-dark-700 rounded mb-2"></div>
								<div class="h-3 bg-dark-700 rounded w-3/4 mb-2"></div>
								<div class="h-5 bg-dark-700 rounded w-1/2"></div>
							</div>
						{/each}
					{/if}
				</div>

				<!-- Infinite scroll sentinel + manual load more -->
				<div bind:this={sentinel} class="mt-8 flex flex-col items-center gap-3 pb-8">
					{#if hasMore && !loadingMore}
						<button
							on:click={loadMore}
							class="btn-ghost text-sm px-8"
						>
							Load more · {total - allHits.length} remaining
						</button>
					{:else if !hasMore && allHits.length > PER_PAGE}
						<p class="text-xs text-gray-600">All {total} products loaded</p>
					{/if}
				</div>
			{/if}
		</div>
	</div>
</div>
