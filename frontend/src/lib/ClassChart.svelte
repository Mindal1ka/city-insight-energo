<script lang="ts">
	// Горизонтальні SVG-бари розподілу будівель за умовними класами A–G.
	// Підписи — звичайний HTML-текст, щоб не зменшувалися разом із графіком на вузьких екранах.
	import { CLASSES } from './classes.ts';
	import { num } from './format.ts';

	let { counts, title }: { counts: Record<string, number>; title: string } = $props();

	const rows = $derived(CLASSES.map((c) => ({ ...c, n: counts[c.letter] ?? 0 })));
	const total = $derived(rows.reduce((s, r) => s + r.n, 0));
	const max = $derived(Math.max(1, ...rows.map((r) => r.n)));
</script>

<figure aria-labelledby="cls-chart-cap">
	<ul class="bars">
		{#each rows as r (r.letter)}
			<li>
				<span class="lbl"><b>{r.letter}</b> {r.text}</span>
				<svg viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
					<rect x="0" y="0" width="100" height="10" fill="#eef2f6" />
					<rect x="0" y="0" width={(r.n / max) * 100} height="10" fill="var(--cls-{r.letter})" />
				</svg>
				<span class="val">{num(r.n)} <span class="muted">· {total ? Math.round((r.n / total) * 100) : 0} %</span></span>
			</li>
		{/each}
	</ul>
	<figcaption id="cls-chart-cap" class="muted small">
		{title}. Усього з класом: {num(total)} будівель. Клас — умовна оцінка: відношення питомого
		споживання (кВт·год/м²) до медіани своєї категорії.
	</figcaption>
</figure>

<style>
	figure {
		margin: 0;
	}
	.bars {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: max-content 1fr max-content;
		gap: 0.5rem 0.75rem;
		align-items: center;
	}
	.bars li {
		display: contents;
	}
	.lbl {
		font-size: 0.9rem;
	}
	.lbl b {
		display: inline-block;
		width: 1.1em;
	}
	svg {
		width: 100%;
		height: 1.4rem;
		display: block;
		border-radius: 3px;
	}
	.val {
		font-size: 0.9rem;
		font-variant-numeric: tabular-nums;
		text-align: right;
		white-space: nowrap;
	}
	figcaption {
		margin-top: 0.75rem;
	}
	@media (max-width: 520px) {
		.bars {
			grid-template-columns: 1fr max-content;
		}
		.lbl {
			grid-column: 1 / -1;
			margin-bottom: -0.3rem;
		}
	}
</style>
