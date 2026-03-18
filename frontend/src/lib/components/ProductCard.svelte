<script lang="ts">
	import type { Product } from '$lib/api';
	import DealBadge from './DealBadge.svelte';

	export let product: Product;

	// Format price with 2 decimal places
	function formatPrice(price: number): string {
		return price.toFixed(2);
	}

	// Store color mapping (consistent colors per store)
	const storeColors: Record<string, string> = {
		NewBeeDrone: 'text-yellow-400',
		PyroDrone: 'text-orange-400',
		RaceDayQuads: 'text-blue-400',
		GetFPV: 'text-purple-400',
		GEPRC: 'text-green-400',
		HDZero: 'text-cyan-400',
		'Rotor Village': 'text-red-400',
	};

	$: storeColor = storeColors[product.store] || 'text-gray-400';

	function hideOnError(e: Event) {
		const img = e.target as HTMLImageElement;
		img.style.display = 'none';
	}
</script>

<a
	href={product.url}
	target="_blank"
	rel="noopener noreferrer"
	class="card block p-4 group cursor-pointer"
>
	<!-- Product image -->
	<div class="relative mb-3 aspect-square bg-dark-700 rounded-lg overflow-hidden">
		{#if product.image_url}
			<img
				src={product.image_url}
				alt={product.title}
				class="w-full h-full object-contain p-2 group-hover:scale-105 transition-transform duration-300"
				loading="lazy"
				on:error={hideOnError}
			/>
		{:else}
			<!-- Placeholder when no image -->
			<div class="w-full h-full flex items-center justify-center text-dark-500">
				<svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
						d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
				</svg>
			</div>
		{/if}

		<!-- Out of stock overlay -->
		{#if !product.in_stock}
			<div class="absolute inset-0 bg-dark-900 bg-opacity-70 flex items-center justify-center">
				<span class="text-gray-400 text-sm font-medium">Out of Stock</span>
			</div>
		{/if}

		<!-- Deal badge overlay -->
		{#if product.is_deal && product.discount_percent}
			<div class="absolute top-2 right-2">
				<DealBadge discount={product.discount_percent} />
			</div>
		{/if}
	</div>

	<!-- Product info -->
	<div class="space-y-1.5">
		<!-- Title -->
		<h3 class="text-sm font-medium text-gray-200 leading-snug line-clamp-2 group-hover:text-white transition-colors">
			{product.title}
		</h3>

		<!-- Store + Category -->
		<div class="flex items-center gap-2 flex-wrap">
			<span class="text-xs font-medium {storeColor}">{product.store}</span>
			{#if product.category}
				<span class="category-tag">{product.category.replace('_', ' ')}</span>
			{/if}
		</div>

		<!-- Price -->
		<div class="flex items-baseline gap-2">
			<span class="text-lg font-bold text-electric-blue">
				${formatPrice(product.price)}
			</span>
			{#if product.original_price && product.original_price > product.price}
				<span class="text-sm text-gray-500 line-through">
					${formatPrice(product.original_price)}
				</span>
				<span class="text-xs text-electric-green font-medium">
					{product.discount_percent?.toFixed(0)}% off
				</span>
			{/if}
		</div>
	</div>

	<!-- External link indicator -->
	<div class="mt-2 text-xs text-gray-600 flex items-center gap-1 group-hover:text-gray-500 transition-colors">
		<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
				d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
		</svg>
		View on {product.store}
	</div>
</a>
