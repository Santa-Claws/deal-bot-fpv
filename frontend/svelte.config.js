import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// Use Node.js adapter for Docker deployment
		adapter: adapter({
			out: 'build',
		}),
	},
};

export default config;
