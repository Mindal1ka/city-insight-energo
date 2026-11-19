<script lang="ts">
	// «Готовність до блекауту»: скільки годин протримається кожен об'єкт. Лише службові ролі (інакше 403).
	import { onMount } from 'svelte';
	import { errMessage, ApiError } from '#lib/api.ts';
	import { fetchBlackoutAll, DEPARTMENTS } from '#lib/api-v2.ts';
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

	async function load() {
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
	<h1>Готовність до блекауту</h1>
	<div class="head-side">
		<span class="mok" title="Демонстраційні дані">МОК</span>
		{#if data}<span class="upd"><Icon name="clock" size={14} /> {dateTime(data.updated_at)}</span>{/if}
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={5} />
{:else if forbidden}
	<p class="lock"><Icon name="lock" size={16} /> Немає доступу</p>
{:else if error && !data}
	<Status {error} retry={load} />
{:else if data && t}
	<div class="kpis">
		<StatCard label="Об'єктів" value={t.objects} icon="building" />
		<StatCard label="З генератором" value={t.with_generator} icon="bolt" tone="good" />
		<StatCard label="З акумулятором" value={t.with_battery} icon="battery" />
		<StatCard label="Тримають ≥ 24 год" value={t.hold_24h} icon="check" tone="good" />
		<StatCard label="Менше 4 год" value={t.under_4h} icon="alert" tone={t.under_4h > 0 ? 'warn' : 'good'} />
	</div>

	<div class="fbar">
		<label class="sel">
			<Icon name="building" size={16} />
			<select bind:value={dept} aria-label="Департамент">
				<option value="">Усі департаменти</option>
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
						<th class="num">Акум., кВт·год</th>
						<th class="num">Генератор, кВт</th>
						<th class="hcol">Годин автономії</th>
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
									{#if r.generator_source === 'МОК'}<span class="mok sm">МОК</span>{/if}
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
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		background: var(--sun-soft);
		color: var(--sun-ink);
		border: 1px dashed #d08a1c;
		cursor: help;
	}
	.mok.sm {
		padding: 0 0.4rem;
		font-size: 0.65rem;
		margin-left: 0.3rem;
	}
	.upd {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
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
		border-radius: 999px;
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
		border-radius: 999px;
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
		border-radius: 999px;
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
		border-radius: 999px;
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: 999px;
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
</style>
