<script lang="ts">
	// «Споживання електроенергії»: скільки електрики споживають комунальні будівлі громади і хто найбільше
	import { api, errMessage, type Summary, type Building } from '#lib/api.ts';
	import { num, pct, date, dateTime } from '#lib/format.ts';
	import Status from '#lib/Status.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Term from '#lib/Term.svelte';
	import { electricityRating, median, BASE_YEAR } from '../rating/electricity.ts';

	let data = $state<Summary | null>(null);
	let buildings = $state<Building[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);

	async function load() {
		loading = true;
		error = null;
		try {
			[data, buildings] = await Promise.all([api.summary(), api.buildings()]);
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	load();

	const base = $derived(data?.years[BASE_YEAR]);
	const partial = $derived(data ? Object.entries(data.years).filter(([, y]) => y.partial) : []);
	const updated = $derived.by(() => {
		if (!data) return null;
		const dates = [...Object.values(data.years).map((y) => y.created), ...data.sources.map((s) => s.created)].filter(
			(d): d is string => !!d
		);
		return dates.sort().at(-1) ?? null;
	});

	/** 4 874 090 → «4,87 млн» */
	function mln(v: number | null | undefined): string {
		if (v === null || v === undefined) return '—';
		return v >= 1e6 ? `${num(v / 1e6, 2)} млн` : num(v);
	}

	const rating = $derived(electricityRating(buildings));
	const withElec = $derived(buildings.filter((b) => (b.years[BASE_YEAR]?.elec_kwh ?? 0) > 0));
	const totalElec = $derived(withElec.reduce((s, b) => s + (b.years[BASE_YEAR]?.elec_kwh ?? 0), 0));
	const typical = $derived(
		median([...rating.rows.values()].filter((r) => !r.excluded && r.kwhM2 !== null).map((r) => r.kwhM2!))
	);

	const byCategory = $derived.by(() => {
		const m = new Map<string, { count: number; kwh: number }>();
		for (const b of buildings) {
			const e = m.get(b.category_short) ?? { count: 0, kwh: 0 };
			e.count++;
			e.kwh += b.years[BASE_YEAR]?.elec_kwh ?? 0;
			m.set(b.category_short, e);
		}
		return [...m.entries()]
			.map(([name, e]) => ({ name, ...e, share: totalElec ? e.kwh / totalElec : 0, med: rating.medians[name] ?? null }))
			.sort((a, b) => b.kwh - a.kwh);
	});
	const catMax = $derived(Math.max(1, ...byCategory.map((c) => c.kwh)));

	const top = $derived(
		[...withElec]
			.sort((a, b) => (b.years[BASE_YEAR]?.elec_kwh ?? 0) - (a.years[BASE_YEAR]?.elec_kwh ?? 0))
			.slice(0, 10)
	);
	const topShare = $derived(
		totalElec ? top.reduce((s, b) => s + (b.years[BASE_YEAR]?.elec_kwh ?? 0), 0) / totalElec : 0
	);
</script>

<svelte:head><title>Споживання електроенергії · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Споживання електроенергії</h1>
		<p class="lead">
			Скільки електроенергії за рік споживають комунальні будівлі громади, які категорії й будівлі
			споживають найбільше. Це основа для рішень, де ставити сонячні станції й акумулятори.
		</p>
	</div>
	{#if updated}
		<p class="muted">Дані <Term key="UMUNI" /> від <strong>{dateTime(updated)}</strong></p>
	{/if}
</div>

{#if loading}
	<Skeleton variant="page" count={4} rows={6} />
{/if}
<Status loading={false} {error} retry={load} />

{#if data && !loading && !error}
	<section aria-labelledby="kpi-h">
		<h2 id="kpi-h" class="visually-hidden">Ключові показники</h2>
		<ul class="kpis">
			<li class="kpi kpi-main">
				<span class="kpi-label">Електроенергія за {BASE_YEAR} рік</span>
				<span class="kpi-value">{mln(base?.elec_kwh)} <span class="kpi-unit"><Term key="кВт·год" plain /></span></span>
				<span class="kpi-note">усі лічильники {num(withElec.length)} будівель</span>
			</li>
			{#each partial as [year, y] (year)}
				<li class="kpi kpi-warn">
					<span class="kpi-label">{year} рік — поки неповний</span>
					<span class="kpi-value">{mln(y.elec_kwh)} <span class="kpi-unit">кВт·год</span></span>
					<span class="kpi-note">дані охоплюють ≈ {pct(y.coverage)} року (до {date(y.created)})</span>
				</li>
			{/each}
			<li class="kpi">
				<span class="kpi-label">
					Типове <Term key="питоме споживання">споживання на 1 м²</Term>
				</span>
				<span class="kpi-value">{num(typical, 1)} <span class="kpi-unit">кВт·год/м²</span></span>
				<span class="kpi-note">медіана по всіх будівлях у рейтингу, {BASE_YEAR}</span>
			</li>
			<li class="kpi">
				<span class="kpi-label">Будівель у базі</span>
				<span class="kpi-value">{num(data.buildings)}</span>
				<span class="kpi-note">
					без даних про електрику: {num(data.buildings - withElec.length)} — <a href="/defects">якість даних</a>
				</span>
			</li>
		</ul>
	</section>

	{#each partial as [year, y] (year)}
		<div class="notice notice-info">
			<p>
				<strong>Чому {year} рік не порівнюємо напряму.</strong> Вивантаження від {date(y.created)}
				охоплює лише ≈ {pct(y.coverage)} року, тому всі порівняння й рейтинг рахуємо за повним
				{BASE_YEAR} роком. Якщо решта {year} року йтиме так само, за рік вийде приблизно
				<strong>{mln(y.elec_kwh / y.coverage)} кВт·год</strong>
				{#if base?.elec_kwh}
					({y.elec_kwh / y.coverage >= base.elec_kwh ? 'більше' : 'менше'}, ніж у {BASE_YEAR}, на
					{pct(Math.abs(y.elec_kwh / y.coverage / base.elec_kwh - 1))}){/if} — це груба оцінка.
			</p>
		</div>
	{/each}

	<div class="grid-2">
		<section class="card" aria-labelledby="cat-h">
			<h2 id="cat-h">За категоріями будівель, {BASE_YEAR}</h2>
			<div class="table-wrap">
				<table>
					<caption class="visually-hidden">Споживання електроенергії за категоріями будівель</caption>
					<thead>
						<tr>
							<th scope="col">Категорія</th>
							<th scope="col" class="num">Будівель</th>
							<th scope="col">Електроенергія, <span class="unit">кВт·год</span></th>
							<th scope="col" class="num">
								<Term key="медіана категорії">Медіана</Term>, <span class="unit">кВт·год/м²</span>
							</th>
						</tr>
					</thead>
					<tbody>
						{#each byCategory as c (c.name)}
							<tr>
								<th scope="row"><a href="/rating?cat={encodeURIComponent(c.name)}">{c.name}</a></th>
								<td class="num">{num(c.count)}</td>
								<td>
									<span class="cat-val"><span class="tnum">{num(c.kwh)}</span> <span class="muted small">· {pct(c.share)}</span></span>
									<span class="cat-track" aria-hidden="true"><span class="cat-fill" style="width:{(c.kwh / catMax) * 100}%"></span></span>
								</td>
								<td class="num">{num(c.med, 1)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="muted small note">
				Медіану порівнюйте лише всередині категорії: лікарня з цілодобовим обладнанням закономірно
				споживає на 1 м² більше, ніж музей.
			</p>
		</section>

		<section class="card" aria-labelledby="top-h">
			<h2 id="top-h">10 найбільших споживачів, {BASE_YEAR}</h2>
			<p class="muted small">
				Разом — <strong>{pct(topShare)}</strong> усієї електроенергії громади. Тут сонячна станція
				дасть найбільшу економію в гривнях.
			</p>
			<ol class="top">
				{#each top as b, i (b.id)}
					{@const r = rating.rows.get(b.id)}
					<li>
						<span class="top-n">{i + 1}</span>
						<span class="top-txt">
							<a href="/object/{b.id}">{b.name}</a>
							<span class="muted small">
								{b.category_short}{#if r?.kwhM2} · {num(r.kwhM2, 1)} кВт·год/м²{/if}
							</span>
						</span>
						<span class="top-v tnum">{num(b.years[BASE_YEAR]?.elec_kwh)} <span class="unit">кВт·год</span></span>
					</li>
				{/each}
			</ol>
			<p class="small"><a href="/solar">Де ставити СЕС →</a></p>
		</section>
	</div>

	<details class="card sources">
		<summary>Джерела даних ({data.sources.length} файли)</summary>
		<p class="muted small">
			Вивантаження з UMUNI, на яких зроблено розрахунок. Щоб оновити — завантажте новий файл на
			сторінці <a href="/upload">«Оновити дані»</a>.
		</p>
		<div class="table-wrap">
			<table>
				<caption class="visually-hidden">Файли джерел даних</caption>
				<thead>
					<tr>
						<th scope="col">Файл</th>
						<th scope="col">Вміст</th>
						<th scope="col" class="num">Рядків</th>
						<th scope="col">Дата вивантаження</th>
					</tr>
				</thead>
				<tbody>
					{#each data.sources as s (s.file)}
						<tr>
							<td><code>{s.file}</code></td>
							<td>{s.kind}</td>
							<td class="num">{num(s.rows)}</td>
							<td>{s.created ? dateTime(s.created) : '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</details>
{/if}

<style>
	.kpis {
		list-style: none;
		padding: 0;
		margin: 0 0 1.25rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
		gap: 1rem;
	}
	.kpi {
		background: var(--surface);
		border: 1px solid var(--line);
		border-top: 4px solid var(--navy-3);
		border-radius: var(--radius);
		padding: 1rem 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		box-shadow: var(--shadow);
	}
	.kpi-main {
		border-top-color: var(--sun);
	}
	.kpi-warn {
		border-top-color: #b8c2cf;
	}
	.kpi-label {
		font-size: 0.9rem;
		color: var(--muted);
		font-weight: 600;
	}
	.kpi-value {
		font-size: 1.85rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		line-height: 1.2;
	}
	.kpi-unit {
		font-size: 1rem;
		font-weight: 500;
		color: var(--muted);
	}
	.kpi-note {
		font-size: 0.875rem;
		color: var(--muted);
	}
	.cat-val {
		display: block;
		white-space: nowrap;
	}
	.cat-track {
		display: block;
		height: 6px;
		margin-top: 0.3rem;
		border-radius: 3px;
		background: #eef2f6;
		min-width: 8rem;
	}
	.cat-fill {
		display: block;
		height: 100%;
		border-radius: 3px;
		background: var(--sun);
	}
	tbody th {
		font-weight: 600;
	}
	.note {
		margin: 0.75rem 0 0;
	}
	.top {
		list-style: none;
		margin: 0 0 0.75rem;
		padding: 0;
	}
	.top li {
		display: grid;
		grid-template-columns: 2rem 1fr max-content;
		gap: 0.75rem;
		align-items: center;
		padding: 0.5rem 0;
		border-bottom: 1px solid #edf0f4;
	}
	.top-n {
		display: grid;
		place-items: center;
		width: 1.8rem;
		height: 1.8rem;
		border-radius: 50%;
		background: #eef2f6;
		font-weight: 700;
		font-size: 0.875rem;
	}
	.top-txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.top-v {
		font-weight: 600;
		white-space: nowrap;
	}
	.sources {
		margin-top: 1.25rem;
	}
	code {
		font-size: 0.875rem;
	}
	@media (max-width: 520px) {
		.top li {
			grid-template-columns: 2rem 1fr;
		}
		.top-v {
			grid-column: 2;
		}
	}
</style>
