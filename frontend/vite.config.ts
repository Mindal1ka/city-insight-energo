import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Примусовий режим рун для проєкту (крім бібліотек). Можна прибрати у Svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// SPA: усе збирається у frontend/build, бекенд (FastAPI) віддає index.html для будь-якого шляху
			adapter: adapter({ pages: 'build', assets: 'build', fallback: 'index.html' })
		})
	],
	server: {
		// У режимі розробки всі запити /api йдуть на локальний FastAPI
		proxy: {
			'/api': 'http://127.0.0.1:8000'
		}
	}
});
