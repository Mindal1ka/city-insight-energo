<script lang="ts">
	// Знак City Insight Map: шестигранна ділянка мапи, у центрі вузол-сонце, лінії до об'єктів.
	// tone="light" — для світлого фону (синій шестикутник), "dark" — для темного (білий).
	let { size = 32, tone = 'light' }: { size?: number; tone?: 'light' | 'dark' } = $props();
	const ink = $derived(tone === 'dark' ? '#FFFFFF' : '#0B2545');
	const bg = $derived(tone === 'dark' ? '#0B2545' : '#FFFFFF');
</script>

<svg class="brandmark" viewBox="10 6 84 96" width={size} height={Math.round((size * 96) / 84)} aria-hidden="true">
	<g transform="translate(4 4)">
		<path d="M48 4l40 23v46L48 96 8 73V27z" fill={ink} />
		<g stroke={bg} stroke-width="4" stroke-linecap="round" opacity=".9"><path d="M48 50V12M48 50L81 69M48 50L15 69" /></g>
		<g fill={bg}><circle cx="48" cy="14" r="5" /><circle cx="80" cy="68" r="5" /><circle cx="16" cy="68" r="5" /></g>
		<circle cx="48" cy="50" r="13" fill="#F5B84A" stroke={ink} stroke-width="4" />
	</g>
</svg>

<style>
	.brandmark {
		display: block;
		flex: none;
	}
</style>
