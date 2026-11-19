<script lang="ts">
	// Сторінка «Нові СЕС»: де вигідно ставити сонячні станції, рейтинг за терміном окупності
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api, errMessage, ApiError, type SolarList, type Summary } from '#lib/api.ts';
	import { num } from '#lib/format.ts';
	import Status from '#lib/Status.svelte';

	let data = $state<SolarList | null>(null);
	let summary = $state<Summary | null>(null);
	let error = $state<string | null>(null);
	let notReady = $state(false);
	let loading = $state(true);

	// Параметри з адреси (?category=&tariff=&capex=), щоб посилання на картку зберігали розрахунок
	const category = $derived(page.url.searchParams.get('category') ?? '');
	const tariffQ = $derived(page.url.searchParams.get('tariff'));
	const capexQ = $derived(page.url.searchParams.get('capex'));

	// Поля форми (заповнюються значеннями за замовчуванням із відповіді API)
	let tariff = $state<number | null>(null);
	let capex = $state<number | null>(null);
	let cat = $state('');

	async function load(c: string, t: string | null, k: string | null) {
		loading = true;
		error = null;
		notReady = false;
		try {
			data = await api.solar({ category: c, tariff: t ? Number(t) : null, capex: k ? Number(k) : null });
			tariff = data.params.tariff_uah_kwh;
			capex = data.params.capex_uah_per_kw;
			cat = c;
		} catch (e) {
			data = null;
			if (e instanceof ApiError && e.status === 404) notReady = true;
			else error = errMessage(e);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		load(category, tariffQ, capexQ);
	});

	// Список категорій беремо з огляду (працює, навіть якщо розрахунок СЕС ще не готовий)
	api.summary().then((s) => (summary = s)).catch(() => {});
	const categories = $derived(summary ? Object.keys(summary.categories).sort() : []);

	// Сортування за окупністю: найшвидша — першою; без окупності — в кінці
	const items = $derived(
		data
			? [...data.items].sort(
					(a, b) => (a.payback_years ?? Infinity) - (b.payback_years ?? Infinity) || (a.rank ?? 0) - (b.rank ?? 0)
				)
			: []
	);
	const totals = $derived({
		kw: items.reduce((s, i) => s + (i.kw_recommended ?? 0), 0),
		capex: items.reduce((s, i) => s + (i.capex_uah ?? 0), 0),
		save: items.reduce((s, i) => s + (i.savings_uah_year ?? 0), 0)
	});

	function submit(e: SubmitEvent) {
		e.preventDefault();
		const p = new URLSearchParams();
		if (cat) p.set('category', cat);
		if (tariff) p.set('tariff', String(tariff));
		if (capex) p.set('capex', String(capex));
		goto(`/solar?${p}`, { reset: false });
	}

	const detailQs = $derived.by(() => {
		const p = new URLSearchParams();
		if (tariffQ) p.set('tariff', tariffQ);
		if (capexQ) p.set('capex', capexQ);
		const s = p.toString();
		return s ? `?${s}` : '';
	});
</script>

<svelte:head><title>Нові СЕС · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Де ставити нові сонячні станції</h1>
		<p class="lead">
			Для кожної будівлі беремо реальне споживання електроенергії, оцінюємо площу даху й можливу
			генерацію та рахуємо, за скільки років станція окупиться.
		</p>
	</div>
</div>

<div class="notice notice-info">
	<p>
		<strong>Станцію підбираємо під власне споживання будівлі,</strong> бо надлишок електроенергії
		комунальні заклади зараз законодавчо не можуть продати в мережу. Більша станція не дасть більшої
		економії — надлишок просто пропаде.
	</p>
</div>

