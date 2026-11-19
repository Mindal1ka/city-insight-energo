<script lang="ts">
	// «Баланс мережі закладів» (вікно 4): K мережі, надлишок і перерозподіл панелей між закладами.
	import { page } from '$app/state';
	import { errMessage } from '#lib/api.ts';
	import { fetchNetwork, type Network } from '#lib/api-v2.ts';
	import { PERIODS, K_CLASSES, THRESHOLDS, classifyK, kText, kwh, uah, type Period } from '#lib/api-ses.ts';
	import { num, signed } from '#lib/format.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Status from '#lib/Status.svelte';
	import Icon from '#lib/Icon.svelte';

	let period = $state<Period>('year');
	let data = $state<Network | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let seq = 0;

	async function load(p: Period) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const d = await fetchNetwork(p);
			if (my === seq) data = d;
		} catch (e) {
			if (my === seq) error = errMessage(e);
		} finally {
			if (my === seq) loading = false;
		}
	}
	$effect(() => {
		load(period);
	});

	const t = $derived(data?.totals);
	const cls = $derived(K_CLASSES.find((c) => c.id === classifyK(t?.k, true)) ?? K_CLASSES[4]);
	const diffDef = $derived((t?.diff_kwh ?? 0) < 0);
	// шкала 0…2: позиція маркера K та порогів
	const SCALE = 2;
	const pos = (v: number) => `${Math.max(0, Math.min(1, v / SCALE)) * 100}%`;
	const unit = $derived(period === 'year' ? 'рік' : period === 'month' ? 'місяць' : 'доба');
</script>

<svelte:head><title>Баланс мережі закладів · City Insight Map · Енергія</title></svelte:head>

