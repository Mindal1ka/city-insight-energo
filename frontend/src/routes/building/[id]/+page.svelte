<script lang="ts">
	// Паспорт даних будівлі: що про неї відомо з UMUNI, скільки електрики витрачає,
	// як це порівняно зі схожими будівлями і які проблеми в даних треба виправити.
	import { page } from '$app/state';
	import { api, errMessage, ApiError, type BuildingFull, type Building } from '#lib/api.ts';
	import { num, pct, scaleKwh, plural } from '#lib/format.ts';
	import { classInfo } from '#lib/classes.ts';
	import { catLabel } from '#lib/categories.ts';
	import ClassBadge from '#lib/ClassBadge.svelte';
	import CompareBar from '#lib/CompareBar.svelte';
	import Status from '#lib/Status.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Term from '#lib/Term.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import Icon from '#lib/Icon.svelte';
	import { electricityRating, isElecRelevant, ratioWords, LEVEL_WORDS, BASE_YEAR } from '../../rating/electricity.ts';
	import { groupDefects, SEVERITY_LABEL } from '../../defects/groups.ts';

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
	// Рейтинг і клас — за електроенергією (рахуємо на клієнті по всіх будівлях)
	const er = $derived(b && all.length ? (electricityRating(all).rows.get(b.id) ?? null) : null);
	const info = $derived(classInfo(er?.cls));
	const elecDefects = $derived(b ? b.defects.filter(isElecRelevant) : []);
	const defects = $derived(b ? (showAllDefects ? b.defects : elecDefects) : []);
	const hiddenDefects = $derived(b ? b.defects.length - elecDefects.length : 0);
	const groups = $derived(groupDefects(defects));
	// Чи є серед проблем такі, що впливають на розрахунок (а не лише довідкові поля)
	const elecGroups = $derived(groupDefects(elecDefects));
	const serious = $derived(elecGroups.some((g) => g.severity !== 'low'));

	const kwhBase = $derived(b?.years[BASE_YEAR]?.elec_kwh ?? null);
	const kwhScaled = $derived(scaleKwh(kwhBase));
	const yearMax = $derived(Math.max(1, ...years.map((y) => b?.years[y]?.elec_kwh ?? 0)));

	const cmpTone = $derived(
		er?.ratio == null ? 'neutral' : er.ratio > 1.5 ? 'bad' : er.ratio > 1.1 ? 'warn' : er.ratio < 0.9 ? 'good' : 'neutral'
	);
</script>

<svelte:head>
	<title>{b ? b.name : 'Паспорт будівлі'} · City Insight Map · Енергія</title>
</svelte:head>

<p class="no-print back">
	<a href="/rating{b ? `?cat=${encodeURIComponent(b.category_short)}` : ''}" data-sveltekit-reset="false">
		<Icon name="arrow-left" size={16} /> До рейтингу
	</a>
</p>

