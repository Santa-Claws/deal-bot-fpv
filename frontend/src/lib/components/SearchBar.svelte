<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let value = '';
	export let placeholder = 'Search FPV parts... (e.g. "2207 motors under $30")';
	export let loading = false;

	const dispatch = createEventDispatcher();

	function handleSubmit(e: Event) {
		e.preventDefault();
		dispatch('search', { query: value });
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			dispatch('search', { query: value });
		}
	}
</script>

<form on:submit={handleSubmit} class="relative w-full">
	<!-- Search icon -->
	<div class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
		{#if loading}
			<!-- Spinning loader -->
			<svg class="w-5 h-5 animate-spin text-electric-blue" fill="none" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		{:else}
			<!-- Search icon -->
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
					d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
			</svg>
		{/if}
	</div>

	<input
		type="text"
		bind:value
		on:keydown={handleKeydown}
		{placeholder}
		class="search-input pl-12 pr-32 text-base"
		autocomplete="off"
		spellcheck="false"
	/>

	<!-- AI badge + submit button -->
	<div class="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
		<!-- AI indicator -->
		<span class="hidden sm:flex items-center gap-1 text-xs text-gray-500">
			<svg class="w-3 h-3 text-electric-blue" fill="currentColor" viewBox="0 0 24 24">
				<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
			</svg>
			AI
		</span>
		<button type="submit" class="btn-primary text-sm py-1.5 px-4">
			Search
		</button>
	</div>
</form>

<!-- Search tips hint -->
<p class="text-xs text-gray-600 mt-2 text-center">
	Try: "2207 motor under $30" · "best ESC 4in1 deals" · "5 inch freestyle frame"
</p>
