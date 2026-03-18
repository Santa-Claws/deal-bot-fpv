/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			colors: {
				// FPV electric blue/green theme
				electric: {
					blue: '#00d4ff',
					green: '#00ff88',
				},
				// Dark mode backgrounds
				dark: {
					900: '#0d0d0f',
					800: '#141418',
					700: '#1c1c22',
					600: '#242429',
					500: '#2c2c33',
				},
			},
			fontFamily: {
				sans: ['Inter', 'system-ui', 'sans-serif'],
				mono: ['JetBrains Mono', 'monospace'],
			},
			animation: {
				'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
				'glow': 'glow 2s ease-in-out infinite alternate',
			},
			keyframes: {
				glow: {
					'0%': { boxShadow: '0 0 5px #00d4ff33' },
					'100%': { boxShadow: '0 0 20px #00d4ff66, 0 0 40px #00d4ff22' },
				},
			},
		},
	},
	plugins: [],
};
