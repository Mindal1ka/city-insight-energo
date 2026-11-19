<script lang="ts">
	// Розрахунок СЕС для однієї будівлі: відповідь одним реченням → повзунок «а якщо інша станція» → прогноз на завтра.
	// Технічні цифри — у розкривних блоках унизу.
	import { page } from '$app/state';
	import { getJSON, qs, errMessage, ApiError, type SolarDetail, type SolarList } from '#lib/api.ts';
	import type { IndependenceItem } from '#lib/api-independence.ts';
	import { num, MONTHS_FULL } from '#lib/format.ts';
	import Status from '#lib/Status.svelte';
	import SolarScenario, { paybackWords, type ScenarioParams } from '#lib/SolarScenario.svelte';
	import ForecastCard from '#lib/ForecastCard.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import { fadeUp } from '#lib/motion.ts';

	type ParamsX = SolarList['params'] & {
		capex_fixed_uah?: number;
		daytime_share?: number;
		roof_usable_share?: number;
		m2_per_kwp?: number;
	};

	let data = $state<SolarDetail | null>(null);
	let prm = $state<ParamsX | null>(null);
	/** Наявна станція (ДЕМО-реєстр) — щоб не радити ставити «з нуля» там, де СЕС уже є */
	let exist = $state<IndependenceItem | null>(null);
	let error = $state<string | null>(null);
	let notReady = $state(false);
	let loading = $state(true);
	let scenKw = $state<number | null>(null);

	const id = $derived(page.params.id ?? '');
	const q = $derived({
		tariff: page.url.searchParams.get('tariff'),
		capex: page.url.searchParams.get('capex'),
		fixed: page.url.searchParams.get('fixed')
	});

	async function load(bid: string, p: { tariff: string | null; capex: string | null; fixed: string | null }) {
		loading = true;
		error = null;
		notReady = false;
		const query = qs(p);
		try {
			const [d, list, ie] = await Promise.all([
				getJSON<SolarDetail>(`/api/solar/${encodeURIComponent(bid)}${query}`),
				getJSON<SolarList>(`/api/solar${query}`).catch(() => null),
				getJSON<{ item: IndependenceItem }>(`/api/independence/${encodeURIComponent(bid)}`).catch(() => null)
			]);
			data = d;
			exist = ie?.item ?? null;
			prm = (d.params ?? list?.params ?? null) as ParamsX | null;
		} catch (e) {
			data = null;
			if (e instanceof ApiError && e.status === 404) notReady = true;
			else error = errMessage(e);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		load(id, q);
	});

	const it = $derived(data?.item);
	const months = $derived(data ? [...data.monthly].sort((a, b) => a.month - b.month) : []);
	const sum = $derived({
		gen: months.reduce((s, m) => s + m.gen_kwh, 0),
		cons: months.reduce((s, m) => s + m.cons_kwh, 0),
		self: months.reduce((s, m) => s + m.self_kwh, 0),
		surplus: months.reduce((s, m) => s + m.surplus_kwh, 0)
	});
	// Параметри для сценарію; якщо список недоступний — відновлюємо з цифр самої будівлі
	const sp = $derived.by<ScenarioParams | null>(() => {
		if (!it) return null;
		const tariff =
			prm?.tariff_uah_kwh ??
			(it.self_consumed_kwh_year && it.savings_uah_year ? it.savings_uah_year / it.self_consumed_kwh_year : 8);
		return {
			tariff,
			capex: prm?.capex_uah_per_kw ?? 30000,
			fixed: prm?.capex_fixed_uah ?? 60000,
			daytime: prm?.daytime_share ?? 0.6
		};
	});
	const backQs = $derived(page.url.search);
	const critical = $derived(it?.category_short === "Охорона здоров'я");

	// ——— Відповідь одним реченням ———
	const money = (v: number | null | undefined) =>
		v === null || v === undefined ? '—' : v >= 1e6 ? `${num(v / 1e6, 2)} млн грн` : `${num(Math.round(v / 1000))} тис. грн`;
	const kwTxt = (v: number) => num(v, v < 10 ? 1 : 0);
	const answer = $derived.by(() => {
		if (!it || !sp) return null;
		if (exist?.has_ses && exist.ses_kw) {
			const add = exist.potential_add_kw ?? 0;
			if (add <= 0)
				return {
					tone: 'ok',
					main: `Тут уже працює станція ${kwTxt(exist.ses_kw)} кВт — цього достатньо.`,
					sub: `Вона покриває ${num(exist.self_sufficiency_pct, 1)} % потреби будівлі. Більша станція виробляла б надлишок, який заклад не може продати.`
				};
			const gain = Math.max(
				0,
				(((exist.potential_self_sufficiency_pct ?? 0) - (exist.self_sufficiency_pct ?? 0)) / 100) * (exist.elec_kwh_year ?? 0)
			);
			const cost = sp.fixed + add * sp.capex;
			const save = gain * sp.tariff;
			return {
				tone: 'ok',
				main: `Тут уже є станція ${kwTxt(exist.ses_kw)} кВт. Варто додати ще ${kwTxt(add)} кВт: разом покриють ${num(exist.potential_self_sufficiency_pct)} % потреби, доповнення ${paybackWords(save > 0 ? cost / save : null)}.`,
				sub: `Доповнення коштуватиме ≈ ${money(cost)} і заощаджуватиме ≈ ${money(save)} на рік. Повзунок нижче показує станцію загалом.`
			};
		}
		if (it.payback_years === null)
			return { tone: 'warn', main: 'Сонячна станція тут не окупиться.', sub: 'Будівля споживає вдень замало електроенергії.' };
		return {
			tone: 'ok',
			main: `Тут варто поставити ${kwTxt(it.kw_recommended ?? 0)} кВт: покриє ${num(it.coverage_pct)} % потреби, ${paybackWords(it.payback_years)}.`,
			sub: `Коштуватиме ≈ ${money(it.capex_uah)}, заощаджуватиме ≈ ${money(it.savings_uah_year)} на рік.`
		};
	});
