<!--
	Значок типу будівлі за category_short з UMUNI (школа, садок, лікарня…). Лише декоративний:
	назву категорії завжди показуйте поруч текстом.
	Використання: <CategoryIcon category={it.category_short} size={22} />
-->
<script lang="ts">
	let { category, size = 22 }: { category: string; size?: number } = $props();

	const kind = $derived.by(() => {
		const c = category.toLocaleLowerCase('uk');
		if (c.startsWith('охорона')) return 'health';
		if (c.startsWith('дошкіл')) return 'kinder';
		if (c.startsWith('заклади освіти') || c.includes('освіт')) return 'school';
		if (c.startsWith('житлов')) return 'home';
		if (c.startsWith('спорт')) return 'sport';
		return 'public';
	});
</script>

<svg
	class="cat-ic"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.8"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
	focusable="false"
>
	{#if kind === 'health'}
		<rect x="3.5" y="3.5" width="17" height="17" rx="4" />
		<path d="M12 8v8M8 12h8" stroke-width="2.4" />
	{:else if kind === 'kinder'}
		<rect x="3.5" y="13" width="7" height="7" rx="1.2" />
		<rect x="13.5" y="13" width="7" height="7" rx="1.2" />
		<rect x="8.5" y="4" width="7" height="7" rx="1.2" />
	{:else if kind === 'school'}
		<path d="M2.5 9.5 12 5l9.5 4.5L12 14z" />
		<path d="M6.5 11.5v4.2c0 1.3 2.5 2.8 5.5 2.8s5.5-1.5 5.5-2.8v-4.2" />
		<path d="M21.5 9.5v5" />
	{:else if kind === 'home'}
		<path d="M3.5 11 12 4l8.5 7" />
		<path d="M5.5 9.5V20h13V9.5" />
		<path d="M10 20v-5.5h4V20" />
	{:else if kind === 'sport'}
		<circle cx="12" cy="12" r="8.5" />
		<path d="M3.8 9.5c3 .8 5.3 3.2 6 6.6M20.2 14.5c-3-.8-5.3-3.2-6-6.6M12 3.5c-1.2 2.7-1.2 14.3 0 17" />
	{:else}
		<path d="M3 9.5 12 4l9 5.5" />
		<path d="M5 10v8M9.7 10v8M14.3 10v8M19 10v8" />
		<path d="M3 20.5h18" />
	{/if}
</svg>

<style>
	.cat-ic {
		display: block;
		flex: none;
	}
</style>
