<script lang="ts">
	// «Готовність до блекауту»: скільки годин протримається кожен об'єкт. Лише службові ролі (інакше 403).
	import { onMount } from 'svelte';
	import { errMessage, ApiError } from '#lib/api.ts';
	import { fetchBlackoutAll, fetchOutages, DEPARTMENTS, type Outages } from '#lib/api-v2.ts';
	import { num, dateTime } from '#lib/format.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Status from '#lib/Status.svelte';
	import Icon from '#lib/Icon.svelte';

	type All = Awaited<ReturnType<typeof fetchBlackoutAll>>;
	let data = $state<All | null>(null);
	let error = $state<string | null>(null);
	let forbidden = $state(false);
	let loading = $state(true);

	let out = $state<Outages | null>(null);
	async function load() {
		fetchOutages().then((o) => (out = o)).catch(() => (out = null));
		try {
			data = await fetchBlackoutAll();
			error = null;
			forbidden = false;
		} catch (e) {
			if (e instanceof ApiError && (e.status === 403 || e.status === 401)) forbidden = true;
			else error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	onMount(load);

	let dept = $state('');
	let noGen = $state(false);

	const horizon = $derived(data?.horizon_h ?? 48);
	const hoursOf = (r: { hours_with_generator: number | null; hours_battery_sun: number }) => r.hours_with_generator ?? r.hours_battery_sun;
	const items = $derived(
		(data?.items ?? [])
			.filter((r) => (!dept || r.department === dept) && (!noGen || !r.generator_kw))
			.sort((a, b) => hoursOf(a) - hoursOf(b))
	);
	const tone = (h: number) => (h < 4 ? 'red' : h < 12 ? 'orange' : h >= 24 ? 'green' : 'yellow');
	const hrs = (h: number) => (h >= horizon ? `${horizon}+` : num(h, 1));
	const t = $derived(data?.totals);
</script>

<svelte:head><title>Блекаут · Insight Tool</title></svelte:head>

<header class="page-head">
	<div class="ph-text">
		<h1>Готовність до блекауту</h1>
		{#if data}<p class="ph-sub"><Icon name="clock" size={14} /> Оновлено {dateTime(data.updated_at)}</p>{/if}
	</div>
	<div class="head-side">
		<span class="mok" title="Демонстраційні дані">ДЕМО</span>
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={4} />
{:else if forbidden}
	<p class="lock"><Icon name="lock" size={16} /> Немає доступу</p>
{:else if error && !data}
	<Status {error} retry={load} />
{:else if data && t}
	<div class="kpis">
		<StatCard label="Об'єктів" value={t.objects} icon="building" />
		<StatCard label="З генератором" value={t.with_generator} icon="bolt" tone="good" />
		{#if t.outage_today_h != null}
			<StatCard label="Витримають сьогоднішнє відключення" value={t.hold_today} unit={`з ${t.objects}`} icon="check" tone="good" />
		{:else}
			<StatCard label="Тримаються ≥ 24 год" value={t.hold_24h} icon="check" tone="good" />
		{/if}
		<StatCard label="Менше 4 год" value={t.under_4h} icon="alert" tone={t.under_4h > 0 ? 'warn' : 'good'} />
	</div>

	{#if out && out.queues.length}
		<section class="out" aria-label="Графік відключень сьогодні">
			<p class="out-h">
				<b>Сьогодні за графіком Полтаваобленерго:</b> до {num(out.worst_hours_off ?? 0, 1)} год без світла, найдовше {num(out.worst_longest_h ?? 0, 1)} год поспіль
				<a class="src" href="https://www.poe.pl.ua/disconnection/power-outages/" target="_blank" rel="noopener">poe.pl.ua</a>
			</p>
			{#each out.queues as q (q.queue)}
				{#if q.days[0]}
					<div class="q">
						<span class="qn">Черга {q.queue}</span>
						<span class="cells" title={q.days[0].off.join(', ')}>
							{#each q.days[0].cells as c, i (i)}<i class="c{c}"></i>{/each}
						</span>
						<span class="qh">{num(q.days[0].hours_off, 1)} год</span>
					</div>
				{/if}
			{/each}
			<p class="out-n">Черга кожного закладу в даних міста не вказана — порівнюємо з найдовшим відключенням серед черг.</p>
		</section>
	{/if}

	<div class="fbar">
		<label class="sel">
			<Icon name="building" size={16} />
			<select bind:value={dept} aria-label="Розпорядник">
				<option value="">Усі розпорядники</option>
				{#each DEPARTMENTS as d (d)}<option value={d}>{d}</option>{/each}
			</select>
		</label>
		<button type="button" class="chip" aria-pressed={noGen} onclick={() => (noGen = !noGen)}>
			<Icon name="bolt" size={15} /> Без генератора
		</button>
		<span class="found"><b>{items.length}</b> / {data.items.length}</span>
	</div>

	<section class="card tbl-card">
		<div class="scroll-x">
			<table class="dtbl">
				<thead>
					<tr>
						<th>Об'єкт</th>
						<th class="num">Акумулятор, кВт·год</th>
						<th class="num">Генератор, кВт</th>
						<th class="hcol">Години</th>
					</tr>
				</thead>
				<tbody>
					{#each items as r (r.id)}
						{@const h = hoursOf(r)}
						<tr>
							<td><span class="nm">
								<a href="/object/{r.id}">{r.name}</a>
								<small>{r.department}</small>
							</span></td>
							<td class="num">{r.battery_kwh == null ? '—' : num(r.battery_kwh, 1)}</td>
							<td class="num">
								{#if r.generator_kw}
									{num(r.generator_kw, 1)}
								{:else}—{/if}
							</td>
							<td class="hcol">
								<span class="hb">
									<span class="track"><span class="fill {tone(h)}" style="width: {Math.min(100, (h / horizon) * 100)}%"></span></span>
									<b class="tnum {tone(h)}">{hrs(h)}</b>
								</span>
							</td>
						</tr>
					{:else}
						<tr><td colspan="4" class="empty">—</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

<style>
	.page-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.6rem;
		margin-bottom: 1rem;
	}
	.page-head h1 {
		margin: 0;
	}
	.head-side {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.mok {
		padding: 0.15rem 0.6rem;
		border-radius: var(--r-pill);
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		background: var(--sun-soft);
		color: var(--sun-ink);
		border: 1px dashed #d08a1c;
		cursor: help;
	}
	.ph-sub {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin: 0.15rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.kpis {
		--fs-stat: 1.85rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
		gap: 0.75rem;
		margin-bottom: 1.1rem;
	}
	.lock {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.5rem 1rem;
		border-radius: var(--r-pill);
		border: 1px dashed var(--line-strong);
		background: var(--surface);
		color: var(--text-2);
		font-weight: 600;
	}
	.fbar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.9rem;
	}
	.sel {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 36px;
		padding: 0 0.7rem;
		border-radius: var(--r-input);
		border: 1px solid var(--line);
		background: var(--surface);
		color: var(--muted);
	}
	.sel select {
		border: 0;
		background: none;
		font: inherit;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--text);
		outline: none;
		min-height: 34px;
		max-width: 14rem;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-height: 36px;
		padding: 0 0.85rem;
		border-radius: var(--r-pill);
		border: 1px solid var(--line);
		background: var(--surface);
		font: inherit;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--text-2);
		cursor: pointer;
	}
	.chip[aria-pressed='true'] {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.found {
		margin-left: auto;
		color: var(--muted);
		font-size: 0.875rem;
		font-variant-numeric: tabular-nums;
	}
	.found b {
		color: var(--ink);
	}
	.tbl-card {
		margin: 0;
		padding: 0.5rem;
	}
	.dtbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}
	.dtbl th {
		padding: 0.55rem 0.6rem;
		text-align: left;
		font-weight: 700;
		white-space: nowrap;
	}
	.dtbl td {
		padding: 0.45rem 0.6rem;
		border-top: 1px solid var(--line-soft);
		white-space: nowrap;
	}
	.num {
		text-align: right !important;
		font-variant-numeric: tabular-nums;
	}
	.nm {
		display: flex;
		flex-direction: column;
		min-width: 13rem;
		white-space: normal;
	}
	.nm a {
		font-weight: 600;
		color: var(--text);
	}
	.nm a:hover {
		color: var(--accent);
	}
	.nm small {
		color: var(--muted);
		font-size: 0.75rem;
	}
	.hcol {
		min-width: 10rem;
	}
	.hb {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.track {
		flex: 1;
		height: 0.7rem;
		border-radius: var(--r-sm);
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: var(--r-sm);
	}
	.fill.red {
		background: #c2410c;
	}
	.fill.orange {
		background: #e8890c;
	}
	.fill.yellow {
		background: #d4b012;
	}
	.fill.green {
		background: #1f8a4c;
	}
	.hb b {
		min-width: 2.6rem;
		text-align: right;
	}
	b.red {
		color: #c2410c;
	}
	b.orange {
		color: #b86a05;
	}
	b.green {
		color: #1f8a4c;
	}
	.empty {
		text-align: center;
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.kpis {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.6rem;
		}
	}
	.out {
		margin: 0 0 1rem;
		padding: 0.9rem 1rem;
		border-radius: var(--r-card);
		background: var(--surface, #fff);
		box-shadow: 0 1px 3px rgba(15, 35, 65, 0.08);
		display: grid;
		gap: 0.4rem;
	}
	.out-h {
		margin: 0 0 0.3rem;
		font-size: 0.92rem;
	}
	.src {
		margin-left: 0.4rem;
		font-size: 0.75rem;
	}
	.q {
		display: grid;
		grid-template-columns: 5.5rem 1fr 3.5rem;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.82rem;
	}
	.cells {
		display: grid;
		grid-template-columns: repeat(48, 1fr);
		gap: 1px;
		height: 14px;
	}
	.cells i {
		display: block;
		border-radius: var(--r-sm);
	}
	.cells .c1 {
		background: #cfe9d9;
	}
	.cells .c2 {
		background: #1a2433;
	}
	.cells .c3 {
		background: #9aa5b4;
	}
	.qh {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.out-n {
		margin: 0.2rem 0 0;
		font-size: 0.75rem;
		color: var(--muted);
	}
</style>
