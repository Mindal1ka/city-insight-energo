<!-- Кільце класів K + легенда-фільтр (клік по рядку вмикає/вимикає клас) -->
<script lang="ts">
	import { Tween } from 'svelte/motion';
	import { EASE, DUR, isReduced } from '../motion.ts';
	import { CLASSES, type KClass } from './DashData.ts';

	let {
		counts,
		selected = [],
		ontoggle,
		center = ''
	}: {
		counts: Record<KClass, number>;
		selected?: string[];
		ontoggle?: (slug: string) => void;
		center?: string;
	} = $props();

	const total = $derived(CLASSES.reduce((s, c) => s + (counts[c.id] ?? 0), 0));
	// Дуги одразу в кінцевому стані; рух (300 мс) лише коли змінюються дані — напр. після фільтра
	const fracs = () => CLASSES.map((c) => (total ? (counts[c.id] ?? 0) / total : 0));
	const vals = new Tween<number[]>(fracs(), { duration: DUR.slow, easing: EASE.out });
	$effect(() => {
		vals.set(fracs(), { duration: isReduced() ? 0 : DUR.slow });
	});
	const R = 62;
	const C = 2 * Math.PI * R;
	const arcs = $derived.by(() => {
		let acc = 0;
		return CLASSES.map((c, i) => {
			const f = vals.current[i] ?? 0;
			const a = { c, len: Math.max(0, f * C - (f > 0.004 ? 2 : 0)), off: -acc * C };
			acc += f;
			return a;
		});
	});
	const pct = (n: number) => (total ? Math.round((n / total) * 100) : 0);
	const desc = $derived(CLASSES.map((c) => `${c.short}: ${counts[c.id] ?? 0}`).join(', '));
</script>

<div class="dd">
	<svg viewBox="0 0 160 160" width="144" height="144" role="img" aria-label="Класи K. {desc}">
		<circle cx="80" cy="80" r={R} fill="none" stroke="var(--line-soft)" stroke-width="22" />
		<g transform="rotate(-90 80 80)">
			{#each arcs as a (a.c.id)}
				<circle
					cx="80"
					cy="80"
					r={R}
					fill="none"
					stroke={a.c.color}
					stroke-width={selected.length && !selected.includes(a.c.slug) ? 14 : 22}
					stroke-dasharray="{a.len} {C}"
					stroke-dashoffset={a.off}
					opacity={selected.length && !selected.includes(a.c.slug) ? 0.35 : 1}
				/>
			{/each}
		</g>
		<text x="80" y="80" text-anchor="middle" class="big">{total}</text>
		<text x="80" y="98" text-anchor="middle" class="small">{center}</text>
	</svg>
	<ul class="lg">
		{#each CLASSES as c (c.id)}
			{@const n = counts[c.id] ?? 0}
			<li>
				<button
					type="button"
					class="row"
					aria-pressed={selected.includes(c.slug)}
					disabled={!ontoggle}
					onclick={() => ontoggle?.(c.slug)}
				>
					<span class="sym" style="background:{c.soft};color:{c.ink};border-color:{c.color}" aria-hidden="true">{c.sym}</span>
					<span class="nm">{c.short}</span>
					<span class="n">{n}</span>
					<span class="p">{pct(n)}%</span>
				</button>
			</li>
		{/each}
	</ul>
</div>

<style>
	.dd {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		flex-wrap: wrap;
	}
	svg {
		flex: none;
	}
	circle {
		transition:
			stroke-width var(--dur-fast) var(--ease-out),
			opacity var(--dur-fast) var(--ease-out);
	}
	.big {
		font-size: 30px;
		font-weight: 800;
		fill: var(--ink);
		font-variant-numeric: tabular-nums;
	}
	.small {
		font-size: 11px;
		fill: var(--muted);
	}
	.lg {
		list-style: none;
		margin: 0;
		padding: 0;
		flex: 1;
		min-width: 12rem;
		display: grid;
		gap: 0.2rem;
	}
	.row {
		display: grid;
		grid-template-columns: 1.6rem 1fr auto 3rem;
		align-items: center;
		gap: 0.55rem;
		width: 100%;
		padding: 0.35rem 0.5rem;
		border: 1px solid transparent;
		border-radius: var(--r-btn);
		background: none;
		font: inherit;
		color: var(--text);
		text-align: left;
		cursor: pointer;
		transition: background var(--dur-fast);
	}
	.row:disabled {
		cursor: default;
	}
	.row:not(:disabled):hover {
		background: var(--neutral-soft);
	}
	.row[aria-pressed='true'] {
		border-color: var(--navy);
		background: var(--accent-soft);
	}
	.sym {
		display: grid;
		place-items: center;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		border: 1.5px solid;
		font-weight: 800;
		font-size: 0.85rem;
	}
	.nm {
		font-weight: 600;
		font-size: 0.92rem;
	}
	.n {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.p {
		color: var(--muted);
		font-size: 0.85rem;
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	@media (prefers-reduced-motion: reduce) {
		circle {
			transition: none;
		}
	}
</style>
