<script lang="ts">
	export let discount: number;
	export let score: number | null = null;
	export let dealType: string | null = null;

	// Color based on discount amount
	$: badgeColor = discount >= 30
		? 'bg-electric-green bg-opacity-20 text-electric-green border-electric-green border-opacity-30'
		: discount >= 15
		? 'bg-yellow-500 bg-opacity-20 text-yellow-400 border-yellow-500 border-opacity-30'
		: 'bg-orange-500 bg-opacity-20 text-orange-400 border-orange-500 border-opacity-30';
</script>

<div class="flex flex-col items-end gap-1">
	<!-- Discount percentage badge -->
	<span class="text-xs font-bold px-2 py-0.5 rounded-full border {badgeColor}">
		{Math.round(discount)}% OFF
	</span>

	<!-- Deal score if provided -->
	{#if score !== null}
		<span class="text-xs text-gray-400">
			⭐ {score.toFixed(1)}/10
		</span>
	{/if}

	<!-- Deal type indicator -->
	{#if dealType === 'historic_low'}
		<span class="text-xs font-bold text-electric-blue bg-electric-blue bg-opacity-10 px-1.5 py-0.5 rounded border border-electric-blue border-opacity-20">
			ALL TIME LOW
		</span>
	{/if}
</div>
