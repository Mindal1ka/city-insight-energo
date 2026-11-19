<script lang="ts">
	// Картка (паспорт) будівлі: атрибути, споживання 2025 проти 2026, порівняння з медіаною, клас, дефекти
	import { page } from '$app/state';
	import { api, errMessage, ApiError, type BuildingFull, type Building, type YearData } from '#lib/api.ts';
	import { num, pct } from '#lib/format.ts';
	import { classInfo } from '#lib/classes.ts';
	import ClassBadge from '#lib/ClassBadge.svelte';
	import CompareBar from '#lib/CompareBar.svelte';
	import Status from '#lib/Status.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Term from '#lib/Term.svelte';
	import { electricityRating, isElecRelevant, ratioWords, BASE_YEAR } from '../../rating/electricity.ts';

	let b = $state<BuildingFull | null>(null);
	let all = $state<Building[]>([]);
	let showAllDefects = $state(false);
	let error = $state<string | null>(null);
	let notFound = $state(false);
	let loading = $state(true);

	const id = $derived(page.params.id ?? '');

	async function load(bid: string) {
		loading = true;
		error = null;
		notFound = false;
		try {
			[b, all] = await Promise.all([api.building(bid), all.length ? all : api.buildings()]);
		} catch (e) {
			b = null;
			if (e instanceof ApiError && e.status === 404) notFound = true;
			else error = errMessage(e);
		} finally {
			loading = false;
		}
	}

	// Перезавантажуємо при зміні id в адресі
	$effect(() => {
		load(id);
	});

	const years = $derived(b ? Object.keys(b.years).sort() : []);
	const baseYear = BASE_YEAR;
	// Рейтинг і клас — за електроенергією (рахуємо на клієнті по всіх будівлях)
	const er = $derived(b && all.length ? (electricityRating(all).rows.get(b.id) ?? null) : null);
	const info = $derived(classInfo(er?.cls));
	const defects = $derived(b ? (showAllDefects ? b.defects : b.defects.filter(isElecRelevant)) : []);
	const hiddenDefects = $derived(b ? b.defects.length - b.defects.filter(isElecRelevant).length : 0);

	// Рядки таблиці: лише електроенергія
	const resources: { key: keyof YearData; label: string; unit: string; digits: number }[] = [
		{ key: 'elec_kwh', label: 'Електроенергія', unit: 'кВт·год', digits: 0 },
		{ key: 'elec_kwh_m2', label: 'Споживання на 1 м²', unit: 'кВт·год/м²', digits: 1 }
	];

	function cell(y: string, key: keyof YearData): number | null {
		const v = b?.years[y]?.[key];
		return typeof v === 'number' ? v : null;
	}


	// Тип запису: «дефект даних» або «аномалія споживання» (якщо бекенд його надсилає)
	function kindOf(t: string | undefined): string {
		return t ?? 'дефект даних';
	}
</script>

<svelte:head>
	<title>{b ? b.name : 'Картка будівлі'} · City Insight Map · Енергія</title>
</svelte:head>

<p class="no-print back"><a href="/rating{b ? `?cat=${encodeURIComponent(b.category_short)}` : ''}">← До рейтингу</a></p>

