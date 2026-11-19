<script lang="ts">
	// SVG-графік на 12 місяців: споживання будівлі проти генерації СЕС (власне використання + надлишок)
	import type { SolarMonth } from './api.ts';
	import { num, niceMax, MONTHS, MONTHS_FULL } from './format.ts';

	let { months }: { months: SolarMonth[] } = $props();

	// Стовпчики «виростають» при появі й плавно змінюються разом із повзунком (CSS-перехід y/height).
	let grown = $state(false);
	let settled = $state(false); // після першої появи — без «драбинки», щоб повзунок відгукувався одразу
	$effect(() => {
		const r = requestAnimationFrame(() => requestAnimationFrame(() => (grown = true)));
		const t = setTimeout(() => (settled = true), 1200);
		return () => {
			cancelAnimationFrame(r);
			clearTimeout(t);
		};
	});
	const uid = $props.id();

	const W = 760;
	const H = 320;
	const PAD = { l: 64, r: 12, t: 16, b: 40 };
	const plotW = W - PAD.l - PAD.r;
	const plotH = H - PAD.t - PAD.b;

	const sorted = $derived([...months].sort((a, b) => a.month - b.month));
	const max = $derived(
		niceMax(Math.max(1, ...sorted.map((m) => Math.max(m.cons_kwh, m.self_kwh + m.surplus_kwh))))
	);
	const ticks = $derived([0, 0.25, 0.5, 0.75, 1].map((f) => f * max));
	const slot = $derived(plotW / Math.max(sorted.length, 1));
	const bw = $derived(Math.min(22, slot * 0.34));

	function y(v: number): number {
		return PAD.t + plotH - ((grown ? v : 0) / max) * plotH;
	}
	function h(v: number): number {
		return ((grown ? v : 0) / max) * plotH;
	}
	function yt(v: number): number {
		return PAD.t + plotH - (v / max) * plotH;
	}
</script>

<figure>
	<div class="legend" aria-hidden="true">
		<span><i class="sw cons"></i> Споживання будівлі</span>
		<span><i class="sw self"></i> Генерація, використана самою будівлею</span>
		<span><i class="sw surplus"></i> Надлишок генерації (пропадає)</span>
	</div>
	<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="{uid}-t {uid}-d">
		<title id="{uid}-t">Помісячна генерація СЕС і споживання електроенергії будівлею, кВт·год</title>
		<desc id="{uid}-d">
			{sorted
				.map(
					(m) =>
						`${MONTHS_FULL[m.month - 1]}: споживання ${num(m.cons_kwh)}, використано власної генерації ${num(m.self_kwh)}, надлишок ${num(m.surplus_kwh)} кВт·год`
				)
				.join('; ')}
		</desc>
		<defs>
			<!-- Штрихування надлишку: колір не єдиний носій сенсу -->
			<pattern id="{uid}-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
				<rect width="6" height="6" fill="var(--sol-surplus)" />
				<line x1="0" y1="0" x2="0" y2="6" stroke="#fff" stroke-width="2" />
			</pattern>
		</defs>
		{#each ticks as t (t)}
			<line x1={PAD.l} x2={W - PAD.r} y1={yt(t)} y2={yt(t)} stroke="#e1e6ec" />
			<text x={PAD.l - 8} y={yt(t)} text-anchor="end" dominant-baseline="middle" class="axis">{num(t)}</text>
		{/each}
		<text x="12" y={PAD.t + plotH / 2} transform="rotate(-90 12 {PAD.t + plotH / 2})" text-anchor="middle" class="axis">кВт·год</text>
		{#each sorted as m, i (m.month)}
			{@const cx = PAD.l + slot * i + slot / 2}
			<g style:--d="{settled ? 0 : i * 35}ms">
				<title>{MONTHS_FULL[m.month - 1]}: споживання {num(m.cons_kwh)} кВт·год; генерація {num(m.gen_kwh)} кВт·год (власне {num(m.self_kwh)}, надлишок {num(m.surplus_kwh)})</title>
				<rect class="bar" x={cx - bw - 1} width={bw} style:y="{y(m.cons_kwh)}px" style:height="{h(m.cons_kwh)}px" fill="var(--sol-cons)" />
				<rect class="bar" x={cx + 1} width={bw} style:y="{y(m.self_kwh)}px" style:height="{h(m.self_kwh)}px" fill="var(--sol-self)" />
				<rect class="bar" x={cx + 1} width={bw} style:y="{y(m.self_kwh + m.surplus_kwh)}px" style:height="{h(m.surplus_kwh)}px" fill="url(#{uid}-hatch)" />
			</g>
			<text x={cx} y={H - PAD.b + 18} text-anchor="middle" class="axis">{MONTHS[m.month - 1]}</text>
		{/each}
		<line x1={PAD.l} x2={W - PAD.r} y1={yt(0)} y2={yt(0)} stroke="#6b7684" />
	</svg>
	<figcaption class="muted small">
		Ліва колонка кожного місяця — споживання, права — генерація станції: суцільна частина
		використовується будівлею, заштрихована — надлишок, який зараз не можна продати.
	</figcaption>
</figure>

<style>
	figure {
		margin: 0;
	}
	svg {
		width: 100%;
		height: auto;
		display: block;
	}
	@media (prefers-reduced-motion: no-preference) {
		.bar {
			transition:
				y 0.45s cubic-bezier(0.22, 1, 0.36, 1) var(--d, 0ms),
				height 0.45s cubic-bezier(0.22, 1, 0.36, 1) var(--d, 0ms);
		}
	}
	.axis {
		font-size: 12px;
		fill: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.25rem;
		font-size: 0.875rem;
		margin-bottom: 0.5rem;
	}
	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}
	.sw {
		display: inline-block;
		width: 14px;
		height: 14px;
		border-radius: 2px;
	}
	.sw.cons {
		background: var(--sol-cons);
	}
	.sw.self {
		background: var(--sol-self);
	}
	.sw.surplus {
		background: repeating-linear-gradient(45deg, var(--sol-surplus) 0 4px, #fff 4px 6px);
		border: 1px solid var(--sol-surplus);
	}
</style>
