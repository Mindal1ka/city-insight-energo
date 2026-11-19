<script lang="ts">
	// «Розподіл енергії» (вікно 3): live по всіх СЕС громади. Автооновлення щохвилини.
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { errMessage } from '#lib/api.ts';
	import { fetchLive, DEPARTMENTS, type LiveAll } from '#lib/api-v2.ts';
	import { num, signed, dateTime } from '#lib/format.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Status from '#lib/Status.svelte';
	import Icon from '#lib/Icon.svelte';

	let data = $state<LiveAll | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	async function load() {
		try {
			data = await fetchLive();
			error = null;
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		load();
		const t = setInterval(load, 60_000);
		return () => clearInterval(t);
	});

	let dept = $state('');
	let onlyShort = $state(false);
	let onlyOff = $state(false);

	const t = $derived(data?.totals);
	const restricted = $derived(!!data && data.items.length === 0);
	const items = $derived(
		(data?.items ?? [])
			.filter((i) => (!dept || i.department === dept) && (!onlyShort || !i.enough) && (!onlyOff || i.status === 'offline'))
			.sort((a, b) => a.balance_kwh - b.balance_kwh)
	);
	const reserve = $derived(t ? t.available_kwh - t.demand_left_kwh : 0);
	const gridTone = $derived(!t ? 'neutral' : t.grid_kw > 0 ? 'warn' : 'good');
	const nf = (v: number | null | undefined, d = 1) => num(v, d);
</script>

<svelte:head><title>Розподіл енергії · Insight Tool</title></svelte:head>

