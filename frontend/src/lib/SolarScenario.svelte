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
</script>

<script lang="ts">
	import type { SolarItem } from './api.ts';
	import { num } from './format.ts';
	import SolarChart from './SolarChart.svelte';

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

	const rec = $derived(simulate(monthly, kwRec, kwRec, params));
	const sim = $derived(simulate(monthly, kwRec, kwNow, params));
	const surplusShare = $derived(sim.gen > 0 ? sim.surplus / sim.gen : 0);
	const overRoof = $derived(roofMax !== null && kwNow > roofMax + 0.05);

	const verdict = $derived.by(() => {
		if (kwNow <= 0) return { tone: 'info', text: 'Вкажіть потужність станції, щоб побачити розрахунок.' };
		if (overRoof)
			return {
				tone: 'bad',
				text: `На дах не вміститься: за площею ${num(roof)} м² максимум ≈ ${num(roofMax, 1)} кВт.`
			};
		if (surplusShare > 0.02)
			return {
				tone: 'warn',
				text: `${num(surplusShare * 100)} % генерації (${num(sim.surplus)} кВт·год/рік) — надлишок, який заклад не може продати. Гроші за цю частину панелей не повертаються.`
			};
		if (kwNow < kwRec * 0.9)
			return {
				tone: 'info',
				text: `Можна більше: до ${num(kwRec, 1)} кВт уся генерація ще споживається самою будівлею.`
			};
		return { tone: 'ok', text: 'Оптимальний розмір: уся генерація споживається будівлею, надлишку немає.' };
	});

	function delta(v: number | null, base: number | null, unit: string, digits = 0): string {
		if (v === null || base === null) return '';
		const d = v - base;
		if (Math.abs(d) < Math.pow(10, -digits) / 2) return 'як у рекомендованого розміру';
		return `${d > 0 ? '▲ +' : '▼ −'}${num(Math.abs(d), digits)} ${unit} проти рекомендованого`;
	}
</script>

