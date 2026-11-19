<script lang="ts">
	// Розрахунок СЕС для однієї будівлі: ключові цифри й помісячний графік генерації проти споживання
	import { page } from '$app/state';
	import { api, errMessage, ApiError, type SolarDetail } from '#lib/api.ts';
	import { num, MONTHS_FULL } from '#lib/format.ts';
	import SolarChart from '#lib/SolarChart.svelte';
	import Status from '#lib/Status.svelte';

	let data = $state<SolarDetail | null>(null);
	let error = $state<string | null>(null);
	let notReady = $state(false);
	let loading = $state(true);

	const id = $derived(page.params.id ?? '');
	const tariffQ = $derived(page.url.searchParams.get('tariff'));
	const capexQ = $derived(page.url.searchParams.get('capex'));

	async function load(bid: string, t: string | null, k: string | null) {
		loading = true;
		error = null;
		notReady = false;
		try {
			data = await api.solarOne(bid, { tariff: t ? Number(t) : null, capex: k ? Number(k) : null });
		} catch (e) {
			data = null;
			if (e instanceof ApiError && e.status === 404) notReady = true;
			else error = errMessage(e);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		load(id, tariffQ, capexQ);
	});

	const it = $derived(data?.item);
	const months = $derived(data ? [...data.monthly].sort((a, b) => a.month - b.month) : []);
	const sum = $derived({
		gen: months.reduce((s, m) => s + m.gen_kwh, 0),
		cons: months.reduce((s, m) => s + m.cons_kwh, 0),
		self: months.reduce((s, m) => s + m.self_kwh, 0),
		surplus: months.reduce((s, m) => s + m.surplus_kwh, 0)
	});
	const backQs = $derived(page.url.search);
</script>

<svelte:head><title>{it ? it.name : 'Розрахунок СЕС'} · City Insight Map · Енергія</title></svelte:head>

<p class="no-print back"><a href="/solar{backQs}">← До рейтингу нових СЕС</a></p>

<Status {loading} {error} retry={() => load(id, tariffQ, capexQ)} />

{#if notReady && !loading}
	<div class="notice notice-warn" role="status">
		<p><strong>Розрахунок ще не готовий.</strong> Для цієї будівлі ще немає оцінки сонячної станції (модуль доробляється або будівлю не знайдено). Спробуйте пізніше.</p>
	</div>
{/if}

{#if data && it && !loading}
	<div class="page-head">
		<div>
			<p class="muted kicker">Нова СЕС · {it.category_short}</p>
			<h1>{it.name}</h1>
			<p><a href="/building/{it.id}">Паспорт будівлі</a></p>
		</div>
		<button type="button" class="btn btn-secondary no-print" onclick={() => window.print()}>Друк / PDF</button>
	</div>

	<ul class="facts">
		<li><span>Рекомендована потужність</span><strong>{num(it.kw_recommended, 1)} кВт</strong><small>максимум за дахом: {num(it.kw_max_roof, 1)} кВт</small></li>
		<li><span>Генерація за рік</span><strong>{num(it.gen_kwh_year)} кВт·год</strong><small>споживання будівлі: {num(it.elec_kwh_year)} кВт·год</small></li>
		<li><span>Покриття потреби</span><strong>{it.coverage_pct !== null ? `${num(it.coverage_pct)} %` : '—'}</strong><small>частка електроенергії від власної СЕС</small></li>
		<li><span>Вартість монтажу</span><strong>{num(it.capex_uah)} грн</strong><small>площа даху ≈ {num(it.roof_area_m2)} м²</small></li>
		<li><span>Економія</span><strong>{num(it.savings_uah_year)} грн/рік</strong><small>на власному споживанні</small></li>
		<li><span>Проста окупність</span><strong>{it.payback_years !== null ? `${num(it.payback_years, 1)} року` : 'не окупається'}</strong><small>без урахування інфляції й деградації</small></li>
	</ul>

	<div class="notice notice-info">
		<p>
			Станцію підібрано <strong>під власне споживання будівлі</strong>: надлишок зараз не можна продати в
			мережу. За рік надлишок становитиме ≈ <strong>{num(it.surplus_kwh_year ?? sum.surplus)} кВт·год</strong>
			— у майбутньому його можна передавати іншим закладам через енергокооператив громади.
		</p>
	</div>

	<section class="card" aria-labelledby="chart-h">
		<h2 id="chart-h">Генерація і споживання по місяцях</h2>
		{#if months.length}
			<SolarChart {months} />
		{:else}
			<p class="muted">Помісячних даних немає.</p>
		{/if}
	</section>

	{#if months.length}
		<details class="card">
			<summary>Таблиця по місяцях</summary>
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
	}
	.facts {
		list-style: none;
		padding: 0;
		margin: 0 0 1.25rem;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
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
	.total th,
	.total td {
		font-weight: 700;
		border-top: 2px solid var(--line-strong);
	}
	details summary {
		margin-bottom: 0.75rem;
	}
</style>
