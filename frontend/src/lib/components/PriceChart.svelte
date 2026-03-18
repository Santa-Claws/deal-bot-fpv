<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import type { PriceHistory } from '$lib/api';

	export let history: PriceHistory;

	let canvas: HTMLCanvasElement;
	let chart: unknown;

	onMount(async () => {
		// Dynamically import Chart.js to avoid SSR issues
		const { Chart, registerables } = await import('chart.js');
		Chart.register(...registerables);

		const labels = history.data_points.map((p) => {
			return new Date(p.date).toLocaleDateString('en-US', {
				month: 'short',
				day: 'numeric',
			});
		});

		const prices = history.data_points.map((p) => p.price);
		const originalPrices = history.data_points.map((p) => p.original_price);

		chart = new Chart(canvas, {
			type: 'line',
			data: {
				labels,
				datasets: [
					{
						label: 'Price',
						data: prices,
						borderColor: '#00d4ff',
						backgroundColor: 'rgba(0, 212, 255, 0.1)',
						borderWidth: 2,
						pointBackgroundColor: '#00d4ff',
						pointRadius: 3,
						pointHoverRadius: 6,
						tension: 0.3,
						fill: true,
					},
					// Show original price line if any price had a discount
					...(originalPrices.some(Boolean)
						? [
								{
									label: 'Original Price',
									data: originalPrices,
									borderColor: '#4b5563',
									borderDash: [5, 5],
									borderWidth: 1.5,
									pointRadius: 0,
									tension: 0.3,
									fill: false,
								},
							]
						: []),
				],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: {
					mode: 'index',
					intersect: false,
				},
				plugins: {
					legend: {
						display: originalPrices.some(Boolean),
						labels: {
							color: '#9ca3af',
							usePointStyle: true,
							pointStyleWidth: 8,
						},
					},
					tooltip: {
						backgroundColor: '#1c1c22',
						borderColor: '#2c2c33',
						borderWidth: 1,
						titleColor: '#e5e7eb',
						bodyColor: '#9ca3af',
						callbacks: {
							label: (ctx) => `$${ctx.parsed.y.toFixed(2)}`,
						},
					},
				},
				scales: {
					x: {
						grid: { color: '#1c1c22' },
						ticks: { color: '#6b7280', maxTicksLimit: 8 },
					},
					y: {
						grid: { color: '#1c1c22' },
						ticks: {
							color: '#6b7280',
							callback: (val) => `$${val}`,
						},
					},
				},
			},
		});
	});

	onDestroy(() => {
		if (chart && typeof (chart as { destroy?: () => void }).destroy === 'function') {
			(chart as { destroy: () => void }).destroy();
		}
	});
</script>

<div class="relative">
	<!-- Chart container -->
	<div class="h-48 relative">
		<canvas bind:this={canvas}></canvas>
	</div>

	<!-- Stats below chart -->
	{#if history.stats}
		<div class="grid grid-cols-4 gap-3 mt-4">
			<div class="text-center">
				<div class="text-xs text-gray-500 mb-1">Current</div>
				<div class="text-sm font-bold text-electric-blue">${history.stats.current.toFixed(2)}</div>
			</div>
			<div class="text-center">
				<div class="text-xs text-gray-500 mb-1">Lowest</div>
				<div class="text-sm font-bold text-electric-green">${history.stats.min.toFixed(2)}</div>
			</div>
			<div class="text-center">
				<div class="text-xs text-gray-500 mb-1">Highest</div>
				<div class="text-sm font-bold text-red-400">${history.stats.max.toFixed(2)}</div>
			</div>
			<div class="text-center">
				<div class="text-xs text-gray-500 mb-1">30d Avg</div>
				<div class="text-sm font-bold text-gray-300">${history.stats.avg.toFixed(2)}</div>
			</div>
		</div>

		{#if history.stats.all_time_low}
			<div class="mt-3 text-center">
				<span class="text-xs font-bold text-electric-blue bg-electric-blue bg-opacity-10
				             px-3 py-1 rounded-full border border-electric-blue border-opacity-20">
					🔥 This is the lowest price we've recorded!
				</span>
			</div>
		{/if}
	{/if}
</div>
