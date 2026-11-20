<script lang="ts" module>
	// Розрахунок «а якщо інша потужність» на клієнті з помісячних масивів API (та сама модель, що й на сервері):
	// генерація на 1 кВт = генерація рекомендованої станції ÷ її потужність; денне споживання = місячне × частка дня;
	// використано будівлею = min(генерація, денне споживання); решта — надлишок, який не можна продати.
	import type { SolarMonth } from './api.ts';

	export interface ScenarioParams {
		tariff: number;
		capex: number;
		fixed: number;
		daytime: number;
	}

	export interface ScenarioResult {
		kw: number;
		months: SolarMonth[];
		gen: number;
		cons: number;
		self: number;
		surplus: number;
		coverage: number; // 0..1
		capexTotal: number;
		savings: number;
		payback: number | null;
	}

	export function simulate(monthly: SolarMonth[], kwRec: number, kw: number, p: ScenarioParams): ScenarioResult {
		const months = [...monthly]
			.sort((a, b) => a.month - b.month)
			.map((m) => {
				const perKw = kwRec > 0 ? m.gen_kwh / kwRec : 0;
				const gen = perKw * kw;
				const day = m.cons_kwh * p.daytime;
				const self = Math.min(gen, day);
				return { month: m.month, gen_kwh: gen, cons_kwh: m.cons_kwh, self_kwh: self, surplus_kwh: Math.max(0, gen - self) };
			});
		const s = (f: (m: SolarMonth) => number) => months.reduce((a, m) => a + f(m), 0);
		const gen = s((m) => m.gen_kwh);
		const cons = s((m) => m.cons_kwh);
		const self = s((m) => m.self_kwh);
		const capexTotal = kw > 0 ? p.fixed + kw * p.capex : 0;
		const savings = self * p.tariff;
		return {
			kw,
			months,
			gen,
			cons,
			self,
			surplus: gen - self,
			coverage: cons > 0 ? self / cons : 0,
			capexTotal,
			savings,
			payback: savings > 0 ? capexTotal / savings : null
		};
	}

	/** Українська множина: plural(3, 'рік', 'роки', 'років') → «роки» */
	export function plural(n: number, one: string, few: string, many: string): string {
		const a = Math.abs(Math.trunc(n));
		const n10 = a % 10;
		const n100 = a % 100;
		if (n10 === 1 && n100 !== 11) return one;
		if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return few;
		return many;
	}

	/** Окупність словами, з одним знаком після коми: 3,64 → «окупиться за 3,6 року» */
	export function paybackWords(years: number | null | undefined): string {
		if (years === null || years === undefined || !Number.isFinite(years)) return 'не окупиться';
		if (years < 1) return 'окупиться менш ніж за рік';
		// дробове число → «року» (родовий однини), як і заведено в українській
		return `окупиться за ${(Math.round(years * 10) / 10).toFixed(1).replace('.', ',')} року`;
	}
</script>