</script>

<svelte:head><title>{it ? it.name : 'Розрахунок СЕС'} · City Insight Map · Енергія</title></svelte:head>

<p class="no-print back"><a href="/solar{backQs}" data-sveltekit-reset="false">← До переліку «Де ставити СЕС»</a></p>

<Status {loading} {error} retry={() => load(id, q)} />

{#if notReady && !loading}
	<div class="notice notice-warn" role="status">
		<p>
			<strong>Розрахунку для цієї будівлі немає.</strong>
			Ймовірно, будівлю не оцінено (немає даних про електроенергію чи площу) або її не знайдено.
			<a href="/object/{id}">Відкрити об’єкт</a>
		</p>
	</div>
{/if}

{#if data && it && !loading}
	<div class="page-head">
		<div>
			<p class="muted kicker">
				Сонячна станція · {it.category_short}
				{#if critical}<span class="pill pill-bad"><span aria-hidden="true">✚</span> критичний заклад</span>{/if}
				{#if it.rank}<span class="pill">№ {it.rank} за окупністю</span>{/if}
			</p>
			<h1>{it.name}</h1>
		</div>
		<div class="head-actions no-print">
			<a class="btn" href="/object/{it.id}">Відкрити об’єкт →</a>
			<button type="button" class="btn btn-secondary" onclick={() => window.print()}>Друк / PDF</button>
		</div>
	</div>

	{#if answer}
		<div class="answer a-{answer.tone}" in:fadeUp={{ y: 10, duration: 420 }}>
			<span class="a-ico" aria-hidden="true">
				{#if answer.tone === 'ok'}
					<svg viewBox="0 0 24 24" width="26" height="26"><circle cx="12" cy="12" r="4.4" /><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" /></svg>
				{:else}!{/if}
			</span>
			<div>
				<p class="a-main">{answer.main}</p>
				<p class="a-sub">{answer.sub}</p>
			</div>
		</div>
	{/if}

	<div class="layout">
		<div class="main-col">
			{#if sp && months.length}
				<SolarScenario
					item={it}
					monthly={months}
					params={sp}
					usableShare={prm?.roof_usable_share ?? 0.5}
					m2PerKw={prm?.m2_per_kwp ?? 6}
					bind:kw={scenKw}
				/>
			{:else}
				<p class="muted">Помісячних даних немає.</p>
			{/if}
		</div>
		<aside class="side-col">
			<Reveal delay={120}>
				<ForecastCard kw={scenKw ?? it.kw_recommended} />
			</Reveal>
			<p class="muted small side-note">Прогноз — для станції, яку ви вибрали повзунком.</p>
		</aside>
	</div>

	<section class="card more" aria-labelledby="more-h">
		<h2 id="more-h">Подробиці розрахунку</h2>
		<p class="muted small more-lead">
			Станцію підібрано <strong>під власне споживання будівлі</strong>: надлишок комунальний заклад не може продати,
			тож більша станція коштує дорожче, а заощаджує майже стільки ж.
		</p>
		{#if months.length}
			<Disclosure summary="Таблиця по місяцях" hint="рекомендована станція {num(it.kw_recommended, 1)} кВт">
				<div class="table-wrap">
					<table>
						<caption class="visually-hidden">Помісячний баланс, кВт·год</caption>
						<thead>
							<tr>
								<th scope="col">Місяць</th>
								<th scope="col" class="num">Споживання, <span class="unit">кВт·год</span></th>
								<th scope="col" class="num">Генерація, <span class="unit">кВт·год</span></th>
								<th scope="col" class="num">Використано будівлею, <span class="unit">кВт·год</span></th>
								<th scope="col" class="num">Надлишок, <span class="unit">кВт·год</span></th>
							</tr>
						</thead>
						<tbody>
							{#each months as m (m.month)}
								<tr>
									<th scope="row">{MONTHS_FULL[m.month - 1]}</th>
									<td class="num">{num(m.cons_kwh)}</td>
									<td class="num">{num(m.gen_kwh)}</td>
									<td class="num">{num(m.self_kwh)}</td>
									<td class="num">{num(m.surplus_kwh)}</td>
								</tr>
							{/each}
							<tr class="total">
								<th scope="row">Разом за рік</th>
								<td class="num">{num(sum.cons)}</td>
								<td class="num">{num(sum.gen)}</td>
								<td class="num">{num(sum.self)}</td>
								<td class="num">{num(sum.surplus)}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</Disclosure>
		{/if}
		<Disclosure summary="Технічні дані будівлі">
			<dl class="facts">
				<div><dt>Рекомендована потужність</dt><dd>{num(it.kw_recommended, 1)} кВт</dd></div>
				<div><dt>Максимум за дахом</dt><dd>{num(it.kw_max_roof, 1)} кВт (дах ≈ {num(it.roof_area_m2)} м²)</dd></div>
				<div><dt>Генерація за рік</dt><dd>{num(it.gen_kwh_year)} кВт·год</dd></div>
				<div><dt>Споживання будівлі</dt><dd>{num(it.elec_kwh_year)} кВт·год/рік</dd></div>
				<div><dt>Вартість монтажу</dt><dd>{num(it.capex_uah)} грн</dd></div>
				<div><dt>Економія</dt><dd>{num(it.savings_uah_year)} грн/рік</dd></div>
				<div><dt>Проста окупність</dt><dd>{it.payback_years !== null ? `${num(it.payback_years, 1)} року` : 'не окупається'}</dd></div>
				{#if exist?.has_ses}
					<div>
						<dt>Наявна станція (ДЕМО-дані)</dt>
						<dd>{num(exist.ses_kw, 1)} кВт{exist.battery_kwh ? `, акумулятор ${num(exist.battery_kwh, 1)} кВт·год` : ''}</dd>
					</div>
				{/if}
			</dl>
		</Disclosure>
		{#if data.assumptions?.length}
			<Disclosure summary="Припущення розрахунку" hint="{data.assumptions.length} пунктів">
				<ul class="assume">
					{#each data.assumptions as a, i (i)}<li>{a}</li>{/each}
				</ul>
				<p class="muted small">Це аналітична оцінка, а не проєкт станції.</p>
			</Disclosure>
		{/if}
	</section>
{/if}

<style>
	.back {
		margin: 0 0 0.75rem;
	}
	.kicker {
		margin: 0 0 0.25rem;
		font-weight: 600;
		font-size: 0.9rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	h1 {
		max-width: 60ch;
	}
	.head-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.head-actions .btn {
		text-decoration: none;
	}
	.answer {
		display: flex;
		gap: 1rem;
		align-items: flex-start;
		padding: 1.1rem 1.35rem;
		margin: 0 0 1.25rem;
		border-radius: var(--radius-lg);
		border: 1px solid #f0d9a8;
		background: linear-gradient(100deg, var(--sun-soft) 0%, #fff 75%);
		box-shadow: var(--shadow-md);
	}
	.a-warn {
		border-color: var(--warn);
		background: var(--warn-soft);
	}
	.a-ico {
		flex: none;
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--sun);
		color: #5a3300;
		font-weight: 800;
		font-size: 1.3rem;
	}
	.a-ico svg {
		fill: #fff3d6;
		stroke: #6d3f00;
		stroke-width: 1.8;
		stroke-linecap: round;
	}
	@media (prefers-reduced-motion: no-preference) {
		.a-ico svg {
			animation: spin 30s linear infinite;
		}
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.a-main {
		margin: 0 0 0.25rem;
		font-size: clamp(1.15rem, 2vw, 1.45rem);
		font-weight: 700;
		line-height: 1.3;
		max-width: 60ch;
		text-wrap: pretty;
	}
	.a-sub {
		margin: 0;
		color: var(--muted);
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
		gap: 1.25rem;
		align-items: start;
		margin-bottom: 1.25rem;
	}
	.main-col :global(.card) {
		margin: 0;
	}
	.side-col {
		position: sticky;
		top: 1rem;
	}
	.side-note {
		margin-top: 0.6rem;
	}
	@media (max-width: 1100px) {
		.layout {
			grid-template-columns: 1fr;
		}
		.side-col {
			position: static;
		}
	}
	.more h2 {
		margin-bottom: 0.25rem;
	}
	.more-lead {
		max-width: 80ch;
		margin: 0 0 0.25rem;
	}
	.total th,
	.total td {
		font-weight: 700;
		border-top: 2px solid var(--line-strong);
	}
	.facts {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
		gap: 0.6rem 1.25rem;
		margin: 0;
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
	.assume {
		margin: 0 0 0.5rem;
		padding-left: 1.2rem;
	}
</style>
