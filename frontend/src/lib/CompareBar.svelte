<script lang="ts">
	// SVG-бари: питоме споживання будівлі проти медіани її категорії
	import { num } from './format.ts';

	let {
		value,
		median,
		category,
		year
	}: { value: number | null; median: number | null; category: string; year: string } = $props();

	const max = $derived(Math.max(value ?? 0, median ?? 0, 1) * 1.05);
	const rows = $derived([
		{ label: 'Ця будівля', v: value, fill: 'var(--accent)', strong: true },
		{ label: `Типова будівля категорії «${category}»`, v: median, fill: '#7d8896', strong: false }
	]);
</script>

<figure>
	<figcaption class="visually-hidden">
		Питоме споживання за {year} рік: ця будівля {num(value, 1)} кВт·год/м², типова будівля категорії
		«{category}» {num(median, 1)} кВт·год/м²
	</figcaption>
	<ul class="bars" aria-hidden="true">
		{#each rows as r, i (r.label)}
			<li>
				<span class="lbl" class:strong={r.strong}>{r.label}</span>
				<span class="row">
					<svg viewBox="0 0 100 10" preserveAspectRatio="none">
						<rect x="0" y="0" width="100" height="10" fill="#eef2f6" />
						<rect class="grow" style="--i:{i}" x="0" y="0" width={r.v ? (r.v / max) * 100 : 0} height="10" fill={r.fill} />
					</svg>
					<span class="val">{num(r.v, 1)} кВт·год/м²</span>
				</span>
			</li>
		{/each}
	</ul>
</figure>

<style>
	figure {
		margin: 0 0 0.75rem;
	}
	.bars {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.6rem;
	}
	.lbl {
		display: block;
		font-size: 0.9rem;
		margin-bottom: 0.15rem;
	}
	.strong {
		font-weight: 700;
	}
	.row {
		display: grid;
		grid-template-columns: 1fr max-content;
		gap: 0.75rem;
		align-items: center;
	}
	svg {
		width: 100%;
		height: 1.5rem;
		display: block;
		border-radius: var(--r-sm);
	}
	/* Смужки «виростають» зліва направо при появі */
	@media (prefers-reduced-motion: no-preference) {
		.grow {
			transform-box: fill-box;
			transform-origin: left center;
			animation: grow-x var(--dur-slow) var(--ease-emph) both;
			animation-delay: calc(var(--i, 0) * 140ms + 200ms);
		}
		@keyframes grow-x {
			from {
				transform: scaleX(0);
			}
		}
	}
	.val {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
		white-space: nowrap;
	}
</style>
