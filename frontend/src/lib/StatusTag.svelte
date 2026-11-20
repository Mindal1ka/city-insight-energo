<script lang="ts">
	// Стан об'єкта за сьогодні: знак + слово + колір (колір ніколи не єдиний носій сенсу)
	import type { SiteStatus } from './api.ts';
	import { num } from './format.ts';

	let {
		status,
		kwh = null,
		size = 'md'
	}: { status: SiteStatus; kwh?: number | null; size?: 'sm' | 'md' | 'lg' } = $props();

	const meta = $derived(
		status === 'surplus'
			? { sign: '+', word: 'надлишок' }
			: status === 'deficit'
				? { sign: '−', word: 'дефіцит' }
				: { sign: '○', word: 'немає СЕС' }
	);
</script>

<span class="tag {status} {size}">
	<span class="sign" aria-hidden="true">{meta.sign}</span>
	<span class="word">{meta.word}</span>
	{#if kwh !== null && status !== 'no_ses'}
		<span class="val tnum">{num(Math.abs(kwh), 1)} кВт·год</span>
	{/if}
</span>

<style>
	.tag {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.2rem 0.7rem 0.2rem 0.25rem;
		border-radius: var(--r-pill);
		font-size: 0.875rem;
		font-weight: 600;
		white-space: nowrap;
		border: 1px solid transparent;
		line-height: 1.4;
	}
	.sign {
		display: grid;
		place-items: center;
		width: 1.35rem;
		height: 1.35rem;
		border-radius: 50%;
		font-weight: 800;
		font-size: 1rem;
		line-height: 1;
		color: #fff;
	}
	.val {
		font-weight: 700;
	}
	.surplus {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
		border-color: #b5dcc0;
	}
	.surplus .sign {
		background: var(--surplus);
	}
	.deficit {
		background: var(--deficit-soft);
		color: var(--deficit-ink);
		border-color: #f3c3ad;
	}
	.deficit .sign {
		background: var(--deficit);
	}
	.no_ses {
		background: var(--neutral-soft);
		color: #3d4857;
		border-color: #d6dce4;
	}
	.no_ses .sign {
		color: #5b6676;
		font-size: 0.85rem;
	}
	.sm {
		font-size: 0.8125rem;
	}
	.lg {
		font-size: 1rem;
		padding: 0.35rem 0.95rem 0.35rem 0.35rem;
	}
	.lg .sign {
		width: 1.75rem;
		height: 1.75rem;
		font-size: 1.25rem;
	}
</style>
