<script lang="ts">
	// Розрахунок СЕС для однієї будівлі: ключові цифри, сценарій «а якщо інша потужність», прогноз на завтра
	import { page } from '$app/state';
	import { getJSON, qs, errMessage, ApiError, type SolarDetail, type SolarList } from '#lib/api.ts';
	import { num, MONTHS_FULL } from '#lib/format.ts';
	import Status from '#lib/Status.svelte';
	import SolarScenario, { type ScenarioParams } from '#lib/SolarScenario.svelte';
	import ForecastCard from '#lib/ForecastCard.svelte';

	type ParamsX = SolarList['params'] & {
		capex_fixed_uah?: number;
		daytime_share?: number;
		roof_usable_share?: number;
		m2_per_kwp?: number;
	};

	let data = $state<SolarDetail | null>(null);
	let prm = $state<ParamsX | null>(null);
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
			const [d, list] = await Promise.all([
				getJSON<SolarDetail>(`/api/solar/${encodeURIComponent(bid)}${query}`),
				getJSON<SolarList>(`/api/solar${query}`).catch(() => null)
			]);
			data = d;
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
</script>

<svelte:head><title>{it ? it.name : 'Розрахунок СЕС'} · City Insight Map · Енергія</title></svelte:head>

<p class="no-print back"><a href="/solar{backQs}">← До переліку «Де ставити СЕС»</a></p>

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
				Нова СЕС · {it.category_short}
				{#if critical}<span class="pill pill-bad">критичний заклад</span>{/if}
				{#if it.rank}<span class="pill">№ {it.rank} за окупністю</span>{/if}
			</p>
			<h1>{it.name}</h1>
		</div>
		<div class="head-actions no-print">
			<a class="btn" href="/object/{it.id}">Відкрити об’єкт →</a>
			<button type="button" class="btn btn-secondary" onclick={() => window.print()}>Друк / PDF</button>
		</div>
	</div>

	<ul class="facts">
		<li><span>Рекомендована потужність</span><strong>{num(it.kw_recommended, 1)} кВт</strong><small>максимум за дахом: {num(it.kw_max_roof, 1)} кВт</small></li>
		<li><span>Генерація за рік</span><strong>{num(it.gen_kwh_year)} кВт·год</strong><small>споживання будівлі: {num(it.elec_kwh_year)} кВт·год</small></li>
		<li><span>Покриття потреби</span><strong>{it.coverage_pct !== null ? `${num(it.coverage_pct)} %` : '—'}</strong><small>частка електроенергії з власного сонця</small></li>
		<li><span>Вартість монтажу</span><strong>{num(it.capex_uah)} грн</strong><small>площа даху ≈ {num(it.roof_area_m2)} м²</small></li>
		<li><span>Економія</span><strong>{num(it.savings_uah_year)} грн/рік</strong><small>на власному споживанні</small></li>
		<li><span>Проста окупність</span><strong>{it.payback_years !== null ? `${num(it.payback_years, 1)} року` : 'не окупається'}</strong><small>без інфляції й деградації</small></li>
	</ul>

	<div class="notice notice-info">
		<p>
			Станцію підібрано <strong>під власне споживання будівлі</strong>: надлишок комунальний заклад зараз не може
			продати в мережу, тож більша станція коштує дорожче, а економить майже стільки ж. Влітку, коли сонця
			найбільше, генерація якраз дорівнює денному споживанню.
		</p>
	</div>

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
			<ForecastCard kw={scenKw ?? it.kw_recommended} />
			<p class="muted small side-note">
				Прогноз — для станції потужністю, вибраною в сценарії. Він показує, що сонячна генерація дуже
				залежить від погоди: у похмурий день вона може бути вчетверо меншою за норму.
			</p>
		</aside>
	</div>

	{#if months.length}
		<details class="card">
			<summary>Таблиця по місяцях (рекомендована потужність {num(it.kw_recommended, 1)} кВт)</summary>
			<div class="table-wrap">
				<table>
					<caption>Помісячний баланс, кВт·год</caption>
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
		</details>
	{/if}

	{#if data.assumptions?.length}
		<section class="card">
			<h2>Припущення розрахунку</h2>
			<ul>
				{#each data.assumptions as a, i (i)}<li>{a}</li>{/each}
			</ul>
			<p class="muted small">Це аналітична оцінка, а не проєкт станції.</p>
		</section>
	{/if}
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
	.facts {
		list-style: none;
		padding: 0;
		margin: 0 0 1.25rem;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
		gap: 1rem;
	}
	.facts li {
		background: var(--surface);
		border: 1px solid var(--line);
		border-top: 4px solid var(--sol-self);
		border-radius: var(--radius);
		padding: 0.85rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.facts span {
		color: var(--muted);
		font-size: 0.875rem;
		font-weight: 600;
	}
	.facts strong {
		font-size: 1.35rem;
		font-variant-numeric: tabular-nums;
	}
	.facts small {
		color: var(--muted);
		font-size: 0.8125rem;
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
		gap: 1.25rem;
		align-items: start;
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
			margin-bottom: 1.25rem;
		}
	}
	.total th,
	.total td {
		font-weight: 700;
		border-top: 2px solid var(--line-strong);
	}
	details summary {
		margin-bottom: 0.75rem;
	}
</style>
