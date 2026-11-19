<script lang="ts">
	// Картка «Сонце завтра»: скільки виробить станція за прогнозом погоди (Open-Meteo × модель PVGIS).
	// kw — потужність станції; null → показуємо міський рівень «на 1 кВт панелей».
	// compact — вузький варіант без перемикача днів (для бокових панелей і списків).
	import { getForecast, ratioOf, type Forecast, type ForecastDay } from './api-forecast.ts';
	import { errMessage } from './api.ts';
	import { num } from './format.ts';
	import { fadeUp } from './motion.ts';
	import Disclosure from './Disclosure.svelte';

	let { kw = null, compact = false }: { kw?: number | null; compact?: boolean } = $props();

	let data = $state<Forecast | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let picked = $state<string | null>(null);

	async function load(force = false) {
		loading = true;
		error = null;
		try {
			data = await getForecast(force);
		} catch (e) {
			data = null;
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	load();

	const uid = $props.id();
	const days = $derived(data?.days ?? []);
	const day = $derived<ForecastDay | null>(
		days.find((d) => d.date === picked) ?? days.find((d) => d.label === 'завтра') ?? days[0] ?? null
	);
	const size = $derived(kw !== null && kw !== undefined && kw > 0 ? kw : null);
	const mult = $derived(size ?? 1);
	const kwh = $derived(day ? day.gen_kwh_per_kwp_day * mult : null);
	const normalKwh = $derived(day ? day.pvgis_avg_kwh_per_kwp_day * mult : null);
	const ratio = $derived(day ? ratioOf(day) : null);
	const ratioPct = $derived(ratio !== null ? Math.round(ratio * 100) : null);

	function digits(v: number | null): number {
		if (v === null) return 0;
		return v < 10 ? 1 : 0;
	}

	type Tone = 'sun' | 'part' | 'cloud';
	function tone(w: string | undefined): Tone {
		if (w === 'сонячно') return 'sun';
		if (w === 'похмуро') return 'cloud';
		return 'part';
	}
	const t = $derived(tone(day?.weather));

	const verdict = $derived.by(() => {
		if (ratio === null) return '';
		if (ratio >= 1.15) return 'краще, ніж зазвичай цієї пори';
		if (ratio >= 0.85) return 'як зазвичай цієї пори';
		if (ratio >= 0.5) return 'менше, ніж зазвичай';
		return 'значно менше, ніж зазвичай';
	});

	// Проста відповідь «мало / середньо / багато» — відносно звичайного дня цієї пори року
	const level = $derived.by(() => {
		if (ratio === null) return { key: 'mid', word: 'невідомо скільки' };
		if (ratio < 0.6) return { key: 'low', word: 'мало' };
		if (ratio < 1.1) return { key: 'mid', word: 'середньо' };
		return { key: 'high', word: 'багато' };
	});
	const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);
	const MONTHS_GEN = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'];
	const monthGen = $derived(day ? (MONTHS_GEN[Number(day.date.slice(5, 7)) - 1] ?? '') : '');

	// ——— Погодинний міні-графік ———
	const SW = $derived(compact ? 240 : 320);
	const SH = $derived(compact ? 56 : 76);
	const PB = 16; // місце під підписи годин
	const scaleMax = $derived(
		Math.max(0.05, ...days.flatMap((d) => d.hourly.map((h) => h.gen_kwh_per_kwp))) * mult
	);
	const range = $derived.by(() => {
		const all = days.flatMap((d) => d.hourly.filter((h) => h.gen_kwh_per_kwp > 0.001).map((h) => h.hour));
		if (!all.length) return { a: 6, b: 18 };
		return { a: Math.max(0, Math.min(...all) - 1), b: Math.min(23, Math.max(...all) + 1) };
	});
	const pts = $derived.by(() => {
		if (!day) return [] as { x: number; y: number; v: number; hour: number }[];
		const { a, b } = range;
		const span = Math.max(1, b - a);
		return day.hourly
			.filter((h) => h.hour >= a && h.hour <= b)
			.sort((p, q) => p.hour - q.hour)
			.map((h) => {
				const v = h.gen_kwh_per_kwp * mult;
				return {
					x: ((h.hour - a) / span) * SW,
					y: 4 + (SH - PB - 4) * (1 - v / scaleMax),
					v,
					hour: h.hour
				};
			});
	});
	const line = $derived(pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '));
	const area = $derived(
		pts.length ? `${line} L${pts[pts.length - 1].x.toFixed(1)},${SH - PB} L${pts[0].x.toFixed(1)},${SH - PB} Z` : ''
	);
	const peak = $derived(pts.reduce((m, p) => (p.v > m.v ? p : m), { x: 0, y: SH, v: 0, hour: 0 }));
	const hourTicks = $derived.by(() => {
		const { a, b } = range;
		const span = Math.max(1, b - a);
		const mid = Math.round((a + b) / 2);
		return [a, mid, b].map((h) => ({ h, x: ((h - a) / span) * SW }));
	});

	const sparkDesc = $derived(
		pts.length
			? `Погодинно: ${pts
					.filter((p) => p.v > 0.001)
					.map((p) => `${p.hour}:00 — ${num(p.v, size ? 1 : 2)} кВт·год`)
					.join('; ')}`
			: 'Немає погодинних даних'
	);

	// ——— Свіжість ———
	const fresh = $derived.by(() => {
		const iso = data?.fetched_at;
		if (!iso) return '';
		const d = new Date(iso);
		if (Number.isNaN(d.getTime())) return '';
		const time = d.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
		const today = new Date().toDateString() === d.toDateString();
		return today
			? `оновлено ${time}`
			: `оновлено ${d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' })}, ${time}`;
	});
	const dayDate = $derived(
		day ? new Date(day.date + 'T12:00:00').toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' }) : ''
	);
</script>

<section class="fc" class:compact aria-labelledby="{uid}-h" aria-busy={loading}>
	<header class="fc-head">
		<h3 id="{uid}-h">
			<span class="sunmark" aria-hidden="true"></span>
			Сонце {day?.label ?? 'завтра'}
			{#if dayDate}<span class="fc-date">· {dayDate}</span>{/if}
		</h3>
		{#if !compact && days.length > 1}
			<div class="fc-days" role="group" aria-label="День прогнозу">
				{#each days as d (d.date)}
					<button type="button" aria-pressed={day?.date === d.date} onclick={() => (picked = d.date)}>{d.label}</button>
				{/each}
			</div>
		{/if}
	</header>

	{#if loading && !data}
		<div class="fc-skel" aria-hidden="true"><i></i><i></i><i></i></div>
		<p class="visually-hidden" role="status">Завантажуємо прогноз погоди…</p>
	{:else if error}
		<div class="fc-err" role="status">
			<p><strong>Прогноз зараз недоступний.</strong> {error}</p>
			<button type="button" class="btn btn-secondary" onclick={() => load(true)}>Спробувати ще раз</button>
		</div>
	{:else if day}
		{#key day.date}
			<div class="fc-main" in:fadeUp={{ y: 6 }}>
				<div class="wx wx-{t}" aria-hidden="true">
					<svg viewBox="0 0 48 48" width={compact ? 44 : 56} height={compact ? 44 : 56}>
						{#if t !== 'cloud'}
							<g class="sun-g" transform={t === 'part' ? 'translate(-5 -5)' : ''}>
								<g class="rays">
									{#each [0, 45, 90, 135, 180, 225, 270, 315] as a (a)}
										<line x1="24" y1="9" x2="24" y2="4.5" transform="rotate({a} 24 24)" />
									{/each}
								</g>
								<circle cx="24" cy="24" r="8.5" />
							</g>
						{/if}
						{#if t !== 'sun'}
							<path
								class="cloud-g"
								d={t === 'cloud'
									? 'M13 36h23a7 7 0 0 0 0-14 10 10 0 0 0-19-2 8 8 0 0 0-4 16z'
									: 'M18 40h20a6 6 0 0 0 0-12 8.5 8.5 0 0 0-16.2-1.6A6.8 6.8 0 0 0 18 40z'}
							/>
						{/if}
					</svg>
				</div>
				<div class="fc-num">
					<p class="fc-say">
						{cap(day.label)} сонця буде <strong class="lvl lvl-{level.key}">{level.word}</strong>
					</p>
					<p class="fc-kwh">
						<span class="big-num">≈ {num(kwh, digits(kwh))}</span>
						<span class="unit-s">кВт·год</span>
						<span class="fc-sub">
							{#if size}виробить станція {num(size, size < 10 ? 1 : 0)} кВт за день{:else}за день з кожного 1 кВт панелей{/if}
						</span>
					</p>
				</div>
			</div>

			{#if pts.length > 1}
				<figure class="spark">
					<svg viewBox="0 0 {SW} {SH}" width="100%" preserveAspectRatio="none" role="img" aria-labelledby="{uid}-st {uid}-sd">
						<title id="{uid}-st">Генерація по годинах, {day.label}</title>
						<desc id="{uid}-sd">{sparkDesc}</desc>
						<line x1="0" x2={SW} y1={SH - PB} y2={SH - PB} class="base" />
						<g class="draw">
							<path d={area} class="area wx-{t}" />
							<path d={line} class="ln" vector-effect="non-scaling-stroke" />
						</g>
						{#if peak.v > 0}
							<circle cx={peak.x} cy={peak.y} r="3" class="pk" vector-effect="non-scaling-stroke" />
						{/if}
					</svg>
					<div class="ticks" aria-hidden="true">
						{#each hourTicks as tk (tk.h)}
							<span style:left="{(tk.x / SW) * 100}%">{tk.h}:00</span>
						{/each}
					</div>
				</figure>
			{/if}
		{/key}

		{#if data?.stale || data?.demo}
			<p class="fc-flags">
				{#if data?.demo}<span class="pill pill-warn">демо</span> Прогноз ще не підключено — показано приклад{/if}
				{#if data?.stale}<span class="pill pill-warn" role="note">⚠ дані застарілі: показано останній збережений прогноз</span>{/if}
			</p>
		{/if}

		{#if !compact}
			<Disclosure summary="Детальніше про прогноз">
				{#if ratioPct !== null}
					<div class="norm">
						<div class="norm-txt">
							<strong>{ratioPct} % від звичайного</strong>
							<span class="muted">— {verdict}</span>
						</div>
						<div class="norm-bar" role="meter" aria-valuemin="0" aria-valuemax="200" aria-valuenow={ratioPct} aria-label="Прогноз у відсотках від багаторічної норми">
							<span class="norm-fill wx-{t}" style:width="{Math.min(100, ratioPct / 2)}%"></span>
							<span class="norm-100" title="норма"></span>
						</div>
						<p class="norm-legend muted">
							Риска — звичайний день {monthGen}: ≈ {num(normalKwh, digits(normalKwh))} кВт·год (середнє PVGIS).
						</p>
					</div>
				{/if}
				<ul class="fc-facts">
					<li>Погода: {day.weather}{#if day.sun_hours !== null && day.sun_hours !== undefined}, сонця ≈ {num(day.sun_hours, 0)} год{/if}</li>
					{#if peak.v > 0}<li>Найбільше — о {peak.hour}:00, ≈ {num(peak.v, size ? 1 : 2)} кВт·год</li>{/if}
					<li>Джерело: {data?.source ?? 'Open-Meteo'}{fresh ? `, ${fresh}` : ''} × модель PVGIS</li>
				</ul>
			</Disclosure>
		{:else}
			<p class="fc-foot">{data?.source ?? 'Open-Meteo'}{fresh ? `, ${fresh}` : ''}</p>
		{/if}
	{:else}
		<p class="muted">Прогнозу на найближчі дні немає.</p>
	{/if}
</section>

<style>
	.fc {
		background: linear-gradient(180deg, #fffaf0 0%, var(--surface) 70%);
		border: 1px solid #efe2c4;
		border-radius: var(--radius-lg);
		padding: 1.1rem 1.25rem 1rem;
		box-shadow: var(--shadow);
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
		min-width: 0;
	}
	.fc.compact {
		padding: 0.85rem 1rem 0.8rem;
		gap: 0.6rem;
	}
	.fc-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 0.75rem;
	}
	h3 {
		margin: 0;
		font-size: 1.05rem;
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}
	.fc-date {
		font-weight: 500;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.sunmark {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--sun);
		box-shadow: 0 0 0 3px var(--sun-soft);
	}
	.fc-days {
		display: inline-flex;
		gap: 3px;
		padding: 3px;
		border-radius: 10px;
		background: #f1ece0;
	}
	.fc-days button {
		font: inherit;
		font-size: 0.8125rem;
		font-weight: 600;
		border: 0;
		background: transparent;
		color: #4a3a1a;
		padding: 0.3rem 0.6rem;
		border-radius: 7px;
		cursor: pointer;
	}
	.fc-days button:hover {
		background: rgba(255, 255, 255, 0.7);
	}
	.fc-days button[aria-pressed='true'] {
		background: #fff;
		color: var(--text);
		box-shadow: 0 1px 2px rgba(16, 24, 40, 0.12);
	}
	.fc-main {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	.wx {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.15rem;
		min-width: 4.5rem;
	}
	.sun-g circle {
		fill: var(--sun);
		stroke: var(--sun-strong);
		stroke-width: 1.5;
	}
	.sun-g line {
		stroke: var(--sun-strong);
		stroke-width: 2.4;
		stroke-linecap: round;
	}
	.cloud-g {
		fill: #e6ebf1;
		stroke: #7d8897;
		stroke-width: 1.8;
		stroke-linejoin: round;
	}
	.fc-num {
		min-width: 0;
	}
	.fc-say {
		margin: 0 0 0.15rem;
		font-size: 1.15rem;
		font-weight: 600;
		line-height: 1.3;
	}
	.compact .fc-say {
		font-size: 1rem;
	}
	.lvl {
		padding: 0 0.35rem;
		border-radius: 6px;
		white-space: nowrap;
	}
	.lvl-low {
		background: #e9edf2;
		color: #3d4856;
	}
	.lvl-mid {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.lvl-high {
		background: #ffe2a8;
		color: #6d3f00;
	}
	.fc-kwh {
		margin: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 0.35rem;
	}
	.fc-kwh .big-num {
		font-size: 1.9rem;
		color: var(--text);
	}
	.compact .fc-kwh .big-num {
		font-size: 1.5rem;
	}
	.fc-sub {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.fc-flags {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--muted);
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
	}
	.fc-facts {
		margin: 0.6rem 0 0;
		padding-left: 1.1rem;
		font-size: 0.875rem;
		color: var(--muted);
	}
	@media (prefers-reduced-motion: no-preference) {
		.rays {
			transform-origin: 24px 24px;
			animation: spin 40s linear infinite;
		}
		.spark .draw {
			animation: reveal 1.1s cubic-bezier(0.22, 1, 0.36, 1) both 0.15s;
		}
		.spark .pk {
			animation: pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both 1.1s;
			transform-box: fill-box;
			transform-origin: center;
		}
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	@keyframes reveal {
		from {
			clip-path: inset(0 100% 0 0);
		}
		to {
			clip-path: inset(0 0 0 0);
		}
	}
	@keyframes pop {
		from {
			transform: scale(0);
		}
	}
	.norm {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.norm-txt {
		font-size: 0.95rem;
	}
	.norm-bar {
		position: relative;
		height: 8px;
		border-radius: 999px;
		background: #eef1f5;
		overflow: visible;
	}
	.norm-fill {
		position: absolute;
		inset: 0 auto 0 0;
		border-radius: 999px;
		background: var(--sun);
	}
	.norm-fill.wx-part {
		background: #e9b553;
	}
	.norm-fill.wx-cloud {
		background: #98a3b1;
	}
	.norm-100 {
		position: absolute;
		left: 50%;
		top: -4px;
		bottom: -4px;
		width: 2px;
		background: var(--text);
		border-radius: 1px;
	}
	.norm-legend {
		margin: 0;
		font-size: 0.8125rem;
	}
	.spark {
		margin: 0;
		position: relative;
	}
	.spark svg {
		display: block;
		height: 76px;
		overflow: visible;
	}
	.compact .spark svg {
		height: 56px;
	}
	.spark .base {
		stroke: var(--line);
		stroke-width: 1;
	}
	.spark .area {
		fill: var(--sun);
		opacity: 0.28;
	}
	.spark .area.wx-cloud {
		fill: #98a3b1;
	}
	.spark .ln {
		fill: none;
		stroke: var(--sun-strong);
		stroke-width: 2;
	}
	.spark .pk {
		fill: #fff;
		stroke: var(--sun-strong);
		stroke-width: 2;
	}
	.ticks {
		position: relative;
		height: 1rem;
		margin-top: -14px;
		font-size: 0.75rem;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.ticks span {
		position: absolute;
		transform: translateX(-50%);
	}
	.ticks span:first-child {
		transform: none;
	}
	.ticks span:last-child {
		transform: translateX(-100%);
	}
	.fc-foot {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.fc :global(.disc) {
		margin-top: 0;
	}
	.fc-err p {
		margin: 0 0 0.5rem;
	}
	.fc-skel {
		display: grid;
		gap: 0.5rem;
	}
	.fc-skel i {
		display: block;
		height: 14px;
		border-radius: 6px;
		background: linear-gradient(90deg, #f0ece2, #f8f5ee, #f0ece2);
	}
	.fc-skel i:first-child {
		height: 36px;
		width: 60%;
	}
	.fc-skel i:last-child {
		height: 48px;
	}
	@media print {
		.fc-days {
			display: none;
		}
	}
</style>
