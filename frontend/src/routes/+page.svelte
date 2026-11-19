<script lang="ts">
	// Сторінка «Огляд»: ключові показники громади, розподіл класів, категорії, джерела даних
	import { api, errMessage, type Summary } from '#lib/api.ts';
	import { num, pct, date, dateTime } from '#lib/format.ts';
	import ClassChart from '#lib/ClassChart.svelte';
	import Status from '#lib/Status.svelte';

	let data = $state<Summary | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	async function load() {
		loading = true;
		error = null;
		try {
			data = await api.summary();
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	load();

	const baseYear = $derived(data?.base_year ? String(data.base_year) : '2025');
	const base = $derived(data?.years[baseYear]);
	// Неповні роки (зазвичай поточний 2026)
	const partialYears = $derived(
		data ? Object.entries(data.years).filter(([, y]) => y.partial) : []
	);
	// Найсвіжіша дата вивантаження серед усіх файлів
	const updated = $derived.by(() => {
		if (!data) return null;
		const dates = [
			...Object.values(data.years).map((y) => y.created),
			...data.sources.map((s) => s.created)
		].filter((d): d is string => !!d);
		return dates.sort().at(-1) ?? null;
	});
	const categories = $derived(
		data ? Object.entries(data.categories).sort((a, b) => b[1].count - a[1].count) : []
	);
</script>

<svelte:head><title>Огляд · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Огляд енергоспоживання</h1>
		<p class="lead">
			Комунальні будівлі громади: скільки споживають тепла, електроенергії й газу та які з них
			найменш ефективні.
		</p>
	</div>
	{#if updated}
		<p class="muted">Дані оновлено: <strong>{dateTime(updated)}</strong></p>
	{/if}
</div>

<Status {loading} {error} retry={load} />

{#if data && !loading}
	<section aria-labelledby="kpi-h">
		<h2 id="kpi-h" class="visually-hidden">Ключові показники</h2>
		<ul class="kpis">
			<li class="kpi">
				<span class="kpi-label">Будівель у базі</span>
				<span class="kpi-value">{num(data.buildings)}</span>
				<span class="kpi-note">з реєстру та річних звітів UMUNI</span>
			</li>
			<li class="kpi">
				<span class="kpi-label">У рейтингу</span>
				<span class="kpi-value">{num(data.in_rating)}</span>
				<span class="kpi-note">
					ще {num(data.buildings - data.in_rating)} виключено з причиною — <a href="/rating">див. рейтинг</a>
				</span>
			</li>
			<li class="kpi">
				<span class="kpi-label">Тепло, {baseYear}</span>
				<span class="kpi-value">{num(base?.heat_gcal)} <span class="kpi-unit">Гкал</span></span>
				<span class="kpi-note">теплова енергія від мереж</span>
			</li>
			<li class="kpi">
				<span class="kpi-label">Електроенергія, {baseYear}</span>
				<span class="kpi-value">{num(base?.elec_kwh)} <span class="kpi-unit">кВт·год</span></span>
				<span class="kpi-note">усі лічильники будівель</span>
			</li>
			<li class="kpi">
				<span class="kpi-label">Газ, {baseYear}</span>
				<span class="kpi-value">{num(base?.gas_m3)} <span class="kpi-unit">м³</span></span>
				<span class="kpi-note">природний газ</span>
			</li>
			<li class="kpi kpi-warn">
				<span class="kpi-label">Дефектів даних</span>
				<span class="kpi-value">{num(data.defects)}</span>
				<span class="kpi-note">на {num(data.defect_buildings)} будівлях — <a href="/defects">перелік</a></span>
			</li>
		</ul>
		<p class="muted small">
			Усього енергії за {baseYear}: <strong>{num(base?.total_mwh)} МВт·год</strong> (тепло, електроенергія
			й газ, перераховані в МВт·год: 1 Гкал = {num(data.coefficients.GCAL_TO_MWH, 3)} МВт·год,
			1 м³ газу ≈ {num(data.coefficients.GAS_KWH_PER_M3, 1)} кВт·год).
		</p>
	</section>

	{#each partialYears as [year, y] (year)}
		<div class="notice notice-warn">
			<p>
				<strong>Дані за {year} рік неповні.</strong> Вивантаження від {date(y.created)} охоплює
				приблизно {pct(y.coverage)} року. Тому рейтинг і класи рахуються за {baseYear} роком, а
				{year} показуємо лише для порівняння. Зараз за {year}: тепло {num(y.heat_gcal)} Гкал,
				електроенергія {num(y.elec_kwh)} кВт·год, газ {num(y.gas_m3)} м³.
			</p>
		</div>
	{/each}

	<div class="grid-2">
		<section class="card" aria-labelledby="cls-h">
			<h2 id="cls-h">Розподіл будівель за класами</h2>
			<ClassChart counts={data.classes} title="Кількість будівель за умовними класами A–G, {baseYear} рік" />
		</section>

		<section class="card" aria-labelledby="cat-h">
			<h2 id="cat-h">Категорії будівель</h2>
			<div class="table-wrap">
				<table>
					<caption>
						Медіана питомого споживання за {baseYear} рік
						<span class="muted">(усі види енергії, кВт·год на 1 м² опалюваної площі)</span>
					</caption>
					<thead>
						<tr>
							<th scope="col">Категорія</th>
							<th scope="col" class="num">Будівель</th>
							<th scope="col" class="num">У рейтингу</th>
							<th scope="col" class="num">Медіана, <span class="unit">кВт·год/м²</span></th>
						</tr>
					</thead>
					<tbody>
						{#each categories as [name, c] (name)}
							<tr>
								<th scope="row"><a href="/rating?cat={encodeURIComponent(name)}">{name}</a></th>
								<td class="num">{num(c.count)}</td>
								<td class="num">{num(c.in_rating)}</td>
								<td class="num">{num(c.median_kwh_m2, 1)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	</div>

	<section class="card sources" aria-labelledby="src-h">
		<h2 id="src-h">Джерела даних</h2>
		<p class="muted">
			Файли-вивантаження з UMUNI, на яких зроблено розрахунок. Щоб оновити — завантажте новий
			файл на сторінці <a href="/upload">«Оновити дані»</a>.
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
	</section>
{/if}

<style>
	.kpis {
		list-style: none;
		padding: 0;
		margin: 0 0 0.75rem;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
		gap: 1rem;
	}
	.kpi {
		background: var(--surface);
		border: 1px solid var(--line);
		border-top: 4px solid var(--accent);
		border-radius: var(--radius);
		padding: 0.9rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		box-shadow: var(--shadow);
	}
	.kpi-warn {
		border-top-color: var(--warn);
	}
	.kpi-label {
		font-size: 0.875rem;
		color: var(--muted);
		font-weight: 600;
	}
	.kpi-value {
		font-size: 1.6rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		line-height: 1.2;
	}
	.kpi-unit {
		font-size: 0.95rem;
		font-weight: 500;
		color: var(--muted);
	}
	.kpi-note {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.sources {
		margin-top: 1.25rem;
	}
	code {
		font-size: 0.875rem;
	}
</style>
