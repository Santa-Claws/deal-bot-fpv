<!--
  Settings page

  Configure Discord webhook URL and notification preferences.
  Changes are saved to the backend and take effect immediately.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getNotificationSettings,
		updateNotificationSettings,
		sendTestNotification,
		type NotificationSettings
	} from '$lib/api';

	let settings: NotificationSettings = {
		discord_webhook_url: '',
		min_deal_score: 7.0,
		categories: null,
		max_price: null,
		enabled: true,
	};

	let loading = true;
	let saving = false;
	let testingSend = false;
	let saveSuccess = false;
	let testSuccess: boolean | null = null;
	let error = '';

	const allCategories = ['motors', 'escs', 'flight_controllers', 'frames', 'vtx', 'cameras', 'props', 'batteries'];

	async function loadSettings() {
		try {
			settings = await getNotificationSettings();
		} catch (e) {
			// Use defaults if API fails
		} finally {
			loading = false;
		}
	}

	async function saveSettings() {
		saving = true;
		error = '';
		saveSuccess = false;
		try {
			await updateNotificationSettings(settings);
			saveSuccess = true;
			setTimeout(() => (saveSuccess = false), 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Save failed';
		} finally {
			saving = false;
		}
	}

	async function testWebhook() {
		testingSend = true;
		testSuccess = null;
		try {
			await sendTestNotification(settings.discord_webhook_url || undefined);
			testSuccess = true;
		} catch (e) {
			testSuccess = false;
		} finally {
			testingSend = false;
			setTimeout(() => (testSuccess = null), 5000);
		}
	}

	function toggleCategory(cat: string) {
		if (!settings.categories) {
			// Currently all categories → switch to selected only
			settings.categories = allCategories.filter((c) => c !== cat);
		} else if (settings.categories.includes(cat)) {
			settings.categories = settings.categories.filter((c) => c !== cat);
			if (settings.categories.length === allCategories.length) {
				settings.categories = null; // All selected = null (all)
			}
		} else {
			settings.categories = [...settings.categories, cat];
		}
	}

	function isCategorySelected(cat: string): boolean {
		return settings.categories === null || settings.categories.includes(cat);
	}

	onMount(loadSettings);
</script>

<svelte:head>
	<title>Settings - FPV Deal Finder</title>
</svelte:head>

<div class="max-w-2xl space-y-6">
	<h1 class="text-2xl font-bold text-gray-100">⚙️ Settings</h1>

	{#if loading}
		<div class="card p-8 animate-pulse">
			<div class="space-y-4">
				<div class="h-4 bg-dark-700 rounded w-1/3"></div>
				<div class="h-10 bg-dark-700 rounded"></div>
				<div class="h-4 bg-dark-700 rounded w-1/2"></div>
			</div>
		</div>
	{:else}
		<!-- Discord Notifications -->
		<div class="card p-6 space-y-5">
			<div class="flex items-center justify-between">
				<h2 class="text-lg font-semibold text-gray-200">🔔 Discord Notifications</h2>
				<label class="flex items-center gap-2 cursor-pointer">
					<span class="text-sm text-gray-400">Enabled</span>
					<button
						on:click={() => (settings.enabled = !settings.enabled)}
						class="relative w-10 h-5 rounded-full transition-colors
						       {settings.enabled ? 'bg-electric-blue' : 'bg-dark-500'}"
					>
						<span class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform
						             {settings.enabled ? 'translate-x-5' : 'translate-x-0'}"
						></span>
					</button>
				</label>
			</div>

			<!-- Webhook URL -->
			<div>
				<label class="block text-sm text-gray-400 mb-2">
					Discord Webhook URL
					<a
						href="https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks"
						target="_blank"
						rel="noopener"
						class="text-electric-blue text-xs ml-1 hover:underline"
					>
						How to create →
					</a>
				</label>
				<div class="flex gap-2">
					<input
						type="url"
						bind:value={settings.discord_webhook_url}
						placeholder="https://discord.com/api/webhooks/..."
						class="flex-1 bg-dark-700 text-gray-300 text-sm border border-dark-500 rounded-lg
						       px-3 py-2 focus:outline-none focus:border-electric-blue placeholder-gray-600"
					/>
					<button
						on:click={testWebhook}
						disabled={!settings.discord_webhook_url || testingSend}
						class="btn-ghost text-sm whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
					>
						{#if testingSend}
							Sending...
						{:else}
							Test
						{/if}
					</button>
				</div>
				{#if testSuccess === true}
					<p class="text-xs text-electric-green mt-1">✓ Test notification sent!</p>
				{:else if testSuccess === false}
					<p class="text-xs text-red-400 mt-1">✗ Failed to send. Check your webhook URL.</p>
				{/if}
			</div>

			<!-- Min deal score -->
			<div>
				<label class="block text-sm text-gray-400 mb-2">
					Minimum Deal Score:
					<span class="text-electric-blue font-mono">{settings.min_deal_score.toFixed(1)}</span>
					/10
				</label>
				<input
					type="range"
					bind:value={settings.min_deal_score}
					min="4"
					max="9.5"
					step="0.5"
					class="w-full accent-electric-blue"
				/>
				<div class="flex justify-between text-xs text-gray-600 mt-1">
					<span>4.0 (More alerts)</span>
					<span>9.5 (Only the best)</span>
				</div>
			</div>

			<!-- Max price filter -->
			<div>
				<label class="block text-sm text-gray-400 mb-2">
					Only notify for deals under $
					<span class="text-electric-blue">{settings.max_price || 'any'}</span>
				</label>
				<div class="flex items-center gap-3">
					<input
						type="number"
						bind:value={settings.max_price}
						placeholder="Any price"
						min="0"
						class="w-32 bg-dark-700 text-gray-300 text-sm border border-dark-500 rounded-lg
						       px-3 py-2 focus:outline-none focus:border-electric-blue"
					/>
					{#if settings.max_price}
						<button
							on:click={() => (settings.max_price = null)}
							class="text-xs text-gray-500 hover:text-gray-300"
						>
							Clear
						</button>
					{/if}
				</div>
			</div>

			<!-- Category filter -->
			<div>
				<label class="block text-sm text-gray-400 mb-2">
					Notify for categories:
					<span class="text-xs text-gray-600">
						{settings.categories === null ? 'All' : settings.categories.length + ' selected'}
					</span>
				</label>
				<div class="flex flex-wrap gap-2">
					{#each allCategories as cat}
						<button
							on:click={() => toggleCategory(cat)}
							class="text-xs px-2.5 py-1 rounded-full border transition-all
							       {isCategorySelected(cat)
								       ? 'bg-electric-blue bg-opacity-20 text-electric-blue border-electric-blue border-opacity-30'
								       : 'bg-dark-600 text-gray-500 border-dark-500 hover:border-dark-400'}"
						>
							{cat.replace('_', ' ')}
						</button>
					{/each}
				</div>
			</div>
		</div>

		<!-- Save button -->
		<div class="flex items-center gap-3">
			<button
				on:click={saveSettings}
				disabled={saving}
				class="btn-primary disabled:opacity-60 disabled:cursor-not-allowed"
			>
				{#if saving}
					Saving...
				{:else}
					Save Settings
				{/if}
			</button>

			{#if saveSuccess}
				<span class="text-electric-green text-sm">✓ Saved!</span>
			{/if}

			{#if error}
				<span class="text-red-400 text-sm">{error}</span>
			{/if}
		</div>

		<!-- Info section -->
		<div class="card p-5 space-y-3">
			<h3 class="text-sm font-semibold text-gray-400">ℹ️ About Notifications</h3>
			<div class="text-xs text-gray-500 space-y-2">
				<p>
					Deal alerts are sent to your Discord channel when a deal is detected that scores
					above your minimum threshold. The AI scores deals 0-10 based on:
				</p>
				<ul class="list-disc list-inside space-y-1 ml-2">
					<li>Discount percentage vs. normal price</li>
					<li>Price vs. 30-day average</li>
					<li>Historical price for this product</li>
					<li>Whether this is an FPV-relevant category</li>
				</ul>
				<p class="text-gray-600">
					Scrapers run every 6 hours. You can trigger a manual scrape with:<br />
					<code class="bg-dark-700 text-electric-blue px-1 rounded text-xs">
						docker exec fpv-celery-worker celery -A app.scrapers.runner call scrape_all_deals
					</code>
				</p>
			</div>
		</div>
	{/if}
</div>
