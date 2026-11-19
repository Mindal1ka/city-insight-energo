<!-- Плитка показника: іконка, підпис, велике число (набігає), одиниця, дрібний рядок під ним -->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import CountUp from '#lib/CountUp.svelte';
	import Icon from '#lib/Icon.svelte';

	type IconName = 'sun' | 'battery' | 'bolt' | 'plug' | 'building' | 'panel' | 'inverter' | 'check' | 'clock' | 'grid' | 'chart' | 'wallet' | 'gauge' | 'info' | 'users' | 'pin' | 'alert';
	let {
		icon,
		label,
		value = null,
		text = null,
		unit = '',
		decimals = 0,
		sub = '',
		tone = 'neutral',
		i = 0,
		children
	}: {
		icon: IconName;
		label: string;
		value?: number | null;
		/** Текстове значення замість числа (модель інвертора, дата) */
		text?: string | null;
		unit?: string;
		decimals?: number;
		sub?: string;
		tone?: 'neutral' | 'sun' | 'good' | 'warn' | 'grid' | 'cons' | 'bat' | 'muted';
		i?: number;
		children?: Snippet;
	} = $props();
	const empty = $derived(text === null && (value === null || value === undefined));
</script>

<div class="tile t-{tone}" style="--d: {Math.min(i * 45, 400)}ms">
	<span class="ic" aria-hidden="true"><Icon name={icon} size={20} /></span>
	<p class="l">{label}</p>
	<p class="v" class:empty>
		{#if text !== null}<span class="txt" title={text}>{text}</span>
		{:else if empty}<span class="na">немає даних</span>
		{:else}<CountUp {value} {decimals} />{#if unit}<small>&nbsp;{unit}</small>{/if}{/if}
	</p>
	{#if sub}<p class="s">{sub}</p>{/if}
	{@render children?.()}
</div>

<style>
	.tile {
		position: relative;
		display: grid;
		grid-template-columns: auto 1fr;
		grid-template-areas: 'ic l' 'v v' 's s';
		align-items: center;
		gap: 0.35rem 0.6rem;
		padding: 0.9rem 1rem;
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius);
		min-width: 0;
		animation: obj-rise 0.5s var(--ease-out) both;
		animation-delay: var(--d);
		transition:
			border-color var(--dur-fast),
			transform var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast);
	}
	.tile:hover {
		border-color: var(--card-line-hover);
		box-shadow: var(--shadow-md);
		transform: translateY(-1px);
	}
	.ic {
		grid-area: ic;
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 9px;
		background: var(--neutral-soft);
		color: var(--muted);
	}
	.t-sun .ic { background: var(--sun-soft); color: var(--sun-ink); }
	.t-good .ic { background: var(--surplus-soft); color: var(--surplus-ink); }
	.t-warn .ic { background: var(--deficit-soft); color: var(--deficit-ink); }
	.t-grid .ic, .t-cons .ic { background: var(--accent-soft); color: var(--cons); }
	.t-bat .ic { background: #ece8fb; color: #4b3a99; }
	.l {
		grid-area: l;
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--muted);
		line-height: 1.2;
		min-width: 0;
	}
	.v {
		grid-area: v;
		margin: 0;
		font-size: 1.6rem;
		font-weight: 700;
		color: var(--ink);
		line-height: 1.1;
		font-variant-numeric: tabular-nums;
		min-width: 0;
	}
	.v small {
		font-size: var(--fs-sm);
		font-weight: 600;
		color: var(--muted);
	}
	.txt {
		display: block;
		font-size: 1.05rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.na {
		font-size: var(--fs-sm);
		font-weight: 500;
		color: var(--muted);
	}
	.s {
		grid-area: s;
		margin: 0;
		font-size: var(--fs-xs);
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	@keyframes obj-rise {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.tile {
			animation: none;
			transition: none;
		}
		.tile:hover {
			transform: none;
		}
	}
	@media (max-width: 640px) {
		.tile {
			padding: 0.75rem;
		}
		.v {
			font-size: 1.3rem;
		}
	}
</style>
