<script lang="ts">
	// Перемикач моменту: «Зараз» або «Літній день» (для демонстрації надлишку) + підпис активного моменту
	import { page } from '$app/state';
	import { VIEWS, type ViewKey } from './api.ts';
	import { moment } from './format.ts';
	import { viewFrom } from './view.ts';
	import Icon from './Icon.svelte';

	let { now = null }: { now?: string | null } = $props();

	const view = $derived(viewFrom(page.url));
	const m = $derived(moment(now));

	function href(v: ViewKey): string {
		const p = new URLSearchParams(page.url.search);
		if (v === 'now') p.delete('view');
		else p.set('view', v);
		const s = p.toString();
		return page.url.pathname + (s ? `?${s}` : '');
	}
</script>

<div class="vs">
	<nav class="seg seg-sm" aria-label="Момент перегляду даних">
		{#each Object.entries(VIEWS) as [key, v] (key)}
			<a
				href={href(key as ViewKey)}
				aria-current={view === key ? 'page' : undefined}
				data-sveltekit-reset="false"
				data-sveltekit-replacestate
			>
				<Icon name={key === 'now' ? 'clock' : 'sun'} size={16} />
				{v.label}
			</a>
		{/each}
	</nav>
	{#if m}
		<p class="when" aria-live="polite">
			Дані на <strong class="tnum">{m.date}, {m.time}</strong>
			<span class="sep" aria-hidden="true">·</span> змодельовано
		</p>
	{/if}
</div>

<style>
	.vs {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.9rem;
	}
	.seg-sm a {
		padding: 0.35rem 0.8rem;
		font-size: 0.9rem;
	}
	.when {
		margin: 0;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.when strong {
		color: var(--text);
	}
	.sep {
		margin: 0 0.15rem;
	}
</style>
