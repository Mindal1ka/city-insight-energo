<script lang="ts">
	// «Споживання електроенергії»: скільки електрики споживають комунальні будівлі громади і хто найбільше.
	// Принцип: одне речення «що тут» → 4 картки → дві прості візуалізації; деталі — за «Детальніше».
	import { api, errMessage, type Summary, type Building } from '#lib/api.ts';
	import { revealRows } from '#lib/motion.ts';
	import { num, pct, date, dateTime, scaleKwh, kwhText, plural } from '#lib/format.ts';
	import { catLabel } from '#lib/categories.ts';
	import Status from '#lib/Status.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Term from '#lib/Term.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import { electricityRating, median, BASE_YEAR } from '../rating/electricity.ts';
	import { grow } from '../rating/grow.ts';

	let data = $state<Summary | null>(null);
	let buildings = $state<Building[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let showMoreTop = $state(false);

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
	const cur = $derived(partial.at(-1) ?? null);
	const updated = $derived.by(() => {
		if (!data) return null;
		const dates = [...Object.values(data.years).map((y) => y.created), ...data.sources.map((s) => s.created)].filter(
			(d): d is string => !!d
		);
		return dates.sort().at(-1) ?? null;
	});

	const rating = $derived(electricityRating(buildings));
	const withElec = $derived(buildings.filter((b) => (b.years[BASE_YEAR]?.elec_kwh ?? 0) > 0));
	const totalElec = $derived(withElec.reduce((s, b) => s + (b.years[BASE_YEAR]?.elec_kwh ?? 0), 0));
	const typical = $derived(
		median([...rating.rows.values()].filter((r) => !r.excluded && r.kwhM2 !== null).map((r) => r.kwhM2!))
	);
	const noData = $derived(data ? data.buildings - withElec.length : 0);
	// З них — без жодного показника за базовий рік (ні електрики, ні тепла, газу чи води)
	const RES = ['elec_kwh', 'heat_gcal', 'gas_m3', 'cold_m3', 'hot_m3'] as const;
	const noneAtAll = $derived(
		buildings.filter((b) => {
			const y = b.years[BASE_YEAR];
			return !y || RES.every((k) => !((y[k] ?? 0) > 0));
		}).length
	);

	const baseScaled = $derived(scaleKwh(base?.elec_kwh));
	const curScaled = $derived(scaleKwh(cur?.[1].elec_kwh));
	// Груба оцінка повного поточного року: якщо решта року йтиме так само
	const projection = $derived(cur && cur[1].coverage > 0 ? cur[1].elec_kwh / cur[1].coverage : null);
	const projDiff = $derived(projection && base?.elec_kwh ? projection / base.elec_kwh - 1 : null);

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
	const topMax = $derived(Math.max(1, top[0]?.years[BASE_YEAR]?.elec_kwh ?? 1));
	const topShown = $derived(showMoreTop ? top : top.slice(0, 5));
	const topShare = $derived(
		totalElec ? top.reduce((s, b) => s + (b.years[BASE_YEAR]?.elec_kwh ?? 0), 0) / totalElec : 0
	);
	const top5Share = $derived(
		totalElec ? top.slice(0, 5).reduce((s, b) => s + (b.years[BASE_YEAR]?.elec_kwh ?? 0), 0) / totalElec : 0
	);
</script>

<svelte:head><title>Споживання електроенергії · Insight Tool</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Споживання електроенергії</h1>
	</div>
	{#if updated}
		<p class="muted small fresh">Дані <Term key="UMUNI" plain /> від <strong>{dateTime(updated)}</strong></p>
	{/if}
</div>

{#if loading}
	<Skeleton variant="page" count={4} rows={6} />
{/if}
<Status loading={false} {error} retry={load} />

{#if data && !loading && !error}
	<section aria-labelledby="kpi-h">
		<h2 id="kpi-h" class="visually-hidden">Головне в цифрах</h2>
		<div class="stats">
			<Reveal delay={0}>
				<StatCard
					label="Електрика за {BASE_YEAR} рік"
					value={baseScaled.value}
					decimals={baseScaled.decimals}
					unit={baseScaled.unit}
					icon="bolt"
					hint="Разом по {num(withElec.length)} {plural(withElec.length, ['будівлі', 'будівлях', 'будівлях'])} громади."
				/>
			</Reveal>
			{#if cur}
				<Reveal delay={70}>
					<StatCard
						label="{cur[0]} рік — поки неповний"
						value={curScaled.value}
						decimals={curScaled.decimals}
						unit={curScaled.unit}
						icon="clock"
						tone="warn"
						toneLabel="рік ще не закінчився"
						hint={projDiff !== null
							? `Дані за ≈ ${pct(cur[1].coverage)} року. Якщо так триватиме — це на ${pct(Math.abs(projDiff))} ${projDiff >= 0 ? 'більше' : 'менше'}, ніж у ${BASE_YEAR}.`
							: `Дані лише за ≈ ${pct(cur[1].coverage)} року.`}
					/>
				</Reveal>
			{/if}
			<Reveal delay={140}>
				<StatCard
					label="Типова будівля на 1 м²"
					value={typical}
					decimals={1}
					unit="кВт·год/м²"
					icon="gauge"
					href="/rating"
					hint="Половина будівель витрачає більше, половина — менше. Хто саме — у рейтингу."
				/>
			</Reveal>
			<Reveal delay={210}>
				<StatCard
					label="Будівель у базі"
					value={data.buildings}
					icon="building"
					tone={noData ? 'warn' : 'neutral'}
					toneLabel="є будівлі без даних"
					hint={noData
						? `Без даних про електрику за ${BASE_YEAR}: ${num(noData)}.`
						: 'Для всіх є дані про електрику.'}
				/>
			</Reveal>
		</div>
	</section>

	<div class="grid-2 main">
		<Reveal class="cell">
			<section class="card" aria-labelledby="cat-h">
				<h2 id="cat-h">За типами будівель <span class="h-chip">{BASE_YEAR}</span></h2>
				<ul class="cats" {@attach grow}>
					{#each byCategory as c, i (c.name)}
						<li>
							<div class="cat-line">
								<a href="/rating?cat={encodeURIComponent(c.name)}" class="cat-name" title={c.name}>{catLabel(c.name)}</a>
								<span class="cat-pct tnum">{pct(c.share)}</span>
							</div>
							<span class="track" aria-hidden="true">
								<span class="fill" style="width:{(c.kwh / catMax) * 100}%; --i:{i}"></span>
							</span>
							<span class="muted small">{kwhText(c.kwh)} · {num(c.count)} {plural(c.count, ['будівля', 'будівлі', 'будівель'])}</span>
						</li>
					{/each}
				</ul>
				<Disclosure summary="Детальніше: типове споживання на 1 м² у кожній категорії">
					<div class="table-wrap">
						<table>
							<caption class="visually-hidden">Споживання за категоріями будівель</caption>
							<thead>
								<tr>
									<th scope="col">Категорія</th>
									<th scope="col" class="num">Будівель</th>
									<th scope="col" class="num">Електрика, <span class="unit">кВт·год</span></th>
									<th scope="col" class="num">
										<Term key="медіана категорії">Типово на 1 м²</Term>
									</th>
								</tr>
							</thead>
							<tbody use:revealRows={{ delay: 160 }}>
								{#each byCategory as c (c.name)}
									<tr>
										<th scope="row">{c.name}</th>
										<td class="num">{num(c.count)}</td>
										<td class="num">{num(c.kwh)}</td>
										<td class="num">{num(c.med, 1)} <span class="unit">кВт·год/м²</span></td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</Disclosure>
			</section>
		</Reveal>

		<Reveal class="cell" delay={90}>
			<section class="card" aria-labelledby="top-h">
				<h2 id="top-h">Найбільші споживачі <span class="h-chip" title="Частка п’ятірки від усієї електрики громади">топ-5 = {pct(top5Share)}</span></h2>
				<ol class="top" {@attach grow}>
					{#each topShown as b, i (b.id)}
						{@const kwh = b.years[BASE_YEAR]?.elec_kwh ?? 0}
						<li>
							<span class="top-n" aria-hidden="true">{i + 1}</span>
							<span class="top-txt">
								<a href="/object/{b.id}"><span class="visually-hidden">{i + 1}. </span>{b.name}</a>
								<span class="track thin" aria-hidden="true">
									<span class="fill" style="width:{(kwh / topMax) * 100}%; --i:{i}"></span>
								</span>
								<span class="muted small">{catLabel(b.category_short)}</span>
							</span>
							<span class="top-v tnum">{kwhText(kwh)}</span>
						</li>
					{/each}
				</ol>
				<div class="top-foot">
					{#if top.length > 5}
						<button type="button" class="btn btn-secondary" aria-expanded={showMoreTop} onclick={() => (showMoreTop = !showMoreTop)}>
							{showMoreTop ? 'Показати лише п’ять' : `Показати всі ${top.length} (разом ${pct(topShare)})`}
						</button>
					{/if}
					<a href="/energy" class="go">Розподіл енергії →</a>
				</div>
			</section>
		</Reveal>
	</div>

	<Disclosure summary="Як рахуємо" hint="{data.sources.length} {plural(data.sources.length, ['файл', 'файли', 'файлів'])} з UMUNI" class="card soft">
		<ul class="muted small">
			<li>Дані — вивантаження з <Term key="UMUNI" plain />, лише електроенергія.</li>
			<li>Порівнюйте всередині категорії: лікарня закономірно витрачає на 1 м² більше, ніж музей.</li>
			{#if cur && projection}
				<li>
					{cur[0]} рік (вивантаження від {date(cur[1].created)}) охоплює ≈ {pct(cur[1].coverage)} року, тому рейтинг — за {BASE_YEAR}.
					Груба оцінка за весь {cur[0]}: <strong>{kwhText(projection)}</strong>.
				</li>
			{/if}
		</ul>
		<ul class="sources">
			{#each data.sources as s (s.file)}
				<li>
					<strong>{s.kind}</strong>
					<span class="muted small">{num(s.rows)} рядків{s.created ? ` · вивантажено ${dateTime(s.created)}` : ''}</span>
					<code>{s.file}</code>
				</li>
			{/each}
		</ul>
	</Disclosure>
{/if}

<style>
	.fresh {
		margin: 0;
	}
	.h-chip {
		display: inline-block;
		margin-left: 0.4rem;
		padding: 0.1rem 0.55rem;
		border-radius: var(--r-pill);
		background: var(--accent-soft);
		color: var(--accent-dark, var(--accent));
		font-size: 0.8rem;
		font-weight: 700;
		vertical-align: middle;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.stats > :global(.reveal) {
		display: grid;
	}
	.main :global(.cell) {
		display: grid;
		min-width: 0;
	}
	.main .card {
		margin-bottom: 0;
	}
	.main {
		margin-bottom: 1.25rem;
	}
	.cats {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.9rem;
	}
	.cats li {
		display: grid;
		gap: 0.3rem;
	}
	.cat-line {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: baseline;
	}
	.cat-name {
		font-weight: 600;
	}
	.cat-pct {
		font-weight: 700;
		font-size: 1.05rem;
	}
	.track {
		display: block;
		height: 10px;
		border-radius: var(--r-sm);
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.track.thin {
		height: 6px;
		margin: 0.3rem 0 0.2rem;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: var(--r-sm);
		background: linear-gradient(90deg, var(--sun), var(--sun-strong));
		transform-origin: left center;
	}
	.top .fill {
		background: var(--navy-3);
	}
	@media (prefers-reduced-motion: no-preference) {
		.fill {
			transform: scaleX(0);
			transition: transform 0.8s var(--ease) calc(var(--i, 0) * 60ms + 120ms);
		}
		:global(.grown) .fill {
			transform: none;
		}
	}
	.top {
		list-style: none;
		margin: 0 0 1rem;
		padding: 0;
	}
	.top li {
		display: grid;
		grid-template-columns: 2rem minmax(0, 1fr) max-content;
		gap: 0.75rem;
		align-items: start;
		padding: 0.65rem 0;
		border-bottom: 1px solid #edf0f4;
	}
	.top li:last-child {
		border-bottom: 0;
	}
	.top-n {
		display: grid;
		place-items: center;
		width: 1.9rem;
		height: 1.9rem;
		border-radius: 50%;
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-weight: 700;
		font-size: 0.875rem;
	}
	.top-txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.top-v {
		font-weight: 700;
		white-space: nowrap;
	}
	.top-foot {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.25rem;
		align-items: center;
		justify-content: space-between;
	}
	.go {
		font-weight: 600;
	}
	:global(.disc.card.soft) {
		padding: 0.25rem 1.25rem;
		margin: 0 0 1rem;
	}
	:global(.disc.card.soft) > :global(.disc-btn) {
		padding: 0.85rem 0;
	}
	.sources {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		display: grid;
		gap: 0.6rem;
	}
	.sources li {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 0.75rem;
		align-items: baseline;
	}
	code {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	@media (max-width: 520px) {
		.top li {
			grid-template-columns: 2rem minmax(0, 1fr);
		}
		.top-v {
			grid-column: 2;
		}
	}
	/* Сенсорні екрани: посилання-категорія — ціль ≥ 40 px */
	@media (max-width: 768px) {
		.cat-name {
			display: inline-flex;
			align-items: center;
			min-height: 40px;
		}
		.cats {
			gap: 0.5rem;
		}
		.cats li {
			gap: 0.15rem;
		}
	}
	/* Телефон: компактний рядок «місце · назва (2 рядки) · смужка · категорія | кВт·год» */
	@media (max-width: 640px) {
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.625rem;
			margin-bottom: 1rem;
		}
		.stats > :global(:last-child:nth-child(odd)) {
			grid-column: 1 / -1;
		}
		.top li {
			grid-template-columns: 1.75rem minmax(0, 1fr) max-content;
			grid-template-areas:
				'n name name'
				'n bar bar'
				'n cat val';
			gap: 0 0.6rem;
			padding: 0.55rem 0;
		}
		.top-n {
			grid-area: n;
			width: 1.75rem;
			height: 1.75rem;
			font-size: 0.8125rem;
		}
		.top-txt {
			display: contents;
		}
		.top-txt > a {
			grid-area: name;
			display: -webkit-box;
			-webkit-box-orient: vertical;
			-webkit-line-clamp: 2;
			line-clamp: 2;
			overflow: hidden;
			line-height: 1.35;
		}
		.top-txt > .track {
			grid-area: bar;
		}
		.top-txt > .muted {
			grid-area: cat;
			min-width: 0;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.top-v {
			grid-area: val;
			font-size: 0.875rem;
		}
		.top-foot .btn {
			flex: 1 1 100%;
		}
	}
</style>