<header class="page-head">
	<h1>Розподіл енергії</h1>
	<div class="head-side">
		<span class="mok" title="Дані інверторів підключаться через API">МОК</span>
		{#if data}<span class="upd"><Icon name="clock" size={14} /> {dateTime(data.updated_at)}</span>{/if}
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={5} />
{:else if error && !data}
	<Status {error} retry={load} />
{:else if data && t}
	<div class="kpis">
		<StatCard label="Генерація зараз" value={t.gen_kw} decimals={1} unit="кВт" icon="sun" tone="good" />
		<StatCard label="Навантаження" value={t.load_kw} decimals={1} unit="кВт" icon="bolt" />
		<StatCard
			label={t.grid_kw > 0 ? 'З мережі (купуємо)' : 'У мережу (віддаємо)'}
			value={Math.abs(t.grid_kw)}
			decimals={1}
			unit="кВт"
			icon="plug"
			tone={gridTone}
		/>
		<StatCard label="СЕС онлайн" value={t.online} icon="check" tone="good">
			<span class="off" class:zero={t.offline === 0}><span class="dot off-dot"></span>{t.offline} офлайн</span>
		</StatCard>
		<StatCard label="В акумуляторах" value={t.battery_kwh_now} decimals={0} unit="кВт·год" icon="battery" />
	</div>

	<section class="card bal" class:short={!t.enough} aria-label="Баланс до кінця дня">
		<div class="bal-sign" aria-hidden="true">{t.enough ? '+' : '−'}</div>
		<div class="bal-main">
			<div class="bal-title">Доступно до кінця дня</div>
			<div class="bal-row">
				<span class="bal-n">{num(t.available_kwh, 0)}</span>
				<span class="vs">vs</span>
				<span class="bal-n dem">{num(t.demand_left_kwh, 0)}</span>
				<span class="u">кВт·год</span>
			</div>
			<div class="bal-sub">
				<span class="pillb" class:ok={t.enough} class:bad={!t.enough}>
					{t.enough ? 'Вистачає' : 'Не вистачає'} · {signed(t.balance_kwh, 0)} кВт·год
				</span>
				<span class="res">Запас {signed(reserve, 0)}</span>
			</div>
		</div>
	</section>

	{#if restricted}
		<a class="lock" href="/login?next={encodeURIComponent(page.url.pathname)}">
			<Icon name="lock" size={16} /> Деталі після входу
		</a>
	{:else}
		<div class="fbar">
			<label class="sel">
				<Icon name="building" size={16} />
				<select bind:value={dept} aria-label="Департамент">
					<option value="">Усі департаменти</option>
					{#each DEPARTMENTS as d (d)}<option value={d}>{d}</option>{/each}
				</select>
			</label>
			<button type="button" class="chip" aria-pressed={onlyShort} onclick={() => (onlyShort = !onlyShort)}>
				<Icon name="alert" size={15} /> Не вистачає
			</button>
			<button type="button" class="chip" aria-pressed={onlyOff} onclick={() => (onlyOff = !onlyOff)}>
				<span class="dot off-dot"></span> Офлайн
			</button>
			<span class="found"><b>{items.length}</b> / {data.items.length}</span>
		</div>

		<section class="card tbl-card">
			<div class="scroll-x">
				<table class="dtbl">
					<thead>
						<tr>
							<th>Об'єкт</th>
							<th class="num">Ген., кВт</th>
							<th class="num">Нав., кВт</th>
							<th class="num">Мережа, кВт</th>
							<th class="num">SOC</th>
							<th class="num">Пік, кВт</th>
							<th class="num">Баланс, кВт·год</th>
						</tr>
					</thead>
					<tbody>
						{#each items as r (r.id)}
							<tr>
								<td><div class="tn">
									<span class="dot" class:on={r.status === 'online'} class:off-dot={r.status !== 'online'} title={r.status}></span>
									<span class="nm">
										<a href="/object/{r.id}">{r.name}</a>
										<small>{r.department}</small>
									</span>
								</div></td>
								<td class="num">{nf(r.gen_kw)}</td>
								<td class="num">{nf(r.load_kw)}</td>
								<td class="num" class:buy={r.grid_kw > 0} class:give={r.grid_kw < 0}>{signed(r.grid_kw)}</td>
								<td class="num">{r.soc_pct == null ? '—' : `${num(r.soc_pct, 0)} %`}</td>
								<td class="num">{nf(r.peak_kw)}</td>
								<td class="num bal-c" class:neg={r.balance_kwh < 0} class:pos={r.balance_kwh >= 0}>{signed(r.balance_kwh, 0)}</td>
							</tr>
						{:else}
							<tr><td colspan="7" class="empty">—</td></tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}
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
	.off {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-weight: 700;
		color: var(--deficit-ink, #9a330a);
		font-size: 0.9rem;
	}
	.off.zero {
		color: var(--muted);
	}
	.dot {
		display: inline-block;
		flex: none;
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		background: #1f8a4c;
	}
	.dot.off-dot,
	.off-dot {
		background: #c2410c;
	}

	/* Баланс */
	.bal {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		margin: 0 0 1.1rem;
		padding: 1.1rem 1.4rem;
		border-left: 6px solid #1f8a4c;
	}
	.bal.short {
		border-left-color: #c2410c;
	}
	.bal-sign {
		display: grid;
		place-items: center;
		width: 4.5rem;
		height: 4.5rem;
		flex: none;
		border-radius: 50%;
		font-size: 3.2rem;
		font-weight: 800;
		line-height: 1;
		background: #e3f4ea;
		color: #1f8a4c;
	}
	.short .bal-sign {
		background: #fdebe2;
		color: #c2410c;
	}
	.bal-title {
		font-weight: 600;
		color: var(--text-2);
		font-size: 0.95rem;
	}
	.bal-row {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.2rem 0.6rem;
	}
	.bal-n {
		font-size: 2.2rem;
		font-weight: 700;
		color: var(--ink);
		font-variant-numeric: tabular-nums;
	}
	.bal-n.dem {
		color: var(--muted);
	}
	.vs,
	.u {
		color: var(--muted);
		font-weight: 600;
	}
	.bal-sub {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.6rem;
		margin-top: 0.35rem;
	}
	.pillb {
		padding: 0.15rem 0.7rem;
		border-radius: 999px;
		font-weight: 700;
		font-size: 0.875rem;
	}
	.pillb.ok {
		background: #e3f4ea;
		color: #14632b;
	}
	.pillb.bad {
		background: #fdebe2;
		color: #9a330a;
	}
	.res {
		color: var(--muted);
		font-size: 0.875rem;
		font-variant-numeric: tabular-nums;
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
		text-decoration: none;
	}
	.lock:hover {
		border-color: var(--navy);
		color: var(--navy);
	}

	/* Фільтри */
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

	/* Таблиця */
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
	.tn {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		white-space: normal;
		min-width: 15rem;
	}
	.nm {
		display: flex;
		flex-direction: column;
		min-width: 0;
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
	.buy {
		color: #9a330a;
	}
	.give {
		color: #1f6fd1;
	}
	.bal-c {
		font-weight: 700;
	}
	.bal-c.neg {
		color: #c2410c;
	}
	.bal-c.pos {
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
		.bal {
			padding: 0.9rem;
			gap: 0.8rem;
		}
		.bal-sign {
			width: 3.2rem;
			height: 3.2rem;
			font-size: 2.3rem;
		}
		.bal-n {
			font-size: 1.6rem;
		}
	}
</style>
