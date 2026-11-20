<script lang="ts">
	// «Що буде, якщо вимкнуть світло»: початок і тривалість відключення → скільки годин протримається заклад
	import { independenceApi, duration, type OutageResult } from './api-independence.ts';
	import { errMessage } from './api.ts';
	import { num, hh } from './format.ts';
	import DemoPill from './DemoPill.svelte';
	import Icon from './Icon.svelte';
	import Term from './Term.svelte';
	import CountUp from './CountUp.svelte';
	import Disclosure from './Disclosure.svelte';

	let {
		siteId,
		day = null,
		startDefault = 18
	}: { siteId: number | string; day?: string | null; startDefault?: number } = $props();

	// svelte-ignore state_referenced_locally
	let start = $state(startDefault);
	let hours = $state(6);
	let r = $state<OutageResult | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(false);

	let seq = 0;
	let timer: ReturnType<typeof setTimeout> | undefined;
	async function load(id: number | string, d: string | null, s: number, n: number) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const res = await independenceApi.outage(id, { day: d, start_hour: s, hours: n });
			if (my === seq) r = res;
		} catch (e) {
			if (my === seq) error = errMessage(e);
		} finally {
			if (my === seq) loading = false;
		}
	}
	$effect(() => {
		const a = [siteId, day, start, hours] as const;
		clearTimeout(timer);
		timer = setTimeout(() => load(...a), 180);
		return () => clearTimeout(timer);
	});

	const PRESETS = [2, 4, 8, 12, 24];
	const step = (v: number, dlt: number, min: number, max: number) => Math.min(max, Math.max(min, v + dlt));

	/** «21:20» (+ «наступного дня») для моменту start + h годин */
	function clock(h: number): string {
		const total = Math.round((start + h) * 60);
		const m = ((total % 1440) + 1440) % 1440;
		const s = `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
		return total >= 1440 ? `${s} наступного дня` : s;
	}

	const tl = $derived(r?.timeline ?? []);
	const max = $derived(Math.max(0.01, ...tl.map((t) => t.load_kwh)));
	const parts = (t: OutageResult['timeline'][number]) => {
		const sun = Math.min(t.solar_kwh, t.load_kwh);
		const bat = Math.min(t.from_battery_kwh, t.load_kwh - sun);
		return { sun, bat, gap: Math.max(0, t.load_kwh - sun - bat) };
	};
	const zero = $derived(!!r && !r.survives_all && r.survives_hours < 0.05);
	/** Дрібний дефіцит (менше 1 кВт·год або ≥ 90 % часу зі світлом) — нейтральний тон, без «потрібен генератор» */
	const minor = $derived(
		!!r && !r.survives_all && !zero && (r.unmet_kwh < 1 || r.survives_hours / Math.max(0.01, r.hours) >= 0.9)
	);
	const tone = $derived(!r ? 'ok' : r.survives_all ? 'ok' : minor ? 'warn' : 'bad');
	/** Акумулятор на початок відключення заряджений не повністю — пояснюємо чому */
	const socNote = $derived(
		r && r.soc_start_pct != null && r.soc_start_pct < 97 && !zero
			? `До ${hh(r.start_hour)} акумулятор віддасть частину енергії будівлі, тож на початок відключення він заряджений на ${num(r.soc_start_pct, 0)} %.`
			: ''
	);
	const okPct = $derived(
		!r ? 0 : r.survives_all ? 100 : Math.max(0, Math.min(100, (r.survives_hours / Math.max(0.01, r.hours)) * 100))
	);
	const srText = $derived.by(() => {
		if (!r) return '';
		if (r.survives_all) return `Заклад протримається всі ${r.hours} год: з ${hh(r.start_hour)} до ${clock(r.hours)}.`;
		if (zero) return `Резерв не зафіксовано: з ${hh(r.start_hour)} бракуватиме ${num(r.unmet_kwh, 1)} кВт·год.`;
		return `Заклад протримається ${duration(r.survives_hours)} з ${r.hours} год, приблизно до ${clock(r.survives_hours)}. Бракуватиме ${num(r.unmet_kwh, 1)} кВт·год. ${socNote}`;
	});
</script>

<section class="panel os" aria-labelledby="os-h">
	<!-- Позначка «ДЕМО» — у DOM одразу після заголовка, як і візуально (порядок Tab = порядок читання) -->
	<div class="panel-head os-head">
		<div>
			<div class="os-hrow">
				<h3 id="os-h">Перевірте самі</h3>
				<DemoPill text="Навантаження — типовий добовий профіль за реальним річним споживанням UMUNI; СЕС і акумулятор змодельовані" />
			</div>
			<p class="muted sub">Оберіть, коли і на скільки зникне світло, — одразу побачите, скільки заклад протримається на <Term key="акумулятор">акумуляторі</Term> і сонці.</p>
		</div>
	</div>

	<div class="controls">
		<div class="ctl">
			<span class="ctl-l" id="os-start-l">Світло вимкнуть о</span>
			<div class="stepper">
				<button type="button" class="sb" aria-label="На годину раніше" onclick={() => (start = (start + 23) % 24)}>−</button>
				<output class="sv tnum" aria-live="polite" aria-labelledby="os-start-l">{hh(start)}</output>
				<button type="button" class="sb" aria-label="На годину пізніше" onclick={() => (start = (start + 1) % 24)}>+</button>
			</div>
			<input type="range" min="0" max="23" step="1" bind:value={start} aria-labelledby="os-start-l" aria-valuetext={hh(start)} />
		</div>
		<div class="ctl">
			<span class="ctl-l" id="os-dur-l">і не буде світла</span>
			<div class="stepper">
				<button type="button" class="sb" aria-label="На годину менше" onclick={() => (hours = step(hours, -1, 1, 24))} disabled={hours <= 1}>−</button>
				<output class="sv tnum" aria-live="polite" aria-labelledby="os-dur-l">{hours} год</output>
				<button type="button" class="sb" aria-label="На годину більше" onclick={() => (hours = step(hours, 1, 1, 24))} disabled={hours >= 24}>+</button>
			</div>
			<div class="presets" role="group" aria-label="Швидкий вибір тривалості">
				{#each PRESETS as p (p)}
					<button type="button" class="chip" aria-pressed={hours === p} onclick={() => (hours = p)}>{p} год</button>
				{/each}
			</div>
		</div>
	</div>

	{#if error}
		<div class="notice notice-error" role="alert"><p><strong>Не вдалося порахувати.</strong> {error}</p></div>
	{:else if r}
		<div class="result {tone}" class:stale={loading}>
			<span class="r-sign" aria-hidden="true">{#key tone}<span class="r-glyph"><Icon name={tone === 'ok' ? 'check' : tone === 'warn' ? 'alert' : 'x'} size={22} stroke={2.4} /></span>{/key}</span>
			<div class="r-body">
				<p class="r-title" aria-hidden="true">
					{#if r.survives_all}
						Протримається всі {r.hours} год
					{:else if zero}
						Резерв не зафіксовано
					{:else if minor}
						Майже вистачить: <CountUp value={r.survives_hours} format={duration} duration={600} /> з {r.hours} год
					{:else}
						Протримається <CountUp value={r.survives_hours} format={duration} duration={600} /> з {r.hours} год
					{/if}
				</p>
				<p class="r-text" aria-hidden="true">
					{#if r.survives_all}
						Світло зникне о {hh(r.start_hour)} і повернеться о {clock(r.hours)} — сонця й акумулятора вистачить на весь цей час.
					{:else if zero}
						Світло зникне о {hh(r.start_hour)}: у даних немає зарядженого акумулятора, а сонця в цей час замало. Бракуватиме {num(r.unmet_kwh, 1)} кВт·год.
					{:else if minor}
						Світло зникне о {hh(r.start_hour)} — енергії вистачить майже на весь час, приблизно до {clock(r.survives_hours)}. Бракуватиме лише {num(r.unmet_kwh, 1)} кВт·год — досить наприкінці вимкнути частину техніки.
					{:else}
						Світло зникне о {hh(r.start_hour)} — енергії вистачить приблизно до {clock(r.survives_hours)}. Далі бракуватиме {num(r.unmet_kwh, 1)} кВт·год: потрібен генератор або більший акумулятор.
					{/if}
				</p>
				{#if socNote}<p class="r-soc" aria-hidden="true"><Icon name="battery" size={15} /> <span>{socNote}</span></p>{/if}
				<p class="r-demo"><DemoPill align="left" text="Навантаження — типовий профіль за реальним річним споживанням UMUNI; СЕС і акумулятор змодельовані" /></p>
				<p class="visually-hidden" role="status" aria-live="polite">{srText}</p>
			</div>
		</div>

		<!-- Проста стрічка часу: скільки з відключення буде світло -->
		<div class="run" class:stale={loading} aria-hidden="true">
			<div class="run-track">
				<span class="run-ok" style:width="{okPct}%">
					{#if okPct >= 18}<span class="run-lbl"><Icon name="check" size={15} stroke={2.6} /> є світло</span>{/if}
				</span>
				<span class="run-gap" style:width="{100 - okPct}%">
					{#if 100 - okPct >= 18}<span class="run-lbl"><Icon name="x" size={15} stroke={2.6} /> без світла</span>{/if}
				</span>
				{#if okPct > 0 && okPct < 100}
					<span class="run-cut" style:left="{okPct}%"><b>{clock(r.survives_hours)}</b></span>
				{/if}
			</div>
			<div class="run-scale tnum">
				<span><b>{hh(r.start_hour)}</b> світло зникло</span>
				<span class="rs-end"><b>{clock(r.hours)}</b> світло повернулось</span>
			</div>
		</div>

		<Disclosure summary="Погодинно: звідки береться енергія" hint="{tl.length} год">
			<figure class="tl">
				<div class="tl-scroll">
				<div class="cols" style="--n: {tl.length}" aria-hidden="true">
					{#each tl as t, i (i)}
						{@const p = parts(t)}
						<div class="col" style="--i: {i}" title="{hh(t.hour)}: потрібно {num(t.load_kwh, 1)} кВт·год, сонце {num(p.sun, 1)}, акумулятор {num(p.bat, 1)}, бракує {num(p.gap, 1)}; в акумуляторі лишилось {num(t.battery_kwh_after, 1)} кВт·год">
							<div class="stack" style="height: {(t.load_kwh / max) * 100}%">
								<span class="gap" style="flex-grow: {p.gap}"></span>
								<span class="bat" style="flex-grow: {p.bat}"></span>
								<span class="sun" style="flex-grow: {p.sun}"></span>
							</div>
							<span class="mark {t.covered ? 'y' : 'n'}"><Icon name={t.covered ? 'check' : 'x'} size={13} stroke={2.6} /></span>
							<span class="hl tnum">{String(t.hour).padStart(2, '0')}</span>
						</div>
					{/each}
				</div>
				</div>
				<!-- Таблиця для екранних зчитувачів: обгортка, бо сама таблиця не стискається до 1 px і розширює сторінку -->
				<div class="visually-hidden"><table>
					<caption>Погодинно під час відключення</caption>
					<thead><tr><th>Година</th><th>Потрібно, кВт·год</th><th>Сонце</th><th>Акумулятор</th><th>Чи вистачає</th></tr></thead>
					<tbody>
						{#each tl as t, i (i)}
							<tr><td>{hh(t.hour)}</td><td>{num(t.load_kwh, 1)}</td><td>{num(t.solar_kwh, 1)}</td><td>{num(t.from_battery_kwh, 1)}</td><td>{t.covered ? 'так' : 'ні'}</td></tr>
						{/each}
					</tbody>
				</table></div>
				<figcaption class="legend">
					<span><i class="k sun"></i>сонце</span>
					<span><i class="k bat"></i>акумулятор</span>
					<span><i class="k gap"></i>бракує (<Icon name="x" size={12} stroke={2.6} /> — година без світла)</span>
					<span class="muted">висота стовпчика — скільки енергії потрібно закладу за годину</span>
				</figcaption>
			</figure>
			{#if r.note}<p class="note muted small"><Icon name="info" size={15} /> {r.note}</p>{/if}
		</Disclosure>
	{:else if loading}
		<p class="muted" role="status">Рахуємо…</p>
	{/if}
</section>

<style>
	.os {
		display: grid;
		gap: 1.2rem;
	}
	.os .panel-head {
		margin: 0;
		align-items: flex-start;
	}
	.sub {
		margin: 0.2rem 0 0;
		max-width: 70ch;
	}
	.os-head > div {
		flex: 1 1 auto;
		min-width: 0;
	}
	.os-hrow {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.4rem 1rem;
	}
	.os-hrow h3 {
		margin: 0;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem 2.5rem;
		padding: 1rem 1.2rem;
		border-radius: var(--r-card);
		background: #f4f7fb;
		border: 1px solid #e3e8ef;
	}
	.ctl {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem 0.9rem;
	}
	.ctl-l {
		font-weight: 600;
		font-size: 1.05rem;
	}
	.stepper {
		display: inline-flex;
		align-items: center;
		border: 1px solid var(--line-strong);
		border-radius: var(--r-btn);
		background: #fff;
		overflow: hidden;
	}
	.sb {
		width: 2.75rem;
		height: 2.75rem;
		border: 0;
		background: #fff;
		font: inherit;
		font-size: 1.4rem;
		font-weight: 700;
		color: var(--accent);
		cursor: pointer;
	}
	.sb:hover:not(:disabled) {
		background: var(--accent-soft);
	}
	.sb:disabled {
		color: #a9b3bf;
		cursor: not-allowed;
	}
	.sv {
		min-width: 5.2rem;
		text-align: center;
		font-size: 1.35rem;
		font-weight: 700;
	}
	input[type='range'] {
		width: 11rem;
		accent-color: var(--navy-3);
	}
	.presets {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.chip {
		padding: 0.3rem 0.75rem;
		min-height: 36px;
		border-radius: var(--r-pill);
		border: 1px solid #cfd7e1;
		background: #fff;
		font: inherit;
		font-size: 0.9rem;
		font-weight: 600;
		cursor: pointer;
	}
	.chip[aria-pressed='true'] {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.result {
		display: flex;
		gap: 1rem;
		align-items: center;
		padding: 1rem 1.25rem;
		border-radius: var(--r-card);
		border: 1px solid;
		border-left-width: 6px;
		transition: opacity 0.2s;
	}
	.result.ok {
		background: var(--surplus-soft);
		border-color: var(--surplus);
	}
	.result.bad {
		background: var(--deficit-soft);
		border-color: var(--deficit);
	}
	.result.warn {
		background: var(--sun-soft, #fff4dc);
		border-color: #e0a63a;
	}
	.warn .r-sign {
		background: #c98a12;
	}
	.warn .r-title {
		color: var(--sun-ink, #7a4b00);
	}
	.r-soc {
		display: flex;
		gap: 0.35rem;
		align-items: flex-start;
		margin: 0.45rem 0 0;
		font-size: 0.875rem;
		color: #3d4857;
	}
	.r-soc :global(.icon) {
		flex: none;
		margin-top: 0.15rem;
	}
	.stale {
		opacity: 0.6;
	}
	.r-sign {
		flex: none;
		display: grid;
		place-items: center;
		width: 3rem;
		height: 3rem;
		border-radius: 50%;
		color: #fff;
		font-size: 1.6rem;
		font-weight: 800;
	}
	.ok .r-sign {
		background: var(--surplus);
	}
	.bad .r-sign {
		background: var(--deficit);
	}
	.r-body {
		min-width: 0;
		flex: 1;
	}
	.r-demo {
		margin: 0.5rem 0 0;
	}
	.r-glyph {
		display: inline-block;
	}
	.r-title {
		margin: 0 0 0.2rem;
		font-size: 1.45rem;
		font-weight: 700;
		line-height: 1.25;
	}
	.ok .r-title {
		color: var(--surplus-ink);
	}
	.bad .r-title {
		color: var(--deficit-ink);
	}
	.r-text {
		margin: 0;
		color: #2b3645;
	}
	/* Стрічка часу відключення */
	.run {
		transition: opacity 0.2s;
	}
	.run-track {
		position: relative;
		display: flex;
		height: 2.6rem;
		border-radius: var(--r-card);
		overflow: visible;
		background: #edf1f5;
	}
	.run-ok,
	.run-gap {
		position: relative;
		display: flex;
		align-items: center;
		height: 100%;
		overflow: hidden;
		white-space: nowrap;
		transition: width 0.7s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.run-ok {
		background: linear-gradient(90deg, #2e9a4f, var(--surplus));
		border-radius: var(--r-card) 0 0 var(--r-card);
		color: #fff;
	}
	.run-gap {
		background: repeating-linear-gradient(135deg, var(--deficit) 0 8px, #d9561d 8px 16px);
		border-radius: 0 var(--r-card) var(--r-card) 0;
		color: #fff;
	}
	.run-ok:only-child,
	.run-gap[style*='width: 100%'] {
		border-radius: var(--r-card);
	}
	.run-lbl {
		padding: 0 0.85rem;
		font-weight: 700;
		font-size: 0.95rem;
		text-shadow: 0 1px 1px rgba(0, 0, 0, 0.25);
	}
	.run-cut {
		position: absolute;
		top: -0.45rem;
		bottom: -0.45rem;
		width: 3px;
		margin-left: -1.5px;
		background: var(--ink, #0f1b2d);
		border-radius: var(--r-sm);
		transition: left 0.7s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.run-cut b {
		position: absolute;
		top: -1.55rem;
		left: 50%;
		transform: translateX(-50%);
		padding: 0.05rem 0.5rem;
		border-radius: var(--r-pill);
		background: var(--ink, #0f1b2d);
		color: #fff;
		font-size: 0.8125rem;
		white-space: nowrap;
	}
	.run-scale {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		margin-top: 0.45rem;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.run-scale b {
		color: var(--text);
	}
	.run:has(.run-cut) {
		padding-top: 1.4rem;
	}
	.tl {
		margin: 0;
	}
	.cols {
		display: grid;
		grid-template-columns: repeat(var(--n), minmax(0, 1fr));
		gap: 4px;
		height: 13rem;
		align-items: end;
		padding-bottom: 0.2rem;
		border-bottom: 1px solid var(--line);
	}
	.col {
		height: 100%;
		display: grid;
		grid-template-rows: 1fr auto auto;
		align-items: end;
		justify-items: center;
		min-width: 0;
	}
	.stack {
		width: min(100%, 3rem);
		display: flex;
		flex-direction: column;
		border-radius: var(--r-sm) var(--r-sm) 0 0;
		overflow: hidden;
		min-height: 3px;
	}
	.stack span {
		flex-basis: 0;
		min-height: 0;
		transition: flex-grow 0.5s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.stack {
		transition: height 0.55s cubic-bezier(0.22, 1, 0.36, 1) calc(var(--i, 0) * 18ms);
	}
	@media (prefers-reduced-motion: no-preference) {
		.col {
			animation: col-in 0.45s cubic-bezier(0.22, 1, 0.36, 1) calc(var(--i, 0) * 25ms) backwards;
		}
		@keyframes col-in {
			from {
				opacity: 0;
				transform: translateY(10px);
			}
		}
		.r-glyph {
			animation: pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
		}
		@keyframes pop {
			from {
				transform: scale(0.3);
				opacity: 0;
			}
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.stack,
		.stack span,
		.run-ok,
		.run-gap,
		.run-cut {
			transition: none;
		}
	}
	.sun,
	.k.sun {
		background: var(--sun);
	}
	.bat,
	.k.bat {
		background: #0f766e;
	}
	.gap,
	.k.gap {
		background: repeating-linear-gradient(135deg, var(--deficit) 0 4px, #f6c9b4 4px 8px);
	}
	.mark {
		font-weight: 800;
		font-size: 0.85rem;
		line-height: 1.6;
	}
	.mark.y {
		color: var(--surplus-ink);
	}
	.mark.n {
		color: var(--deficit-ink);
	}
	.hl {
		font-size: 0.75rem;
		color: var(--muted);
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		margin-top: 0.6rem;
		font-size: 0.875rem;
	}
	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.k {
		display: inline-block;
		width: 0.9rem;
		height: 0.9rem;
		border-radius: var(--r-sm);
	}
	.note {
		display: flex;
		gap: 0.4rem;
		align-items: flex-start;
		margin: 0;
	}
	.rs-end {
		text-align: right;
	}
	.tl-scroll {
		position: relative;
	}
	@media (max-width: 700px) {
		.cols {
			height: 10rem;
			gap: 2px;
		}
		.hl {
			font-size: 0.65rem;
		}
	}

	/* ---------- Телефон: великі елементи під палець ---------- */
	@media (max-width: 640px) {
		.os {
			gap: 1rem;
		}
		.os .panel-head {
			flex-wrap: wrap;
			gap: 0.5rem;
		}
		.sub {
			font-size: 0.875rem;
		}
		.controls {
			flex-direction: column;
			gap: 1rem;
			padding: 0.9rem;
			margin-inline: -0.25rem;
		}
		.ctl {
			display: grid;
			grid-template-columns: minmax(0, 1fr);
			gap: 0.5rem;
		}
		.ctl-l {
			font-size: 0.9375rem;
		}
		.stepper {
			display: grid;
			grid-template-columns: 3.25rem minmax(0, 1fr) 3.25rem;
			width: 100%;
			border-radius: var(--r-btn);
		}
		.sb {
			width: 100%;
			height: 3.25rem;
			font-size: 1.6rem;
			touch-action: manipulation;
		}
		.sb:active:not(:disabled) {
			background: var(--accent-soft);
		}
		.sv {
			min-width: 0;
			font-size: 1.5rem;
			border-inline: 1px solid var(--line-soft, #e6ebf1);
			line-height: 3.25rem;
		}
		input[type='range'] {
			width: 100%;
			height: 2.75rem;
			margin: 0;
		}
		/* Пресети — чипи в один ряд з прокруткою */
		.presets {
			flex-wrap: nowrap;
			gap: 0.4rem;
			overflow-x: auto;
			scrollbar-width: none;
			margin-inline: -0.9rem;
			padding: 2px 0.9rem;
			scroll-padding-inline: 0.9rem;
		}
		.presets::-webkit-scrollbar {
			display: none;
		}
		.chip {
			flex: 1 0 auto;
			min-height: 44px;
			padding: 0.3rem 0.9rem;
			font-size: 0.9375rem;
			touch-action: manipulation;
		}
		.result {
			align-items: flex-start;
			gap: 0.75rem;
			padding: 0.85rem 0.9rem;
			border-left-width: 4px;
		}
		.r-sign {
			width: 2.25rem;
			height: 2.25rem;
			font-size: 1.2rem;
		}
		.r-title {
			font-size: 1.2rem;
		}
		.r-text {
			font-size: 0.9rem;
		}
		.run-lbl {
			padding: 0 0.6rem;
			font-size: 0.8125rem;
		}
		.run-scale {
			font-size: 0.8125rem;
			gap: 0.5rem;
		}
		.run-scale span {
			display: flex;
			flex-direction: column;
			line-height: 1.3;
		}
		.rs-end {
			align-items: flex-end;
		}
		/* Погодинна стрічка: на вузькому екрані — горизонтальна прокрутка всередині, не всієї сторінки */
		.tl-scroll {
			overflow-x: auto;
			overscroll-behavior-x: contain;
			scrollbar-width: thin;
			padding-bottom: 0.25rem;
		}
		.cols {
			min-width: calc(var(--n) * 22px);
			gap: 3px;
		}
		.hl {
			font-size: 0.6875rem;
		}
		.legend {
			font-size: 0.8125rem;
			gap: 0.35rem 0.9rem;
		}
	}
</style>