{#if loading}<Skeleton variant="page" count={4} rows={4} />{/if}
<Status loading={false} {error} retry={() => load(id)} />

{#if notFound && !loading}
	<div class="notice notice-warn" role="alert">
		<p><strong>Будівлю не знайдено.</strong> Можливо, після оновлення даних змінився її номер. Знайдіть її в <a href="/rating">рейтингу</a>.</p>
	</div>
{/if}

{#if b && !loading}
	<div class="page-head">
		<div>
			<p class="kicker">Паспорт даних · {catLabel(b.category_short)}</p>
			<h1>{b.name}</h1>
			<p class="lead">{b.address}</p>
			<p class="lead plain hide-phone">Усе, що відомо про будівлю з даних <Term key="UMUNI" plain />: скільки електрики вона витрачає і як це порівняно зі схожими будівлями.</p>
		</div>
		<div class="actions no-print">
			<a class="btn" href="/object/{b.id}"><Icon name="sun" size={18} /> Сонце й автономність</a>
			<button type="button" class="btn btn-secondary hide-phone" onclick={() => window.print()}>Друк / PDF</button>
		</div>
	</div>

	<section class="stats" aria-label="Головне в цифрах">
		<Reveal>
			<StatCard
				label="Електрика за {BASE_YEAR} рік"
				value={kwhScaled.value}
				decimals={kwhScaled.decimals}
				unit={kwhScaled.unit}
				icon="bolt"
				hint={kwhBase ? 'Усі лічильники будівлі за повний рік.' : 'Немає даних за цей рік.'}
			/>
		</Reveal>
		<Reveal delay={70}>
			<StatCard
				label="На 1 м² за рік"
				value={er?.kwhM2 ?? null}
				decimals={1}
				unit="кВт·год/м²"
				icon="gauge"
				tone={cmpTone}
				toneLabel={cmpTone === 'good' ? 'економніше за типову' : cmpTone === 'neutral' ? undefined : 'більше за типову'}
				hint={er?.ratio != null
					? ratioWords(er.ratio) === LEVEL_WORDS
						? `Приблизно як у типової будівлі категорії (${num(er.median, 1)}).`
						: `Це ${ratioWords(er.ratio)}, ніж у типової будівлі категорії (${num(er.median, 1)}).`
					: 'Не рахується: бракує даних.'}
			/>
		</Reveal>
		<Reveal delay={140}>
			<StatCard
				label="Черга на перевірку"
				value={er && !er.excluded ? er.rank : null}
				icon="chart"
				unit={er && !er.excluded ? `з ${er.rankOf}` : ''}
				href={er && !er.excluded ? `/rating?cat=${encodeURIComponent(b.category_short)}` : undefined}
				hint={er && !er.excluded
					? '№ 1 — та, що витрачає найбільше на 1 м² серед схожих: її перевіряють першою.'
					: 'Будівля поки не в рейтингу — причина нижче.'}
			/>
		</Reveal>
		<Reveal delay={210}>
			<StatCard
				label="Проблем у даних"
				value={elecDefects.length}
				icon={serious ? 'alert' : elecDefects.length ? 'info' : 'check'}
				tone={serious ? 'warn' : elecDefects.length ? 'neutral' : 'good'}
				toneLabel={serious ? 'треба виправити' : 'все гаразд'}
				href={elecDefects.length ? '#def-h' : undefined}
				hint={serious
					? 'Впливають на розрахунок. Що саме і як виправити — внизу сторінки.'
					: elecDefects.length
						? 'Лише довідкові поля — на розрахунок електрики не впливають.'
						: 'Дані про електрику без помилок.'}
			/>
		</Reveal>
	</section>

	<div class="grid-2 main">
		<Reveal class="cell">
			<section class="card" aria-labelledby="cls-h">
				<h2 id="cls-h">Порівняно зі схожими будівлями</h2>
				{#if er && !er.excluded}
					<p class="cls-line">
						<ClassBadge cls={er.cls} />
						<span class="muted">категорія «{b.category_short}», {BASE_YEAR} рік</span>
					</p>
					<CompareBar value={er.kwhM2} median={er.median} category={b.category_short} year={BASE_YEAR} />
					<p>
						На кожен квадратний метр будівля витрачає <strong>{ratioWords(er.ratio)}</strong>{#if ratioWords(er.ratio) !== LEVEL_WORDS}, ніж
							<Term key="медіана категорії">типова будівля</Term> цієї категорії{/if}.
					</p>
					<Disclosure summary="Що означає клас {info?.letter ?? ''}">
						<p class="small">
							{#if info}<Term key="умовний клас">Клас</Term> <strong>{info.letter}</strong> — «{info.text}» ({info.range}).{/if}
							Клас — <strong>аналітична оцінка</strong> відносно схожих будівель громади, а
							<strong>не офіційний енергетичний сертифікат</strong>.
						</p>
					</Disclosure>
				{:else if er}
					<div class="notice notice-warn">
						<p>
							<strong>Будівля поки не в рейтингу.</strong> Причина: {er.excluded}. Після виправлення даних в
							UMUNI вона з’явиться в рейтингу автоматично.
						</p>
					</div>
				{/if}
			</section>
		</Reveal>

		<Reveal class="cell" delay={90}>
			<section class="card" aria-labelledby="cons-h">
				<h2 id="cons-h">Електрика за роками</h2>
				<ul class="years">
					{#each years as y, i (y)}
						{@const v = b.years[y]?.elec_kwh ?? null}
						<li>
							<span class="y-l">
								<strong>{y}</strong>
								{#if b.years[y].partial}<span class="pill pill-warn">неповний рік · {pct(b.years[y].coverage)}</span>{/if}
							</span>
							<span class="y-track" aria-hidden="true">
								<span class="y-fill" class:partial={b.years[y].partial} style="width:{((v ?? 0) / yearMax) * 100}%; --i:{i}"></span>
							</span>
							<span class="y-v tnum">{num(v)} <span class="unit">кВт·год</span></span>
						</li>
					{/each}
				</ul>
				<p class="muted small">
					Неповний рік не можна напряму порівнювати з повним: у ньому менше місяців.
				</p>
				<Disclosure summary="Характеристики будівлі">
					<dl class="attrs">
						<dt>Категорія</dt>
						<dd>{b.category ?? b.category_short}</dd>
						<dt>Площа</dt>
						<dd>{b.heated_area !== null ? `${num(b.heated_area, 1)} м²` : 'не вказано'}</dd>
						<dt>Поверхів</dt>
						<dd>{b.floors ?? 'не вказано'}</dd>
						<dt>Рік забудови</dt>
						<dd>{b.year_built ?? 'не вказано'}</dd>
						<dt>На карті</dt>
						<dd>{b.has_coords ? 'так' : 'так, за адресою (координат немає в UMUNI)'}</dd>
						<dt>Номер у UMUNI</dt>
						<dd>{b.id > 0 ? b.id : 'немає в реєстрі будівель'}</dd>
						{#each years as y (y)}
							<dt>На 1 м², {y}</dt>
							<dd>{num(b.years[y]?.elec_kwh_m2 ?? null, 1)} кВт·год/м²</dd>
						{/each}
					</dl>
				</Disclosure>
			</section>
		</Reveal>
	</div>

	<Reveal>
		<section class="card defs" aria-labelledby="def-h">
			<h2 id="def-h">Що виправити в даних</h2>
			{#if hiddenDefects > 0}
				<label class="toggle no-print">
					<input type="checkbox" bind:checked={showAllDefects} />
					Показати також тепло, газ і воду ({hiddenDefects})
				</label>
			{/if}
			{#if defects.length === 0}
				<p class="all-ok"><Icon name="check" size={20} /> Проблем у даних про електроенергію не знайдено.</p>
			{:else}
				<ul class="dgroups">
					{#each groups as g (g.key)}
						<li class="sev-{g.severity}">
							<span class="pill pill-{g.severity}">{SEVERITY_LABEL[g.severity]}</span>
							<p class="dg-t"><strong>{g.title}</strong>{#if g.items.length > 1} <span class="muted">· {g.items.length} {plural(g.items.length, ['запис', 'записи', 'записів'])}</span>{/if}</p>
							<p class="dg-todo"><Icon name="check" size={16} /> <span><strong>Що робити:</strong> {g.todo}</span></p>
						</li>
					{/each}
				</ul>
				<Disclosure summary="Технічні подробиці для фахівця з даних" hint="{defects.length} {plural(defects.length, ['запис', 'записи', 'записів'])}">
					<div class="table-wrap">
						<table>
							<caption class="visually-hidden">Записи про проблеми в даних цієї будівлі</caption>
							<thead>
								<tr>
									<th scope="col">Правило</th>
									<th scope="col">Поле</th>
									<th scope="col">Значення</th>
									<th scope="col">Набір даних</th>
								</tr>
							</thead>
							<tbody>
								{#each defects as d, i (i)}
									<tr>
										<td>{d.правило}</td>
										<td>{d.поле}</td>
										<td>{d.значення === '' || d.значення === null ? '—' : d.значення}</td>
										<td class="small muted">{d.набір}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</Disclosure>
			{/if}
		</section>
	</Reveal>

	<p class="muted small print-only">
		Аналітична оцінка на даних UMUNI. Не є офіційним енергосертифікатом.
	</p>
{/if}

<style>
	.back {
		margin: 0 0 0.75rem;
	}
	.back a {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-weight: 600;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.kicker {
		margin: 0 0 0.25rem;
		font-weight: 600;
		font-size: 0.9rem;
		color: var(--sun-ink);
	}
	h1 {
		max-width: 60ch;
	}
	.lead.plain {
		margin-top: 0.4rem;
		font-size: 0.95rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 270px), 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.stats > :global(.reveal) {
		display: grid;
	}
	.main {
		margin-bottom: 1.25rem;
	}
	.main :global(.cell) {
		display: grid;
		min-width: 0;
	}
	.main .card {
		margin-bottom: 0;
	}
	.cls-line {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 0.9rem;
		align-items: center;
	}
	.years {
		list-style: none;
		margin: 0 0 0.75rem;
		padding: 0;
		display: grid;
		gap: 0.9rem;
	}
	.years li {
		display: grid;
		gap: 0.3rem;
	}
	.y-l {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}
	.y-track {
		display: block;
		height: 12px;
		border-radius: 999px;
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.y-fill {
		display: block;
		height: 100%;
		border-radius: 999px;
		background: var(--navy-3);
		transform-origin: left center;
	}
	.y-fill.partial {
		background: repeating-linear-gradient(135deg, var(--sun) 0 8px, var(--sun-strong) 8px 16px);
	}
	@media (prefers-reduced-motion: no-preference) {
		.y-fill {
			animation: grow-x 0.8s var(--ease) both;
			animation-delay: calc(var(--i, 0) * 120ms + 250ms);
		}
		@keyframes grow-x {
			from {
				transform: scaleX(0);
			}
		}
	}
	.y-v {
		font-weight: 600;
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
	.all-ok {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		color: var(--ok);
		font-weight: 600;
	}
	.dgroups {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.75rem;
	}
	.dgroups li {
		padding: 0.75rem 1rem;
		border: 1px solid var(--line);
		border-left: 4px solid var(--line-strong);
		border-radius: 10px;
	}
	.dgroups li.sev-high {
		border-left-color: var(--bad);
	}
	.dgroups li.sev-mid {
		border-left-color: var(--sun-strong);
	}
	.dgroups p {
		margin: 0.35rem 0 0;
	}
	.pill-high {
		background: var(--bad-soft);
		border-color: var(--bad);
		color: var(--bad);
	}
	.pill-mid {
		background: var(--sun-soft);
		border-color: var(--sun-ink);
		color: var(--sun-ink);
	}
	.dg-todo {
		display: flex;
		gap: 0.4rem;
		align-items: flex-start;
		color: var(--ok);
	}
	.dg-todo span {
		color: var(--text);
	}
	.dg-todo :global(svg) {
		flex: none;
		margin-top: 0.2rem;
	}
	.defs h2 {
		scroll-margin-top: 6rem;
	}
	.print-only {
		display: none;
	}
	/* Сенсорні екрани: «До рейтингу» — ціль ≥ 40 px */
	@media (max-width: 768px) {
		.back {
			margin-bottom: 0.25rem;
		}
		.back a {
			min-height: 40px;
		}
	}
	/* Телефон: компактний паспорт */
	@media (max-width: 640px) {
		.kicker {
			font-size: 0.8125rem;
		}
		h1 {
			font-size: 1.3rem;
			line-height: 1.25;
		}
		.page-head .lead {
			font-size: 0.9375rem;
		}
		.actions {
			width: 100%;
		}
		.actions .btn {
			flex: 1 1 auto;
			justify-content: center;
		}
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.625rem;
			margin-bottom: 1rem;
		}
		.stats > :global(:last-child:nth-child(odd)) {
			grid-column: 1 / -1;
		}
		.main {
			margin-bottom: 0.875rem;
		}
		.years {
			gap: 0.7rem;
		}
		.y-track {
			height: 10px;
		}
		.attrs {
			grid-template-columns: minmax(0, auto) minmax(0, 1fr);
			gap: 0.35rem 0.9rem;
			font-size: 0.9375rem;
		}
		.dgroups li {
			padding: 0.65rem 0.8rem;
		}
		.toggle {
			min-height: 40px;
			font-size: 0.9375rem;
		}
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