<script lang="ts">
	import type { SolarItem } from './api.ts';
	import Icon from './Icon.svelte';
	import { num } from './format.ts';
	import SolarChart from './SolarChart.svelte';
	import StatCard from './StatCard.svelte';
	import Disclosure from './Disclosure.svelte';
	import { fadeUp } from './motion.ts';

	let {
		item,
		monthly,
		params,
		usableShare = 0.5,
		m2PerKw = 6,
		kw = $bindable(null)
	}: {
		item: SolarItem;
		monthly: SolarMonth[];
		params: ScenarioParams;
		usableShare?: number;
		m2PerKw?: number;
		kw?: number | null;
	} = $props();

	const uid = $props.id();
	const kwRec = $derived(item.kw_recommended ?? 0);
	let roof = $state<number | null>(null);
	let kwInput = $state<number | null>(null);

	// початкові значення — з розрахунку сервера
	$effect.pre(() => {
		if (roof === null) roof = item.roof_area_m2 ?? null;
		if (kwInput === null) kwInput = item.kw_recommended ?? null;
	});

	const kwNow = $derived(kwInput !== null && kwInput > 0 ? kwInput : 0);
	$effect(() => {
		kw = kwNow > 0 ? kwNow : null;
	});

	const roofMax = $derived(roof && roof > 0 ? Math.floor(((roof * usableShare) / m2PerKw) * 10) / 10 : null);
	const sliderMax = $derived(Math.max(5, Math.ceil(Math.max(roofMax ?? 0, kwRec * 2.5))));
	const step = $derived(sliderMax > 60 ? 1 : 0.5);

	const sim = $derived(simulate(monthly, kwRec, kwNow, params));
	const surplusShare = $derived(sim.gen > 0 ? sim.surplus / sim.gen : 0);
	const overRoof = $derived(roofMax !== null && kwNow > roofMax + 0.05);

	const verdict = $derived.by(() => {
		if (kwNow <= 0) return { tone: 'info', text: 'Виберіть потужність станції, щоб побачити розрахунок.' };
		if (overRoof)
			return { tone: 'bad', text: `Стільки панелей не вміститься на дах: максимум ≈ ${num(roofMax, 1)} кВт.` };
		if (surplusShare > 0.02)
			return {
				tone: 'warn',
				text: `Забагато: ${num(surplusShare * 100)} % енергії пропадатиме — заклад не може продати надлишок. Гроші за ці панелі не повернуться.`
			};
		if (kwNow < kwRec * 0.9)
			return { tone: 'info', text: `Можна більше: до ${num(kwRec, 1)} кВт будівля все ще використає всю енергію сама.` };
		return { tone: 'ok', text: 'Оптимальний розмір: будівля сама використовує всю енергію станції.' };
	});
	const pbYears = $derived(sim.payback);
	const pbUnit = $derived(pbYears === null ? '' : 'року'); // «3,4 року» — дробові числа завжди «року»
	const fill = $derived(Math.min(100, (kwNow / sliderMax) * 100));
	const recPos = $derived(Math.min(100, (kwRec / sliderMax) * 100));
</script>

