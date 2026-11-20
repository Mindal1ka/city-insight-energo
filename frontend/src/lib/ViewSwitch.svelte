<script lang="ts">
	// Перемикач моменту: «Зараз» або «Літній день» (як працювали б станції в сонячний червневий день).
	// Під перемикачем — одне речення, що саме зараз показано, щоб не треба було здогадуватися.
	import { page } from '$app/state';
	import { VIEWS, type ViewKey } from './api.ts';
	import { moment, longDate } from './format.ts';
	import { viewFrom } from './view.ts';
	import Icon from './Icon.svelte';

	let { now = null }: { now?: string | null } = $props();

	const view = $derived(viewFrom(page.url));
	const m = $derived(moment(now));
	const summerDay = $derived(longDate(VIEWS.summer.day).replace(/\s?\d{4}\s?р\.?$/, ''));

	const SUB: Record<ViewKey, string> = {
		now: 'сьогодні',
		summer: 'для порівняння'
	};

	function href(v: ViewKey): string {
		const p = new URLSearchParams(page.url.search);
		if (v === 'now') p.delete('view');
		else p.set('view', v);
		const s = p.toString();
		return page.url.pathname + (s ? `?${s}` : '');
	}
</script>

<div class="vs">
	<span class="vs-label" id="vs-label">Показати енергію</span>
	<nav class="seg seg-sm" aria-labelledby="vs-label">
		{#each Object.entries(VIEWS) as [key, v] (key)}
			<a
				href={href(key as ViewKey)}
				aria-current={view === key ? 'page' : undefined}
				data-sveltekit-reset="false"
				data-sveltekit-replacestate
				data-sveltekit-noscroll
			>
				<Icon name={key === 'now' ? 'clock' : 'sun'} size={16} />
				<span class="opt">
					<span class="opt-main">{v.label}</span>
					<span class="opt-sub">{SUB[key as ViewKey]}</span>
				</span>
			</a>
		{/each}
	</nav>
	<p class="when" aria-live="polite">
		{#if view === 'summer'}
			Показано сонячний день <strong>{summerDay}, {VIEWS.summer.hour}:00</strong> — так станції працюють
			улітку.
		{:else if m}
			Дані на <strong class="tnum">{m.date}, {m.time}</strong>. Генерацію змодельовано.
		{/if}
	</p>
</div>

<style>
	.vs {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.35rem;
		max-width: 24rem;
	}
	.vs-label {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--muted);
	}
	.seg-sm a {
		padding: 0.35rem 0.85rem 0.35rem 0.7rem;
		font-size: 0.95rem;
		line-height: 1.15;
	}
	.opt {
		display: flex;
		flex-direction: column;
	}
	.opt-sub {
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--muted);
	}
	.when {
		margin: 0;
		font-size: 0.875rem;
		color: var(--muted);
		line-height: 1.4;
	}
	.when strong {
		color: var(--text);
		font-weight: 600;
	}

	/* Телефон: компактний сегментований перемикач в один ряд на всю ширину */
	@media (max-width: 640px) {
		.vs {
			max-width: none;
			width: 100%;
			gap: 0.3rem;
		}
		.vs-label {
			position: absolute;
			width: 1px;
			height: 1px;
			overflow: hidden;
			clip: rect(0 0 0 0);
			white-space: nowrap;
		}
		.seg {
			display: flex;
			width: 100%;
			padding: 3px;
			gap: 3px;
			overflow: visible;
		}
		.seg.seg-sm a {
			flex: 1 1 0;
			justify-content: center;
			min-height: 38px;
			padding: 0.3rem 0.5rem;
			font-size: 0.9rem;
		}
		.opt-sub {
			display: none;
		}
		.when {
			font-size: 0.8rem;
			line-height: 1.35;
		}
	}
</style>
