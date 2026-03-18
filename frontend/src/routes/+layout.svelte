<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';

	const navLinks = [
		{ href: '/', label: 'Search', icon: '🔍' },
		{ href: '/deals', label: 'Deals', icon: '🔥' },
		{ href: '/settings', label: 'Settings', icon: '⚙️' },
	];

	$: currentPath = $page.url.pathname;
</script>

<div class="min-h-screen bg-dark-900 flex flex-col">
	<!-- Top navigation bar -->
	<nav class="bg-dark-800 border-b border-dark-600 sticky top-0 z-50">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
			<div class="flex items-center justify-between h-14">

				<!-- Logo -->
				<a href="/" class="flex items-center gap-2 group">
					<div class="w-7 h-7 rounded-lg bg-gradient-to-br from-electric-blue to-electric-green
					            flex items-center justify-center text-dark-900 font-bold text-sm
					            group-hover:shadow-[0_0_15px_rgba(0,212,255,0.5)] transition-all">
						F
					</div>
					<span class="font-semibold text-gray-100 hidden sm:block">FPV Deal Finder</span>
				</a>

				<!-- Navigation links -->
				<div class="flex items-center gap-1">
					{#each navLinks as link}
						<a
							href={link.href}
							class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
							       {currentPath === link.href
								       ? 'bg-dark-600 text-electric-blue'
								       : 'text-gray-400 hover:text-gray-200 hover:bg-dark-700'}"
						>
							<span class="hidden sm:inline">{link.icon}</span>
							{link.label}
						</a>
					{/each}
				</div>

			</div>
		</div>
	</nav>

	<!-- Page content -->
	<main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6">
		<slot />
	</main>

	<!-- Footer -->
	<footer class="border-t border-dark-700 py-4 mt-8">
		<div class="max-w-7xl mx-auto px-4 text-center text-xs text-gray-600">
			FPV Deal Finder · Self-hosted · Prices update every 6 hours
		</div>
	</footer>
</div>