<section class="card scen" aria-labelledby="{uid}-h">
	<h2 id="{uid}-h">А якщо інша потужність?</h2>
	<p class="muted intro">
		Змініть потужність станції або площу даху — покриття, надлишок, економія й окупність перераховуються
		одразу.
	</p>

	<div class="controls">
		<div class="field kwf">
			<label for="{uid}-kw">Потужність станції, кВт</label>
			<div class="kwrow">
				<input
					type="range"
					min="0.5"
					max={sliderMax}
					{step}
					bind:value={kwInput}
					aria-label="Потужність станції, кВт (повзунок)"
					aria-valuetext="{num(kwNow, 1)} кВт"
				/>
				<input id="{uid}-kw" type="number" min="0.5" step="0.1" inputmode="decimal" bind:value={kwInput} />
			</div>
			<div class="quick">
				<button type="button" class="chip" aria-pressed={Math.abs(kwNow - kwRec) < 0.05} onclick={() => (kwInput = kwRec)}
					>Рекомендовано · {num(kwRec, 1)} кВт</button
				>
				{#if roofMax}
					<button type="button" class="chip" aria-pressed={Math.abs(kwNow - roofMax) < 0.05} onclick={() => (kwInput = roofMax)}
						>Увесь дах · {num(roofMax, 1)} кВт</button
					>
				{/if}
			</div>
		</div>
		<div class="field roof">
			<label for="{uid}-roof">Площа даху, м²</label>
			<input id="{uid}-roof" type="number" min="1" step="10" inputmode="decimal" bind:value={roof} />
			<small class="muted"
				>під панелі — {num(usableShare * 100)} % даху, {num(m2PerKw)} м² на 1 кВт → максимум
				<strong>{num(roofMax, 1)} кВт</strong></small
			>
		</div>
	</div>

	<ul class="res" aria-live="polite">
		<li>
			<span>Покриття потреби</span>
			<strong>{num(sim.coverage * 100)} %</strong>
			<small>{num(sim.self)} з {num(sim.cons)} кВт·год/рік — власне сонце</small>
		</li>
		<li class:warn={surplusShare > 0.02}>
			<span>Надлишок (пропадає)</span>
			<strong>{num(sim.surplus)} <em>кВт·год/рік</em></strong>
			<small>{sim.gen > 0 ? `${num(surplusShare * 100)} % генерації` : '—'}</small>
		</li>
		<li>
			<span>Економія</span>
			<strong>{num(sim.savings)} <em>грн/рік</em></strong>
			<small>{delta(sim.savings, rec.savings, 'грн')}</small>
		</li>
		<li>
			<span>Вартість</span>
			<strong>{num(sim.capexTotal)} <em>грн</em></strong>
			<small>{num(params.fixed)} грн + {num(kwNow, 1)} кВт × {num(params.capex)} грн</small>
		</li>
		<li class="pb">
			<span>Проста окупність</span>
			<strong>{sim.payback !== null ? num(sim.payback, 1) : '—'} <em>років</em></strong>
			<small>{delta(sim.payback, rec.payback, 'року', 1)}</small>
		</li>
	</ul>

	<p class="verdict v-{verdict.tone}" role="status">
		<span class="vi" aria-hidden="true">{verdict.tone === 'ok' ? '✓' : verdict.tone === 'info' ? 'i' : '!'}</span>
		{verdict.text}
	</p>

	<SolarChart months={sim.months} />

	<details class="how">
		<summary>Як ми рахуємо (припущення)</summary>
		<ul>
			<li>
				Генерація на 1 кВт — PVGIS для Полтави, середній рік; береться з розрахунку сервера й множиться на вибрану
				потужність.
			</li>
			<li>
				Удень будівля споживає {num(params.daytime * 100)} % своєї електроенергії; використати сама вона може лише
				цю частину. Решта генерації — надлишок, бо продавати його комунальний заклад зараз не може.
			</li>
			<li>
				Вартість = {num(params.fixed)} грн на об’єкт (проєкт, підключення) + {num(params.capex)} грн за кВт; тариф
				{num(params.tariff, 2)} грн/кВт·год.
			</li>
			<li>Окупність проста: без кредиту, інфляції та деградації панелей. Це оцінка, а не проєкт станції.</li>
		</ul>
	</details>
</section>

<style>
	.intro {
		margin-top: -0.25rem;
	}
	.controls {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
		gap: 1rem 1.5rem;
		margin-bottom: 1rem;
	}
	@media (max-width: 760px) {
		.controls {
			grid-template-columns: 1fr;
		}
	}
	.kwrow {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.kwrow input[type='range'] {
		flex: 1;
		accent-color: var(--sun-strong);
		min-width: 0;
	}
	.kwrow input[type='number'] {
		width: 7rem;
	}
	.roof input {
		width: 9rem;
	}
	.quick {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.4rem;
	}
	.chip {
		font: inherit;
		font-size: 0.8125rem;
		font-weight: 600;
		padding: 0.25rem 0.65rem;
		border-radius: 999px;
		border: 1px solid var(--line-strong);
		background: #fff;
		color: var(--text);
		cursor: pointer;
	}
	.chip[aria-pressed='true'] {
		background: var(--sun-soft);
		border-color: var(--sun-strong);
		color: var(--sun-ink);
	}
	.res {
		list-style: none;
		padding: 0;
		margin: 0 0 0.75rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 0.75rem;
	}
	.res li {
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 0.65rem 0.85rem;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		background: #fbfcfd;
	}
	.res li.warn {
		border-color: var(--sol-surplus);
		background: var(--warn-soft);
	}
	.res li.pb {
		border-color: var(--sol-self);
		background: var(--ok-soft);
	}
	.res span {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--muted);
	}
	.res strong {
		font-size: 1.35rem;
		font-variant-numeric: tabular-nums;
	}
	.res em {
		font-style: normal;
		font-size: 0.85rem;
		color: var(--muted);
		font-weight: 600;
	}
	.res small {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.verdict {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.6rem 0.85rem;
		border-radius: var(--radius);
		border: 1px solid var(--line);
		margin-bottom: 1rem;
	}
	.vi {
		flex: none;
		width: 1.35rem;
		height: 1.35rem;
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
	.how {
		margin-top: 0.75rem;
	}
	.how ul {
		margin: 0.5rem 0 0;
		padding-left: 1.2rem;
	}
</style>