<form class="card toolbar params" onsubmit={submit}>
	<div class="field">
		<label for="s-cat">Категорія</label>
		<select id="s-cat" bind:value={cat}>
			<option value="">Усі категорії</option>
			{#each categories as c (c)}<option value={c}>{c}</option>{/each}
		</select>
	</div>
	<div class="field">
		<label for="s-tariff">Тариф на електроенергію, грн/кВт·год</label>
		<input id="s-tariff" type="number" min="0.1" step="0.01" bind:value={tariff} inputmode="decimal" />
	</div>
	<div class="field">
		<label for="s-capex">Вартість монтажу СЕС, грн/кВт</label>
		<input id="s-capex" type="number" min="1000" step="500" bind:value={capex} inputmode="decimal" />
	</div>
	<button class="btn" type="submit">Перерахувати</button>
</form>

<Status {loading} {error} retry={() => load(category, tariffQ, capexQ)} />

{#if notReady && !loading}
	<div class="notice notice-warn" role="status">
		<p><strong>Розрахунок ще не готовий.</strong> Модуль оцінки сонячних станцій зараз доробляється. Спробуйте трохи пізніше — сторінка запрацює автоматично, щойно розрахунок з’явиться на сервері.</p>
	</div>
{/if}

{#if data && !loading}
	<p>
		{num(items.length)} будівель. Якщо поставити рекомендовані станції на всіх: потужність
		<strong>{num(totals.kw)} кВт</strong>, вартість <strong>{num(totals.capex)} грн</strong>, економія
		<strong>{num(totals.save)} грн/рік</strong>.
	</p>
	<div class="table-wrap">
		<table>
			<caption>
				Рейтинг будівель для нових СЕС{cat ? ` — ${cat}` : ''}
				<span class="muted">— від найшвидшої окупності до найдовшої; тариф {num(data.params.tariff_uah_kwh, 2)} грн/кВт·год, монтаж {num(data.params.capex_uah_per_kw)} грн/кВт</span>
			</caption>
			<thead>
				<tr>
					<th scope="col" class="num">№</th>
					<th scope="col">Будівля</th>
					<th scope="col" class="num">Споживання ел., <span class="unit">кВт·год/рік</span></th>
					<th scope="col" class="num">Дах, <span class="unit">м²</span></th>
					<th scope="col" class="num">Рекомендовано, <span class="unit">кВт</span></th>
					<th scope="col" class="num">Генерація, <span class="unit">кВт·год/рік</span></th>
					<th scope="col" class="num">Покриття потреби</th>
					<th scope="col" class="num">Вартість, <span class="unit">грн</span></th>
					<th scope="col" class="num">Економія, <span class="unit">грн/рік</span></th>
					<th scope="col" class="num">Окупність, <span class="unit">років</span></th>
				</tr>
			</thead>
			<tbody>
				{#each items as it, i (it.id)}
					<tr>
						<td class="num">{i + 1}</td>
						<td class="name">
							<a href="/solar/{it.id}{detailQs}">{it.name}</a>
							<div class="muted small">{it.category_short}</div>
						</td>
						<td class="num">{num(it.elec_kwh_year)}</td>
						<td class="num">{num(it.roof_area_m2)}</td>
						<td class="num">
							{num(it.kw_recommended, 1)}
							{#if it.kw_max_roof}<div class="muted small">макс. за дахом {num(it.kw_max_roof, 1)}</div>{/if}
							{#if it.limited_by}<div class="muted small">обмежує: {it.limited_by}</div>{/if}
						</td>
						<td class="num">{num(it.gen_kwh_year)}</td>
						<td class="num">{it.coverage_pct !== null ? `${num(it.coverage_pct)} %` : '—'}</td>
						<td class="num">{num(it.capex_uah)}</td>
						<td class="num">{num(it.savings_uah_year)}</td>
						<td class="num"><strong>{it.payback_years !== null ? num(it.payback_years, 1) : 'не окупається'}</strong></td>
					</tr>
				{:else}
					<tr><td colspan="10" class="muted">Немає будівель для розрахунку.</td></tr>
				{/each}
			</tbody>
		</table>
	</div>

	{#if data.params.source_notes?.length}
		<section class="card notes">
			<h2>Припущення та джерела</h2>
			<ul>
				<li>Потужність на 1 м² даху: {num(data.params.kwp_per_m2_roof, 3)} кВт/м².</li>
				{#if data.params.capex_fixed_uah}<li>Фіксована вартість на об’єкт (проєкт і підключення): {num(data.params.capex_fixed_uah)} грн.</li>{/if}
				{#each data.params.source_notes as n, i (i)}<li>{n}</li>{/each}
			</ul>
			<p class="muted small">Це аналітична оцінка, а не проєкт станції.</p>
		</section>
	{/if}
{/if}

<style>
	.params {
		padding: 1rem;
	}
	.params input {
		width: 12rem;
	}
	.notes {
		margin-top: 1.25rem;
	}
	.notes ul {
		margin: 0 0 0.5rem;
		padding-left: 1.2rem;
	}
</style>