<header class="page-head">
	<h1>Баланс мережі закладів</h1>
	<div class="seg" role="radiogroup" aria-label="Період">
		{#each PERIODS as p (p.id)}
			<button type="button" role="radio" aria-checked={period === p.id} class:on={period === p.id} onclick={() => (period = p.id)}>
				{p.label}
			</button>
		{/each}
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={6} />
{:else if error && !data}
	<Status {error} retry={() => load(period)} />
{:else if data && t}
	<div class="net" class:stale={loading}>
		<div class="kpis">
			<StatCard label="Панелі згенерували" value={t.gen_kwh} unit="кВт·год" icon="sun" format={(n) => kwh(n).replace(' кВт·год', '')} tone="good" />
			<StatCard label="Спожито" value={t.cons_kwh} unit="кВт·год" icon="bolt" format={(n) => kwh(n).replace(' кВт·год', '')} />
			<StatCard
				label={diffDef ? 'Дефіцит' : 'Надлишок'}
				value={Math.abs(t.diff_kwh)}
				unit="кВт·год"
				icon={diffDef ? 'alert' : 'chart'}
				format={(n) => kwh(n).replace(' кВт·год', '')}
				tone={diffDef ? 'bad' : 'neutral'}
				toneLabel={diffDef ? 'дефіцит' : 'надлишок'}
			/>
			<StatCard label="Не використано" value={t.surplus_kwh} unit="кВт·год" icon="battery" format={(n) => kwh(n).replace(' кВт·год', '')}>
				<span class="sub">{uah(t.surplus_uah)}</span>
			</StatCard>
			<StatCard label="З мережі" value={t.grid_kwh} unit="кВт·год" icon="plug" format={(n) => kwh(n).replace(' кВт·год', '')} />
		</div>

		<section class="card kcard" style="--kc:{cls.color};--ks:{cls.soft}">
			<div class="k-top">
				<span class="k-big">K <b>{kText(t.k)}</b></span>
				<span class="k-badge"><span aria-hidden="true">{cls.icon}</span> {cls.short}</span>
				<span class="k-per">за {unit}</span>
			</div>
			<div class="scale" aria-hidden="true">
				<span class="seg-b" style="left:0;width:{pos(THRESHOLDS.low)};background:{K_CLASSES[1].color}"></span>
				<span class="seg-b" style="left:{pos(THRESHOLDS.low)};width:calc({pos(THRESHOLDS.high)} - {pos(THRESHOLDS.low)});background:{K_CLASSES[0].color}"></span>
				<span class="seg-b" style="left:{pos(THRESHOLDS.high)};right:0;background:{K_CLASSES[2].color}"></span>
				{#if t.k != null}<span class="mark" style="left:{pos(t.k)}"></span>{/if}
			</div>
			<div class="ticks" aria-hidden="true">
				<span style="left:0">0</span>
				<span style="left:{pos(THRESHOLDS.low)}">0,8</span>
				<span style="left:50%">1</span>
				<span style="left:{pos(THRESHOLDS.high)}">1,2</span>
				<span style="left:100%">2</span>
			</div>
		</section>

		<section class="card pairs" aria-label="Перерозподіл надлишку">
			<h2><Icon name="grid" size={18} /> Перерозподіл надлишку</h2>
			<div class="counts">
				<span><b>{t.donors}</b> донорів</span>
				<span><b>{t.takers}</b> реципієнтів</span>
				<span><b>{t.pairs}</b> пар</span>
				<span><b>{num(t.move_kw, 0)}</b> кВт панелей</span>
			</div>

			{#if data.pairs === null}
				<a class="lock" href="/login?next={encodeURIComponent(page.url.pathname)}">
					<Icon name="lock" size={16} /> Деталі після входу
				</a>
			{:else if data.pairs.length === 0}
				<p class="empty">—</p>
			{:else}
				<ul class="plist">
					{#each data.pairs as p (p.from_id + '-' + p.to_id)}
						<li>
							<div class="route">
								<a href="/object/{p.from_id}">{p.from_name}</a>
								<Icon name="arrow-right" size={16} />
								<a href="/object/{p.to_id}">{p.to_name}</a>
								{#if p.same_department}
									<span class="same" title={p.department_from}>один департамент</span>
								{/if}
							</div>
							<div class="nums">
								<span class="mv"><b>{num(p.move_kw, 1)}</b> кВт панелей</span>
								<span><Icon name="pin" size={13} /> {p.distance_km == null ? '—' : `${num(p.distance_km, 1)} км`}</span>
								<span class="gain">{signed(p.gain_kwh_year, 0)} кВт·год/рік</span>
								<span class="gain">{uah(p.saved_uah_year)}/рік</span>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
			{#if data.note}<p class="note">{data.note}</p>{/if}
		</section>
	</div>
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
	.seg {
		display: inline-flex;
		padding: 3px;
		border-radius: 999px;
		background: var(--surface);
		border: 1px solid var(--line);
	}
	.seg button {
		min-height: 32px;
		padding: 0.2rem 0.9rem;
		border: 0;
		border-radius: 999px;
		background: none;
		font: inherit;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--text-2);
		cursor: pointer;
	}
	.seg button.on {
		background: var(--navy);
		color: #fff;
	}
	.net {
		transition: opacity var(--dur-base);
	}
	.net.stale {
		opacity: 0.6;
	}
	.kpis {
		--fs-stat: 1.85rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
		gap: 0.75rem;
		margin-bottom: 1.1rem;
	}
	.sub {
		font-weight: 700;
		color: var(--text-2);
		font-size: 0.95rem;
	}

	/* K */
	.kcard {
		margin: 0 0 1.1rem;
		padding: 1.1rem 1.4rem 1.6rem;
		border-left: 6px solid var(--kc);
	}
	.k-top {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.4rem 0.9rem;
		margin-bottom: 1rem;
	}
	.k-big {
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--muted);
	}
	.k-big b {
		font-size: 2.6rem;
		color: var(--ink);
		font-variant-numeric: tabular-nums;
	}
	.k-badge {
		padding: 0.15rem 0.75rem;
		border-radius: 999px;
		font-weight: 700;
		background: var(--ks);
		color: var(--kc);
		border: 1.5px solid var(--kc);
	}
	.k-per {
		color: var(--muted);
		font-size: 0.875rem;
	}
	.scale {
		position: relative;
		height: 12px;
		border-radius: 6px;
		overflow: visible;
	}
	.seg-b {
		position: absolute;
		top: 0;
		bottom: 0;
	}
	.seg-b:first-child {
		border-radius: 6px 0 0 6px;
	}
	.seg-b:nth-child(3) {
		border-radius: 0 6px 6px 0;
	}
	.mark {
		position: absolute;
		top: -6px;
		width: 4px;
		height: 24px;
		margin-left: -2px;
		border-radius: 2px;
		background: var(--ink);
		box-shadow: 0 0 0 2px #fff;
	}
	.ticks {
		position: relative;
		height: 1.2rem;
		margin-top: 0.7rem;
		font-size: 0.75rem;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.ticks span {
		position: absolute;
		transform: translateX(-50%);
	}
	.ticks span:first-child {
		transform: none;
	}
	.ticks span:last-child {
		transform: translateX(-100%);
	}

	/* Пари */
	.pairs {
		margin: 0;
	}
	.pairs h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 0.6rem;
		font-size: 1.08rem;
	}
	.counts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		margin-bottom: 0.8rem;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.counts b {
		color: var(--ink);
		font-size: 1.15rem;
		font-variant-numeric: tabular-nums;
	}
	.plist {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.plist li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.3rem 1rem;
		padding: 0.6rem 0;
		border-top: 1px solid var(--line-soft);
	}
	.route {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.3rem 0.5rem;
		min-width: 0;
		font-weight: 600;
	}
	.route a {
		color: var(--text);
	}
	.route a:hover {
		color: var(--accent);
	}
	.route :global(svg) {
		color: var(--muted);
		flex: none;
	}
	.same {
		padding: 0.05rem 0.55rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 700;
		background: #e3f4ea;
		color: #14632b;
	}
	.nums {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.9rem;
		font-size: 0.875rem;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.nums span {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.mv b {
		color: var(--ink);
		font-size: 1rem;
	}
	.gain {
		color: #1f8a4c;
		font-weight: 700;
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
	.empty {
		color: var(--muted);
		margin: 0;
	}
	.note {
		margin: 0.8rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.kpis {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.6rem;
		}
		.k-big b {
			font-size: 2rem;
		}
		.kcard {
			padding: 0.9rem 0.9rem 1.4rem;
		}
	}
</style>
