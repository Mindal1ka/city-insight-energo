<script lang="ts">
	// Індекс енергонезалежності 0–100: число + слово + «стовпчики сигналу» (колір не єдиний носій сенсу)
	import type { IndexClass } from './api-independence.ts';

	let {
		index,
		cls,
		size = 'md',
		showWord = true
	}: { index: number | null; cls: IndexClass; size?: 'sm' | 'md' | 'lg'; showWord?: boolean } = $props();

	const bars = $derived(cls === 'висока' ? 3 : cls === 'середня' ? 2 : cls === 'низька' ? 1 : 0);
	const tone = $derived(cls === 'висока' ? 'hi' : cls === 'середня' ? 'mid' : cls === 'низька' ? 'low' : 'none');
	const label = $derived(
		`Індекс енергонезалежності ${index ?? 0} зі 100 — ${cls === 'відсутня' ? 'енергонезалежності немає' : cls}`
	);
</script>

<span class="ib {tone} {size}" role="img" aria-label={label} title={label}>
	<span class="bars" aria-hidden="true">
		{#each [1, 2, 3] as b (b)}
			<i class:on={b <= bars} style="height: {30 + b * 23}%"></i>
		{/each}
	</span>
	<span class="n tnum" aria-hidden="true">{index ?? 0}</span>
	{#if showWord}<span class="w" aria-hidden="true">{cls === 'відсутня' ? 'немає' : cls}</span>{/if}
</span>

<style>
	.ib {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.18rem 0.65rem 0.18rem 0.5rem;
		border-radius: 999px;
		border: 1px solid;
		font-size: 0.875rem;
		font-weight: 700;
		line-height: 1.4;
		white-space: nowrap;
		vertical-align: middle;
	}
	.bars {
		display: inline-flex;
		align-items: flex-end;
		gap: 2px;
		height: 0.95em;
	}
	.bars i {
		display: block;
		width: 0.28em;
		border-radius: 1px;
		background: currentColor;
		opacity: 0.22;
	}
	.bars i.on {
		opacity: 1;
	}
	.n {
		font-size: 1.05em;
	}
	.w {
		font-weight: 600;
	}
	.hi {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
		border-color: #b5dcc0;
	}
	.mid {
		background: var(--sun-soft);
		color: var(--sun-ink);
		border-color: #f0d49b;
	}
	.low {
		background: var(--deficit-soft);
		color: var(--deficit-ink);
		border-color: #f3c3ad;
	}
	.none {
		background: var(--neutral-soft);
		color: #3d4857;
		border-color: #cfd7e1;
	}
	.sm {
		font-size: 0.8125rem;
		padding: 0.1rem 0.55rem 0.1rem 0.45rem;
	}
	.lg {
		font-size: 1.15rem;
		padding: 0.35rem 1rem 0.35rem 0.8rem;
		gap: 0.55rem;
	}
	.lg .n {
		font-size: 1.5em;
		letter-spacing: -0.02em;
	}
</style>