<section class="card scen" aria-labelledby="{uid}-h">
	<h2 id="{uid}-h">Інша потужність?</h2>

	<div class="kwbox">
		<div class="kwtop">
			<label for="{uid}-kw" class="kwlabel">Потужність станції</label>
			<output for="{uid}-kw" class="kwval" aria-hidden="true"><span>{num(kwNow, kwNow < 10 ? 1 : 0)}</span> кВт</output>
		</div>
		<div class="rangebox" style:--fill="{fill}%" style:--rec={recPos}>
			<input
				id="{uid}-kw"
				class="big-range"
				type="range"
				min="0.5"
				max={sliderMax}
				{step}
				bind:value={kwInput}
				aria-valuetext="{num(kwNow, 1)} кіловат"
			/>
			<span class="rec-mark" aria-hidden="true"><i></i>рекомендовано</span>
		</div>
		<div class="quick">
			<button type="button" class="chip press" aria-pressed={Math.abs(kwNow - kwRec) < 0.05} onclick={() => (kwInput = kwRec)}
				><Icon name="check" size={14} stroke={2.4} /> Рекомендовано: {num(kwRec, 1)} кВт</button
			>
			{#if roofMax}
				<button type="button" class="chip press" aria-pressed={Math.abs(kwNow - roofMax) < 0.05} onclick={() => (kwInput = roofMax)}
					>Увесь дах · {num(roofMax, 1)} кВт</button
				>
			{/if}
		</div>
	</div>

	<div class="res" aria-live="polite">
		<StatCard
			label="Покриє потреби"
			value={sim.coverage * 100}
			unit="%"
			icon="sun"
			hint="З кожних 100 кВт·год електроенергії {num(sim.coverage * 100)} дасть власне сонце."
		/>
		<StatCard
			label="Економія на рік"
			value={sim.savings / 1000}
			unit="тис. грн"
			icon="wallet"
			
		/>
		<StatCard
			label="Окупиться за"
			value={pbYears}
			decimals={1}
			unit={pbUnit}
			icon="clock"
			tone={pbYears === null ? 'neutral' : surplusShare > 0.02 || overRoof ? 'warn' : 'good'}
			toneLabel={surplusShare > 0.02 ? 'довше, ніж могло б' : 'добре'}
			hint="Станція коштуватиме ≈ {sim.capexTotal >= 1e6 ? `${num(sim.capexTotal / 1e6, 2)} млн` : `${num(Math.round(sim.capexTotal / 1000))} тис.`} грн."
		/>
	</div>

	{#key verdict.tone}
		<p class="verdict v-{verdict.tone}" role="status" in:fadeUp={{ y: 6 }}>
			<span class="vi" aria-hidden="true"><Icon name={verdict.tone === 'ok' ? 'check' : verdict.tone === 'info' ? 'info' : 'alert'} size={14} stroke={2.4} /></span>
			<span>{verdict.text}</span>
		</p>
	{/key}

	<SolarChart months={sim.months} />

	<Disclosure summary="Дах і точна потужність">
		<div class="tech">
			<div class="field roof">
				<label for="{uid}-roof">Площа даху, м²</label>
				<input id="{uid}-roof" type="number" min="1" step="10" inputmode="decimal" bind:value={roof} />
				<small class="muted"
					>під панелі — {num(usableShare * 100)} % даху, {num(m2PerKw)} м² на 1 кВт → максимум
					<strong>{num(roofMax, 1)} кВт</strong></small
				>
			</div>
			<div class="field">
				<label for="{uid}-kwn">Точна потужність, кВт</label>
				<input id="{uid}-kwn" type="number" min="0.5" step="0.1" inputmode="decimal" bind:value={kwInput} />
			</div>
		</div>
		<dl class="facts">
			<div><dt>Генерація за рік</dt><dd>{num(sim.gen)} кВт·год</dd></div>
			<div><dt>Використає будівля</dt><dd>{num(sim.self)} з {num(sim.cons)} кВт·год</dd></div>
			<div><dt>Надлишок (пропадає)</dt><dd>{num(sim.surplus)} кВт·год ({num(surplusShare * 100)} %)</dd></div>
			<div><dt>Вартість</dt><dd>{num(params.fixed)} грн + {num(kwNow, 1)} кВт × {num(params.capex)} грн = {num(sim.capexTotal)} грн</dd></div>
			<div><dt>Економія</dt><dd>{num(sim.self)} кВт·год × {num(params.tariff, 2)} грн = {num(sim.savings)} грн/рік</dd></div>
			<div><dt>Проста окупність</dt><dd>{pbYears !== null ? `${num(pbYears, 1)} року` : 'не окупиться'}</dd></div>
		</dl>
		<ul class="how">
			<li>Генерація на 1 кВт — PVGIS для Полтави, середній рік; множиться на вибрану потужність.</li>
			<li>
				Удень будівля споживає {num(params.daytime * 100)} % своєї електроенергії; використати сама вона може лише цю
				частину. Решта генерації — надлишок, бо продавати його комунальний заклад зараз не може.
			</li>
			<li>Окупність проста: без кредиту, інфляції та зносу панелей. Це оцінка, а не проєкт станції.</li>
		</ul>
	</Disclosure>
</section>

<style>
	.intro {
		margin-top: -0.25rem;
	}
	.kwbox {
		max-width: 760px;
		margin-bottom: 1.25rem;
	}
	.kwtop {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}
	.kwlabel {
		font-weight: 700;
		font-size: 1rem;
	}
	.kwval {
		font-size: 1.1rem;
		font-weight: 600;
		color: var(--sun-ink);
	}
	.kwval span {
		font-size: 2.2rem;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		letter-spacing: -0.01em;
	}
	.rangebox {
		position: relative;
	}
	.rangebox {
		padding-bottom: 1.1rem;
	}
	.rec-mark {
		position: absolute;
		left: calc(16px + (100% - 32px) * var(--rec) / 100);
		top: 34px;
		display: flex;
		flex-direction: column;
		align-items: center;
		font-size: 0.72rem;
		font-weight: 600;
		color: var(--surplus-ink);
		pointer-events: none;
		transform: translateX(-50%);
		white-space: nowrap;
	}
	.rec-mark i {
		width: 2px;
		height: 6px;
		background: var(--surplus-ink);
	}
	.big-range {
		-webkit-appearance: none;
		appearance: none;
		width: 100%;
		height: 44px;
		background: transparent;
		cursor: pointer;
		margin: 0;
	}
	.big-range::-webkit-slider-runnable-track {
		height: 12px;
		border-radius: var(--r-sm);
		background: linear-gradient(90deg, var(--sun-strong) 0 var(--fill), #e7eaef var(--fill) 100%);
	}
	.big-range::-moz-range-track {
		height: 12px;
		border-radius: var(--r-sm);
		background: #e7eaef;
	}
	.big-range::-moz-range-progress {
		height: 12px;
		border-radius: var(--r-sm);
		background: var(--sun-strong);
	}
	.big-range::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 32px;
		height: 32px;
		margin-top: -10px;
		border-radius: 50%;
		background: #fff;
		border: 4px solid var(--sun-strong);
		box-shadow: 0 2px 8px rgba(138, 79, 0, 0.3);
		transition: transform var(--dur-fast, 300ms) var(--ease-out, ease);
	}
	.big-range::-moz-range-thumb {
		width: 26px;
		height: 26px;
		border-radius: 50%;
		background: #fff;
		border: 4px solid var(--sun-strong);
	}
	.big-range:hover::-webkit-slider-thumb,
	.big-range:active::-webkit-slider-thumb {
		transform: scale(1.12);
	}
	.big-range:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: 4px;
		border-radius: var(--r-btn);
	}
	.quick {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.4rem;
	}
	.chip {
		font: inherit;
		font-size: 0.875rem;
		font-weight: 600;
		padding: 0.35rem 0.8rem;
		min-height: 34px;
		border-radius: var(--r-pill);
		border: 1px solid var(--line-strong);
		background: #fff;
		color: var(--text);
		cursor: pointer;
	}
	.chip[aria-pressed='true'] {
		background: var(--sun-soft);
		border-color: var(--sun-strong);
		color: var(--sun-ink);
		box-shadow: inset 0 0 0 1px var(--sun-strong);
	}
	.res {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.85rem;
		margin-bottom: 0.9rem;
	}
	@media (max-width: 640px) {
		/* 2 в ряд; третя («Окупиться за») — на всю ширину */
		.res {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.625rem;
		}
		.res > :global(:last-child:nth-child(odd)) {
			grid-column: 1 / -1;
		}
		.chip {
			min-height: 40px;
		}
		.tech input {
			width: 100%;
		}
		.tech > :global(*) {
			flex: 1 1 100%;
		}
	}
	.verdict {
		display: flex;
		align-items: flex-start;
		gap: 0.55rem;
		padding: 0.65rem 0.9rem;
		border-radius: var(--radius);
		border: 1px solid var(--line);
		margin: 0 0 1rem;
		font-weight: 500;
	}
	.vi {
		flex: none;
		width: 1.4rem;
		height: 1.4rem;
		border-radius: 50%;
		display: inline-grid;
		place-items: center;
		font-weight: 800;
		font-size: 0.85rem;
		color: #fff;
		background: var(--accent);
	}
	.v-ok {
		background: var(--ok-soft);
		border-color: var(--ok);
	}
	.v-ok .vi {
		background: var(--ok);
	}
	.v-warn {
		background: var(--warn-soft);
		border-color: var(--warn);
	}
	.v-warn .vi {
		background: var(--warn);
	}
	.v-bad {
		background: var(--bad-soft);
		border-color: var(--bad);
	}
	.v-bad .vi {
		background: var(--bad);
	}
	.v-info {
		background: var(--accent-soft);
		border-color: var(--accent);
	}
	.tech {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.5rem;
		margin-bottom: 0.75rem;
	}
	.tech input {
		width: 9rem;
	}
	.roof small {
		display: block;
		max-width: 36ch;
	}
	.facts {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.5rem 1.25rem;
		margin: 0 0 0.75rem;
	}
	.facts div {
		border-left: 3px solid var(--line);
		padding-left: 0.6rem;
	}
	.facts dt {
		font-size: 0.8125rem;
		color: var(--muted);
		font-weight: 600;
	}
	.facts dd {
		margin: 0;
		font-variant-numeric: tabular-nums;
	}
	.how {
		margin: 0;
		padding-left: 1.2rem;
		font-size: 0.9rem;
	}
</style>
