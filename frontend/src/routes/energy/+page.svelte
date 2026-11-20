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
	import { auth } from '#lib/auth.svelte.ts';

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

	const t = $derived(data?.totals);
	const restricted = $derived(!!data && data.items.length === 0);
	const items = $derived(
		(data?.items ?? [])
			.filter((i) => (!dept || i.department === dept) && (!onlyShort || !i.enough))
			.sort((a, b) => a.balance_kwh - b.balance_kwh)
	);
	const gridTone = $derived(!t ? 'neutral' : t.grid_kw > 0 ? 'warn' : 'good');
	const nf = (v: number | null | undefined, d = 1) => num(v, d);
	// «Заряд» — дані акумуляторів: фінансовий орган їх не бачить (бекенд віддає null) — колонку ховаємо
	const showSoc = $derived(auth.user?.role !== 'finance' && (data?.items ?? []).some((r) => r.soc_pct != null));
</script>

<svelte:head><title>Розподіл енергії · Insight Tool</title></svelte:head>

<header class="page-head">
	<div class="ph-text">
		<h1>Розподіл енергії зараз</h1>
		{#if data}<p class="ph-sub"><Icon name="clock" size={14} /> Оновлено {dateTime(data.updated_at)}</p>{/if}
	</div>
	<div class="head-side">
		<span class="mok" title="Дані інверторів підключаться через API">ДЕМО</span>
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={4} />
{:else if error && !data}
	<Status {error} retry={load} />
{:else if data && t}
	<div class="kpis">
		<StatCard label="Генерація зараз" value={t.gen_kw} decimals={1} unit="кВт" icon="sun" tone="good" />
		<StatCard label="Навантаження" value={t.load_kw} decimals={1} unit="кВт" icon="bolt" />
		<StatCard
			label={t.grid_kw > 0 ? 'Мережа (купуємо)' : 'Мережа (віддаємо)'}
			value={Math.abs(t.grid_kw)}
			decimals={1}
			unit="кВт"
			icon="plug"
			tone={gridTone}
		/>
		<StatCard
			label="Баланс до кінця дня"
			value={t.balance_kwh}
			decimals={0}
			unit="кВт·год"
			icon={t.enough ? 'check' : 'alert'}
			tone={t.enough ? 'good' : 'bad'}
			format={(n) => signed(n, 0)}
		/>
	</div>

	{#if restricted}
		<a class="lock" href="/login?next={encodeURIComponent(page.url.pathname)}">
			<Icon name="lock" size={16} /> Деталі після входу
		</a>
	{:else}
		<div class="fbar">
			<label class="sel">
				<Icon name="building" size={16} />
				<select bind:value={dept} aria-label="Розпорядник">
					<option value="">Усі розпорядники</option>
					{#each DEPARTMENTS as d (d)}<option value={d}>{d}</option>{/each}
				</select>
			</label>
			<button type="button" class="chip" aria-pressed={onlyShort} onclick={() => (onlyShort = !onlyShort)}>
				<Icon name="alert" size={15} /> Лише проблемні
			</button>
			<span class="found"><b>{items.length}</b> / {data.items.length}</span>
		</div>

		<section class="card tbl-card">
			<div class="scroll-x">
				<table class="dtbl">
					<thead>
						<tr>
							<th>Об'єкт</th>
							<th class="num">Генерація, кВт</th>
							<th class="num">Навантаження, кВт</th>
							{#if showSoc}<th class="num">Заряд</th>{/if}
							<th class="num">Баланс, кВт·год</th>
						</tr>
					</thead>
					<tbody>
						{#each items as r (r.id)}
							<tr>
								<td><div class="tn">
									<span class="dot" class:off-dot={r.status !== 'online'} title={r.status}></span>
									<span class="nm">
										<a href="/object/{r.id}">{r.name}</a>
										<small>{r.department}</small>
									</span>
								</div></td>
								<td class="num">{nf(r.gen_kw)}</td>
								<td class="num">{nf(r.load_kw)}</td>
								{#if showSoc}<td class="num">{r.soc_pct == null ? '—' : `${num(r.soc_pct, 0)} %`}</td>{/if}
								<td class="num bal-c" class:neg={r.balance_kwh < 0} class:pos={r.balance_kwh >= 0}>{signed(r.balance_kwh, 0)}</td>
							</tr>
						{:else}
							<tr><td colspan={showSoc ? 5 : 4} class="empty">—</td></tr>
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
	.ph-sub {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin: 0.15rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
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
	.kpis {
		--fs-stat: 1.85rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
		gap: 0.75rem;
		margin-bottom: 1.1rem;
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
	}
</style>
