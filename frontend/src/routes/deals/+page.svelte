<!--
  Deals feed page

  Shows all detected deals sorted by AI score.
  Best deals (score 8+) appear first.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import DealBadge from '$lib/components/DealBadge.svelte';
	import { getDeals, type Deal } from '$lib/api';

	let deals: Deal[] = [];
	let loading = true;
	let error = '';
	let selectedCategory = '';
	let minScore = 4;

	const dealTypeLabels: Record<string, string> = {
		sale: '🏷️ On Sale',
		price_drop: '📉 Price Drop',
		historic_low: '🔥 Historic Low',
		cross_store: '🏪 Best Price',
	};

	const categories = [
		{ value: '', label: 'All Categories' },
		{ value: 'motors', label: 'Motors' },
		{ value: 'escs', label: 'ESCs' },
		{ value: 'flight_controllers', label: 'Flight Controllers' },
		{ value: 'frames', label: 'Frames' },
		{ value: 'vtx', label: 'VTX' },
	];

	async function loadDeals() {
		loading = true;
		error = '';
		try {
			const response = await getDeals({
				category: selectedCategory || undefined,
				min_score: minScore,
			});
			deals = response.deals;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load deals';
		} finally {
			loading = false;
		}
	}

	// Score → color
	function scoreColor(score: number): string {
		if (score >= 8) return 'text-electric-green';
		if (score >= 6) return 'text-electric-blue';
		if (score >= 4) return 'text-yellow-400';
		return 'text-gray-400';
	}

	// Score → bar width
	function scoreWidth(score: number): string {
		return `${(score / 10) * 100}%`;
	}

	onMount(loadDeals);
</script>

<svelte:head>
	<title>FPV Deal Finder - Deals</title>
</svelte:head>

<div class="space-y-6">
	<!-- Page header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold text-gray-100">🔥 Deal Feed</h1>
			<p class="text-gray-500 text-sm mt-1">AI-scored deals from all supported stores</p>
		</div>

		<!-- Filters -->
		<div class="flex items-center gap-3">
			<select
				bind:value={selectedCategory}
				on:change={loadDeals}
				class="bg-dark-700 text-gray-300 text-sm border border-dark-500 rounded-lg px-3 py-2
				       focus:outline-none focus:border-electric-blue"
			>
				{#each categories as cat}
					<option value={cat.value}>{cat.label}</option>
				{/each}
			</select>

			<select
				bind:value={minScore}
				on:change={loadDeals}
				class="bg-dark-700 text-gray-300 text-sm border border-dark-500 rounded-lg px-3 py-2
				       focus:outline-none focus:border-electric-blue"
			>
				<option value={4}>Score 4+</option>
				<option value={6}>Score 6+</option>
				<option value={7}>Score 7+</option>
				<option value={8}>Score 8+ (Best)</option>
			</select>
		</div>
	</div>

	<!-- Loading state -->
	{#if loading}
		<div class="space-y-3">
			{#each Array(5) as _}
				<div class="card p-4 animate-pulse flex gap-4">
					<div class="w-20 h-20 bg-dark-700 rounded-lg flex-shrink-0"></div>
					<div class="flex-1 space-y-2">
						<div class="h-4 bg-dark-700 rounded w-3/4"></div>
						<div class="h-3 bg-dark-700 rounded w-1/2"></div>
						<div class="h-6 bg-dark-700 rounded w-1/4"></div>
					</div>
				</div>
			{/each}
		</div>

	<!-- Error state -->
	{:else if error}
		<div class="card p-8 text-center">
			<p class="text-red-400">{error}</p>
			<button on:click={loadDeals} class="btn-ghost mt-3">Retry</button>
		</div>

	<!-- Empty state -->
	{:else if deals.length === 0}
		<div class="card p-12 text-center">
			<div class="text-5xl mb-4">🤷</div>
			<h3 class="text-lg font-medium text-gray-300 mb-2">No deals found</h3>
			<p class="text-gray-500 text-sm">
				Deals are detected automatically during scraping.
				Try lowering the minimum score or waiting for the next scrape cycle.
			</p>
		</div>

	<!-- Deals list -->
	{:else}
		<div class="space-y-3">
			{#each deals as deal (deal.id)}
				<a
					href={deal.product.url}
					target="_blank"
					rel="noopener noreferrer"
					class="card p-4 flex gap-4 group hover:border-dark-400 cursor-pointer"
				>
					<!-- Product image -->
					<div class="w-20 h-20 flex-shrink-0 bg-dark-700 rounded-lg overflow-hidden">
						{#if deal.product.image_url}
							<img
								src={deal.product.image_url}
								alt={deal.product.title}
								class="w-full h-full object-contain p-1"
								loading="lazy"
							/>
						{:else}
							<div class="w-full h-full flex items-center justify-center text-dark-500 text-2xl">
								🔧
							</div>
						{/if}
					</div>

					<!-- Deal info -->
					<div class="flex-1 min-w-0">
						<div class="flex items-start justify-between gap-3">
							<div class="min-w-0">
								<!-- Deal type badge -->
								<span class="text-xs text-gray-500 mb-1 block">
									{dealTypeLabels[deal.deal_type] || deal.deal_type}
									· <span class="text-gray-600">{deal.product.store}</span>
								</span>

								<!-- Product title -->
								<h3 class="text-sm font-medium text-gray-200 truncate
								           group-hover:text-white transition-colors">
									{deal.product.title}
								</h3>

								<!-- Price -->
								<div class="flex items-baseline gap-2 mt-1">
									<span class="text-lg font-bold text-electric-blue">
										${deal.product.current_price?.toFixed(2)}
									</span>
									{#if deal.product.original_price && deal.product.original_price > (deal.product.current_price || 0)}
										<span class="text-sm text-gray-500 line-through">
											${deal.product.original_price.toFixed(2)}
										</span>
									{/if}
								</div>
							</div>

							<!-- Deal badge & score -->
							<div class="flex-shrink-0 text-right space-y-2">
								{#if deal.discount_percent}
									<DealBadge
										discount={deal.discount_percent}
										score={deal.deal_score}
									/>
								{/if}
							</div>
						</div>

						<!-- AI Score bar -->
						{#if deal.deal_score}
							<div class="mt-2 flex items-center gap-2">
								<span class="text-xs text-gray-600">Deal Score</span>
								<div class="flex-1 h-1.5 bg-dark-600 rounded-full overflow-hidden">
									<div
										class="h-full rounded-full transition-all duration-500
										       {deal.deal_score >= 8 ? 'bg-electric-green' :
										        deal.deal_score >= 6 ? 'bg-electric-blue' : 'bg-yellow-400'}"
										style="width: {scoreWidth(deal.deal_score)}"
									></div>
								</div>
								<span class="text-xs font-mono {scoreColor(deal.deal_score)}">
									{deal.deal_score.toFixed(1)}
								</span>
							</div>
						{/if}
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