{#if loading}<Skeleton variant="page" count={2} rows={4} />{/if}
<Status loading={false} {error} retry={() => load(id)} />

{#if notFound && !loading}
	<div class="notice notice-warn" role="alert">
		<p><strong>Будівлю не знайдено.</strong> Можливо, після оновлення даних змінився її номер. Знайдіть її в <a href="/rating">рейтингу</a>.</p>
	</div>
{/if}

{#if b && !loading}
	<div class="page-head">
		<div>
			<p class="muted kicker">Паспорт даних будівлі · {b.category_short}</p>
			<h1>{b.name}</h1>
			<p class="lead">{b.address}</p>
		</div>
		<div class="actions no-print">
			<a class="btn" href="/object/{b.id}">Сонце, акумулятор і автономність →</a>
			<button type="button" class="btn btn-secondary" onclick={() => window.print()}>Друк / PDF</button>
		</div>
	</div>

	<div class="grid-2">
		<section class="card" aria-labelledby="attr-h">
			<h2 id="attr-h">Характеристики</h2>
			<dl class="attrs">
				<dt>Категорія</dt>
				<dd>{b.category ?? b.category_short}</dd>
				<dt>Площа</dt>
				<dd>{b.heated_area !== null ? `${num(b.heated_area, 1)} м²` : 'не вказано'}</dd>
				<dt>Поверховість</dt>
				<dd>{b.floors ?? 'не вказано'}</dd>
				<dt>Рік забудови</dt>
				<dd>{b.year_built ?? 'не вказано'}</dd>
				<dt>Координати</dt>
				<dd>{b.has_coords ? 'є' : 'немає (потрібне геокодування)'}</dd>
				<dt>Номер у <Term key="UMUNI" plain /></dt>
				<dd>{b.id > 0 ? b.id : 'немає в реєстрі будівель'}</dd>
			</dl>
		</section>

		<section class="card" aria-labelledby="cls-h">
			<h2 id="cls-h">Електроенергія порівняно зі схожими, {baseYear}</h2>
			{#if er && !er.excluded}
				<p class="cls-line">
					<ClassBadge cls={er.cls} />
					<span>Місце <strong>{er.rank}</strong> з {er.rankOf} у категорії «{b.category_short}» (1 = найбільше споживає на 1 м²)</span>
				</p>
				<CompareBar value={er.kwhM2} median={er.median} category={b.category_short} year={baseYear} />
				<p>
					<Term key="питоме споживання">Споживання на 1 м²</Term>: {ratioWords(er.ratio)}{#if er.ratio !== null && ratioWords(er.ratio) !== 'на рівні медіани'}, ніж
						<Term key="медіана категорії">медіана категорії</Term>{/if}.
					{#if info}<Term key="умовний клас">Клас</Term> <strong>{info.letter}</strong> означає «{info.text}» ({info.range}).{/if}
				</p>
			{:else if er}
				<div class="notice notice-warn">
					<p>
						<strong>Будівля не входить до рейтингу.</strong> Причина: {er.excluded}.
						Після виправлення даних в UMUNI вона з’явиться в рейтингу автоматично.
					</p>
				</div>
			{/if}
			<p class="muted small disclaimer">
				Клас — <strong>аналітична оцінка</strong> відносно медіани схожих будівель громади, а
				<strong>не офіційний енергетичний сертифікат</strong> будівлі.
			</p>
		</section>
	</div>

	<section class="card consumption" aria-labelledby="cons-h">
		<h2 id="cons-h">Споживання електроенергії</h2>
		<div class="table-wrap">
			<table>
				<caption>
					Річне споживання за роками
					<span class="muted">— дані UMUNI; неповний рік позначено окремо</span>
				</caption>
				<thead>
					<tr>
						<th scope="col">Ресурс</th>
						<th scope="col">Одиниця</th>
						{#each years as y (y)}
							<th scope="col" class="num">
								{y}
								{#if b.years[y].partial}
									<br /><span class="pill pill-warn">неповний рік, {pct(b.years[y].coverage)}</span>
								{/if}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each resources as r (r.key)}
						<tr>
							<th scope="row">{r.label}</th>
							<td class="unit">{r.unit}</td>
							{#each years as y (y)}
								<td class="num">{num(cell(y, r.key), r.digits)}</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="muted small">
			«—» означає, що показника немає у вивантаженні. Неповний рік не можна напряму
			порівнювати з повним: у ньому менше місяців.
		</p>
	</section>

	<section class="card" aria-labelledby="def-h">
		<h2 id="def-h">Дефекти даних і аномалії ({defects.length})</h2>
		{#if hiddenDefects > 0}
			<label class="toggle no-print">
				<input type="checkbox" bind:checked={showAllDefects} />
				Показати також записи про тепло, газ і воду ({hiddenDefects})
			</label>
		{/if}
		{#if defects.length === 0}
			<p class="notice notice-ok">Дефектів даних, що стосуються електроенергії, не знайдено.</p>
		{:else}
			<div class="table-wrap">
				<table>
					<caption class="visually-hidden">Дефекти даних і аномалії цієї будівлі</caption>
					<thead>
						<tr>
							<th scope="col">Тип</th>
							<th scope="col">Що не так</th>
							<th scope="col">Поле</th>
							<th scope="col">Значення</th>
							<th scope="col">Що робити</th>
							<th scope="col">Набір даних</th>
						</tr>
					</thead>
					<tbody>
						{#each defects as d, i (i)}
							<tr>
								<td>
									<span class="pill {kindOf(d.тип) === 'аномалія споживання' ? 'pill-bad' : 'pill-warn'}">{kindOf(d.тип)}</span>
								</td>
								<td>{d.правило}</td>
								<td>{d.поле}</td>
								<td>{d.значення ?? '—'}</td>
								<td>{d.що_робити}</td>
								<td class="small muted">{d.набір}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>

	<p class="muted small print-only">
		Аналітична оцінка на даних UMUNI. Не є офіційним енергосертифікатом.
	</p>
{/if}

<style>
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-weight: 500;
		margin-bottom: 0.75rem;
		cursor: pointer;
	}
	.toggle input {
		width: 1.1rem;
		height: 1.1rem;
	}
	.back {
		margin: 0 0 0.75rem;
	}
	.kicker {
		margin: 0 0 0.25rem;
		font-weight: 600;
		font-size: 0.9rem;
	}
	h1 {
		max-width: 60ch;
	}
	.attrs {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.4rem 1.25rem;
		margin: 0;
	}
	dt {
		color: var(--muted);
		font-weight: 600;
	}
	dd {
		margin: 0;
	}
	.cls-line {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 0.9rem;
		align-items: center;
	}
	.disclaimer {
		border-top: 1px solid var(--line);
		padding-top: 0.6rem;
		margin-top: 0.75rem;
	}
	.consumption {
		margin-top: 1.25rem;
	}
	.print-only {
		display: none;
	}
	@media print {
		.print-only {
			display: block;
		}
		.grid-2 {
			grid-template-columns: 1fr 1fr;
		}
	}
</style>
