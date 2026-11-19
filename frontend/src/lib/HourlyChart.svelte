<script lang="ts">
	// Погодинний графік за день: генерація СЕС (стовпчики), споживання (лінія), заряд акумулятора (лінія, права вісь).
	// Минулі години — суцільні, майбутні — світліші й пунктиром (прогноз). Вертикальна мітка «зараз».
	import type { SiteHour } from './api.ts';
	import { num, hh } from './format.ts';
	import { isReduced } from './motion.ts';

	let {
		hours,
		nowHour = null,
		nowMinute = 0,
		peakHour = null
	}: {
		hours: SiteHour[];
		nowHour?: number | null;
		nowMinute?: number;
		peakHour?: number | null;
	} = $props();

	// Ширина контейнера → viewBox у справжніх пікселях, щоб підписи не дрібнішали на планшеті
	let cw = $state(1000);
	const W = $derived(Math.max(520, Math.round(cw) || 1000));
	const H = $derived(W < 760 ? 300 : 360);
	const PAD = { l: 58, r: 58, t: 34, b: 38 };
	const plotW = $derived(W - PAD.l - PAD.r);
	const plotH = $derived(H - PAD.t - PAD.b);
	const slot = $derived(plotW / 24);

	const data = $derived([...hours].sort((a, b) => a.hour - b.hour));
	const hasGen = $derived(data.some((d) => d.gen_kwh > 0));
	const hasSoc = $derived(data.some((d) => d.soc_pct !== null));
	// «Гарний» крок шкали: 1, 2, 2,5 або 5 × 10ⁿ, приблизно 4–5 поділок
	const scale = $derived.by(() => {
		const top = Math.max(1, ...data.map((d) => Math.max(d.gen_kwh, d.cons_kwh))) * 1.1;
		const raw = top / 4;
		const p = Math.pow(10, Math.floor(Math.log10(raw)));
		const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw) ?? 10 * p;
		const n = Math.ceil(top / step);
		return { max: n * step, ticks: Array.from({ length: n + 1 }, (_, i) => i * step) };
	});
	const max = $derived(scale.max);
	const ticks = $derived(scale.ticks);
	const bw = $derived(slot * 0.56);

	const cx = (h: number) => PAD.l + slot * h + slot / 2;
	const y = (v: number) => PAD.t + plotH - (v / max) * plotH;
	const ys = (p: number) => PAD.t + plotH - (p / 100) * plotH;

	function line(pts: [number, number][]): string {
		return pts.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`).join('');
	}

	// Межа «факт / прогноз»: перша година з forecast = true
	const firstFc = $derived(data.findIndex((d) => d.forecast));
	const split = $derived(firstFc === -1 ? data.length : firstFc);
	const pastPts = $derived(data.slice(0, split));
	// Прогнозна частина починається з останньої фактичної точки, щоб лінія була неперервною
	const fcPts = $derived(data.slice(Math.max(0, split - 1)));

	const consPast = $derived(line(pastPts.map((d) => [cx(d.hour), y(d.cons_kwh)])));
	const consFc = $derived(split < data.length ? line(fcPts.map((d) => [cx(d.hour), y(d.cons_kwh)])) : '');
	const consArea = $derived(
		data.length
			? line(data.map((d) => [cx(d.hour), y(d.cons_kwh)])) +
					`L${cx(data[data.length - 1].hour)},${y(0)}L${cx(data[0].hour)},${y(0)}Z`
			: ''
	);
	const socPast = $derived(
		line(pastPts.filter((d) => d.soc_pct !== null).map((d) => [cx(d.hour), ys(d.soc_pct!)]))
	);
	const socFc = $derived(
		split < data.length
			? line(fcPts.filter((d) => d.soc_pct !== null).map((d) => [cx(d.hour), ys(d.soc_pct!)]))
			: ''
	);

	// Позиція мітки «зараз»: початок поточної години + хвилини
	const nowX = $derived(
		nowHour === null ? null : PAD.l + slot * (nowHour + Math.min(59, nowMinute) / 60)
	);
	const peak = $derived(peakHour === null ? null : (data.find((d) => d.hour === peakHour) ?? null));

	// Графік «малюється», коли з'являється на екрані: стовпчики ростуть, лінії прокреслюються
	let seen = $state(false);
	function onView(node: HTMLElement) {
		if (isReduced() || typeof IntersectionObserver === 'undefined') {
			seen = true;
			return;
		}
		const io = new IntersectionObserver(
			(es) => {
				if (es.some((e) => e.isIntersecting)) {
					seen = true;
					io.disconnect();
				}
			},
			{ threshold: 0.25 }
		);
		io.observe(node);
		return () => io.disconnect();
	}

	// Інтерактивна підказка: миша або стрілки клавіатури
	let active = $state<number | null>(null);
	const act = $derived(active === null ? null : (data[active] ?? null));

	function onKey(e: KeyboardEvent) {
		if (!data.length) return;
		if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
			e.preventDefault();
			const start = active ?? (nowHour ?? 0);
			const d = e.key === 'ArrowRight' ? 1 : -1;
			active = Math.max(0, Math.min(data.length - 1, start + (active === null ? 0 : d)));
		} else if (e.key === 'Home') {
			active = 0;
		} else if (e.key === 'End') {
			active = data.length - 1;
		} else if (e.key === 'Escape') {
			active = null;
		}
	}

	function hourText(d: SiteHour): string {
		return (
			`${hh(d.hour)}${d.forecast ? ', прогноз' : ''}: ` +
			(hasGen ? `генерація ${num(d.gen_kwh, 1)}, ` : '') +
			`споживання ${num(d.cons_kwh, 1)} кВт·год` +
			(d.soc_pct !== null ? `, заряд ${num(d.soc_pct, 0)} %` : '')
		);
	}

	const summary = $derived.by(() => {
		const g = data.reduce((a, d) => a + d.gen_kwh, 0);
		const c = data.reduce((a, d) => a + d.cons_kwh, 0);
		return `За добу: генерація ${num(g, 1)} кВт·год, споживання ${num(c, 1)} кВт·год.` +
			(peak ? ` Пік споживання ${num(peak.cons_kwh, 1)} кВт о ${hh(peak.hour)}.` : '') +
			(nowHour !== null ? ` Після ${hh(nowHour)} — прогноз.` : '');
	});
</script>

<figure class="hc">
	<div class="legend">
		{#if hasGen}<span><i class="sw gen" aria-hidden="true"></i>Генерація СЕС</span>{/if}
		<span><i class="sw cons" aria-hidden="true"></i>Споживання</span>
		{#if hasSoc}<span><i class="sw soc" aria-hidden="true"></i>Заряд акумулятора, % (права шкала)</span>{/if}
		<span class="fc-key"><i class="sw dash" aria-hidden="true"></i>світліше й пунктиром — прогноз</span>
	</div>

	<div class="plot" class:seen bind:clientWidth={cw} {@attach onView}>
		<svg
			viewBox="0 0 {W} {H}"
			role="slider"
			aria-label="Погодинний графік генерації та споживання за добу. {summary} Стрілками вліво-вправо можна переглянути значення кожної години."
			aria-valuemin={0}
			aria-valuemax={23}
			aria-valuenow={act?.hour ?? nowHour ?? 0}
			aria-valuetext={act ? hourText(act) : 'година не обрана'}
			tabindex="0"
			onkeydown={onKey}
			onblur={() => (active = null)}
			onmouseleave={() => (active = null)}
		>
			<defs>
				<linearGradient id="hc-gen" x1="0" x2="0" y1="0" y2="1">
					<stop offset="0" stop-color="#f7b23b" />
					<stop offset="1" stop-color="#ef9a12" />
				</linearGradient>
				<linearGradient id="hc-cons" x1="0" x2="0" y1="0" y2="1">
					<stop offset="0" stop-color="#1f4f84" stop-opacity="0.16" />
					<stop offset="1" stop-color="#1f4f84" stop-opacity="0.01" />
				</linearGradient>
				<pattern id="hc-fc" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
					<rect width="7" height="7" fill="#fde7bf" />
					<line x1="0" y1="0" x2="0" y2="7" stroke="#f3c26b" stroke-width="2.5" />
				</pattern>
			</defs>

			<!-- Зона прогнозу -->
			{#if nowX !== null}
				<rect x={nowX} y={PAD.t} width={W - PAD.r - nowX} height={plotH} fill="#f3f6fa" />
				<text x={W - PAD.r - 8} y={PAD.t + 16} text-anchor="end" class="zone">прогноз</text>
			{/if}

			<!-- Сітка й ліва шкала -->
			{#each ticks as t, i (i)}
				<line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke={i === 0 ? '#c3ccd7' : '#e6ebf1'} />
				<text x={PAD.l - 10} y={y(t)} text-anchor="end" dominant-baseline="middle" class="axis">{num(t, t % 1 ? 1 : 0)}</text>
			{/each}
			<text x={PAD.l - 10} y={PAD.t - 14} text-anchor="end" class="axis unit">кВт·год</text>

			<!-- Права шкала заряду -->
			{#if hasSoc}
				{#each [0, 50, 100] as p (p)}
					<text x={W - PAD.r + 10} y={ys(p)} dominant-baseline="middle" class="axis soc-axis">{p} %</text>
				{/each}
				<text x={W - PAD.r + 10} y={PAD.t - 14} class="axis unit soc-axis">заряд</text>
			{/if}

			<!-- Підписи годин -->
			{#each data as d (d.hour)}
				{#if d.hour % 3 === 0}
					<text x={cx(d.hour)} y={H - PAD.b + 22} text-anchor="middle" class="axis">{hh(d.hour)}</text>
				{/if}
			{/each}

			<!-- Площа під споживанням -->
			<path d={consArea} fill="url(#hc-cons)" class="fade" />

			<!-- Стовпчики генерації -->
			{#if hasGen}
				{#each data as d (d.hour)}
					{#if d.gen_kwh > 0}
						{@const top = y(d.gen_kwh)}
						{@const h = Math.max(1.5, y(0) - top)}
						<rect
							class="bar"
							class:fc={d.forecast}
							style="--i: {d.hour}"
							x={cx(d.hour) - bw / 2}
							y={top}
							width={bw}
							height={h}
							rx={Math.min(5, h / 2)}
							fill={d.forecast ? 'url(#hc-fc)' : 'url(#hc-gen)'}
							stroke={d.forecast ? '#d99520' : 'none'}
							stroke-dasharray={d.forecast ? '4 3' : undefined}
						/>
					{/if}
				{/each}
			{/if}

			<!-- Лінія споживання -->
			<path d={consPast} class="cons-line draw" pathLength="1" />
			{#if consFc}<path d={consFc} class="cons-line fc-line fade late" />{/if}

			<!-- Лінія заряду -->
			{#if hasSoc}
				<path d={socPast} class="soc-line draw" pathLength="1" />
				{#if socFc}<path d={socFc} class="soc-line fc-line fade late" />{/if}
			{/if}

			<!-- Пік споживання -->
			{#if peak && peak.cons_kwh > 0}
				<g class="fade late">
				<circle cx={cx(peak.hour)} cy={y(peak.cons_kwh)} r="5.5" fill="#fff" stroke="#1f4f84" stroke-width="2.5" />
				<text x={cx(peak.hour)} y={y(peak.cons_kwh) - 12} text-anchor="middle" class="peak">
					пік {num(peak.cons_kwh, 1)} кВт
				</text>
				</g>
			{/if}

			<!-- Мітка «зараз» -->
			{#if nowX !== null}
				<line x1={nowX} x2={nowX} y1={PAD.t - 6} y2={PAD.t + plotH} class="now-line" />
				<g transform="translate({nowX}, {PAD.t - 16})">
					<rect x="-30" y="-12" width="60" height="22" rx="11" fill="#0f2f52" />
					<text x="0" y="0" text-anchor="middle" dominant-baseline="middle" class="now-text">зараз</text>
				</g>
			{/if}

			<!-- Активна година -->
			{#if act}
				<rect x={PAD.l + slot * act.hour} y={PAD.t} width={slot} height={plotH} class="hover-band" />
				<circle cx={cx(act.hour)} cy={y(act.cons_kwh)} r="4.5" fill="#1f4f84" />
				{#if act.soc_pct !== null}<circle cx={cx(act.hour)} cy={ys(act.soc_pct)} r="4" fill="#0f766e" />{/if}
			{/if}

			<!-- Зони наведення -->
			{#each data as d, i (d.hour)}
				<rect
					x={PAD.l + slot * d.hour}
					y={PAD.t}
					width={slot}
					height={plotH}
					fill="transparent"
					role="presentation"
					onmouseenter={() => (active = i)}
				/>
			{/each}
		</svg>

		{#if act}
			{@const left = ((cx(act.hour)) / W) * 100}
			<div
				class="tip"
				style="left: {left}%; transform: translateX({left > 70 ? '-100%' : left < 30 ? '0' : '-50%'})"
				aria-hidden="true"
			>
				<p class="tip-h">{hh(act.hour)}–{hh((act.hour + 1) % 24)} {#if act.forecast}<span class="tip-fc">прогноз</span>{/if}</p>
				{#if hasGen}<p><i class="sw gen" aria-hidden="true"></i>Генерація <b class="tnum">{num(act.gen_kwh, 1)}</b> кВт·год</p>{/if}
				<p><i class="sw cons" aria-hidden="true"></i>Споживання <b class="tnum">{num(act.cons_kwh, 1)}</b> кВт·год</p>
				{#if act.soc_pct !== null}<p><i class="sw soc" aria-hidden="true"></i>Заряд <b class="tnum">{num(act.soc_pct, 0)}</b> %</p>{/if}
			</div>
		{/if}
	</div>
	<figcaption class="visually-hidden">{summary}</figcaption>
</figure>

<style>
	.hc {
		margin: 0;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.25rem;
		font-size: 0.875rem;
		color: #3d4857;
		margin-bottom: 0.5rem;
	}
	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
	}
	.fc-key {
		color: var(--muted);
	}
	.sw {
		display: inline-block;
		width: 0.95rem;
		height: 0.95rem;
		border-radius: 4px;
		flex: none;
	}
	.sw.gen {
		background: linear-gradient(#f7b23b, #ef9a12);
	}
	.sw.cons {
		height: 3px;
		border-radius: 2px;
		background: #1f4f84;
	}
	.sw.soc {
		height: 3px;
		border-radius: 2px;
		background: #0f766e;
	}
	.sw.dash {
		height: 0;
		border-top: 3px dashed #7d8796;
		border-radius: 0;
	}
	.plot {
		position: relative;
	}
	svg {
		display: block;
		width: 100%;
		height: auto;
		border-radius: 8px;
		cursor: crosshair;
	}
	svg:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: 4px;
		box-shadow: none;
	}
	.axis {
		font-size: 13px;
		fill: #5b6676;
		font-variant-numeric: tabular-nums;
	}
	.unit {
		font-size: 12px;
		font-weight: 600;
	}
	.soc-axis {
		fill: #0f766e;
	}
	.zone {
		font-size: 12px;
		font-weight: 600;
		fill: #6b7686;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.cons-line {
		fill: none;
		stroke: #1f4f84;
		stroke-width: 3;
		stroke-linejoin: round;
		stroke-linecap: round;
	}
	.soc-line {
		fill: none;
		stroke: #0f766e;
		stroke-width: 2.25;
		stroke-linejoin: round;
		stroke-linecap: round;
	}
	.fc-line {
		stroke-dasharray: 7 6;
		opacity: 0.6;
	}
	.bar {
		transition: opacity 0.2s;
	}
	@media (prefers-reduced-motion: no-preference) {
		.bar {
			transform-box: fill-box;
			transform-origin: 50% 100%;
			transition:
				transform 0.7s cubic-bezier(0.22, 1, 0.36, 1) calc(var(--i, 0) * 30ms),
				opacity 0.2s;
		}
		.plot:not(.seen) .bar {
			transform: scaleY(0);
		}
		.draw {
			stroke-dasharray: 1;
			stroke-dashoffset: 0;
			transition: stroke-dashoffset 1.3s cubic-bezier(0.45, 0, 0.2, 1) 0.15s;
		}
		.plot:not(.seen) .draw {
			stroke-dashoffset: 1;
		}
		.fade {
			transition: opacity 0.6s ease 0.3s;
		}
		.fade.late {
			transition-delay: 1.1s;
		}
		.plot:not(.seen) .fade {
			opacity: 0;
		}
	}
	.peak {
		font-size: 13px;
		font-weight: 700;
		fill: #1f4f84;
		paint-order: stroke;
		stroke: #fff;
		stroke-width: 6px;
		stroke-linejoin: round;
	}
	.now-line {
		stroke: #0f2f52;
		stroke-width: 2;
	}
	.now-text {
		font-size: 12.5px;
		font-weight: 700;
		fill: #fff;
	}
	.hover-band {
		fill: rgba(15, 47, 82, 0.06);
	}
	.tip {
		position: absolute;
		top: 2.25rem;
		pointer-events: none;
		background: #fff;
		border: 1px solid #dbe2ea;
		border-radius: 12px;
		box-shadow: var(--shadow-lg);
		padding: 0.6rem 0.8rem;
		font-size: 0.875rem;
		min-width: 13rem;
		z-index: 5;
	}
	.tip p {
		margin: 0.1rem 0;
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}
	.tip b {
		margin-left: auto;
	}
	.tip-h {
		font-weight: 700;
		margin-bottom: 0.3rem !important;
	}
	.tip-fc {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--muted);
		border: 1px dashed var(--line-strong);
		border-radius: 999px;
		padding: 0 0.45rem;
	}
</style>
