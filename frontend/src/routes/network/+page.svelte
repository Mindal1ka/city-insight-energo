<script lang="ts">
	// «Баланс мережі»: K мережі, різниця генерації/споживання і перерозподіл панелей між закладами.
	import { page } from '$app/state';
	import { errMessage } from '#lib/api.ts';
	import { segIndicator } from '#lib/motion.ts';
	import { fetchNetwork, type Network } from '#lib/api-v2.ts';
	import { PERIODS, K_CLASSES, THRESHOLDS, classifyK, kText, kwh, uah, type Period } from '#lib/api-ses.ts';
	import { num, signed } from '#lib/format.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Status from '#lib/Status.svelte';
	import Icon from '#lib/Icon.svelte';
	import Disclosure from '#lib/Disclosure.svelte';

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
	let showAll = $state(false);
	const shown = $derived(showAll ? (data?.pairs ?? []) : (data?.pairs ?? []).slice(0, 10));
</script>

<svelte:head><title>Баланс мережі · Insight Tool</title></svelte:head>

<header class="page-head">
	<div class="ph-text">
		<h1>Баланс мережі</h1>
		<p class="ph-sub">Скільки згенерували, скільки спожили і куди передати надлишок</p>
	</div>
	<div class="seg" role="radiogroup" aria-label="Період" use:segIndicator>
		{#each PERIODS as p (p.id)}
			<button type="button" role="radio" aria-checked={period === p.id} class:on={period === p.id} onclick={() => (period = p.id)}>
				{p.label}
			</button>
		{/each}
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={4} />
{:else if error && !data}
	<Status {error} retry={() => load(period)} />
{:else if data && t}
	<div class="net" class:stale={loading}>
		<div class="kpis">
			<StatCard label="Згенерували" value={t.gen_kwh} unit="кВт·год" icon="sun" format={(n) => kwh(n).replace(' кВт·год', '')} tone="good" />
			<StatCard label="Спожили" value={t.cons_kwh} unit="кВт·год" icon="bolt" format={(n) => kwh(n).replace(' кВт·год', '')} />
			<StatCard
				label={diffDef ? 'Різниця (дефіцит)' : 'Різниця (надлишок)'}
				value={t.diff_kwh}
				unit="кВт·год"
				icon={diffDef ? 'alert' : 'chart'}
				format={(n) => signed(n, 0)}
				tone={diffDef ? 'bad' : 'neutral'}
				toneLabel={diffDef ? 'дефіцит' : 'надлишок'}
			/>
			<StatCard label="K мережі · за {unit}" value={t.k} decimals={2} icon="gauge">
				<div class="kmini" style="--kc:{cls.color}">
					<div class="scale" aria-hidden="true">
						<span class="seg-b" style="left:0;width:{pos(THRESHOLDS.low)};background:{K_CLASSES[1].color}"></span>
						<span class="seg-b" style="left:{pos(THRESHOLDS.low)};width:calc({pos(THRESHOLDS.high)} - {pos(THRESHOLDS.low)});background:{K_CLASSES[0].color}"></span>
						<span class="seg-b" style="left:{pos(THRESHOLDS.high)};right:0;background:{K_CLASSES[2].color}"></span>
						{#if t.k != null}<span class="mark" style="left:{pos(t.k)}"></span>{/if}
					</div>
					<span class="kcls"><span aria-hidden="true"><Icon name={cls.svg} size={12} stroke={2.6} /></span> {cls.short} · {kText(t.k)}</span>
				</div>
			</StatCard>
		</div>

		<section class="card pairs" aria-label="Перерозподіл надлишку">
			<h2>Перерозподіл надлишку</h2>

			{#if data.pairs === null}
				<a class="lock" href="/login?next={encodeURIComponent(page.url.pathname)}">
					<Icon name="lock" size={16} /> Деталі після входу
				</a>
			{:else if data.pairs.length === 0}
				<p class="empty">—</p>
			{:else}
				<ul class="plist">
					{#each shown as p (p.from_id + '-' + p.to_id)}
						<li>
							<div class="route">
								<a href="/object/{p.from_id}">{p.from_name}</a>
								<Icon name="arrow-right" size={16} />
								<a href="/object/{p.to_id}">{p.to_name}</a>
							</div>
							<div class="nums">
								<span>{num(p.move_kw, 0)} кВт</span>
								<span class="gain">{uah(p.saved_uah_year)}/рік</span>
							</div>
						</li>
					{/each}
				</ul>
				{#if data.pairs.length > 10}
					<button type="button" class="more" onclick={() => (showAll = !showAll)}>
						{showAll ? 'Згорнути' : `Показати всі (${data.pairs.length})`}
					</button>
				{/if}
			{/if}
		</section>

		<Disclosure summary="Детальніше">
			<div class="det">
				<span><b>{kwh(t.surplus_kwh)}</b> не використано ({uah(t.surplus_uah)})</span>
				<span><b>{kwh(t.grid_kwh)}</b> з мережі</span>
				<span><b>{t.donors}</b> донорів · <b>{t.takers}</b> реципієнтів · <b>{t.pairs}</b> пар · <b>{num(t.move_kw, 0)}</b> кВт панелей</span>
			</div>
			{#if data.note}<p class="note">{data.note}</p>{/if}
		</Disclosure>
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
	.ph-sub {
		margin: 0.15rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.seg {
		display: inline-flex;
		padding: 3px;
		border-radius: var(--r-btn);
		background: var(--surface);
		border: 1px solid var(--line);
	}
	.seg button {
		min-height: 32px;
		padding: 0.2rem 0.9rem;
		border: 0;
		border-radius: var(--r-input);
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
	.seg:global(.has-ind) button.on {
		background: transparent;
	}
	.seg :global(.seg-ind) {
		background: var(--navy);
		box-shadow: none;
		border-radius: var(--r-input);
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

	/* K: мала шкала */
	.kmini {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin-top: 0.3rem;
	}
	.scale {
		position: relative;
		height: 8px;
		border-radius: var(--r-sm);
	}
	.seg-b {
		position: absolute;
		top: 0;
		bottom: 0;
	}
	.seg-b:first-child {
		border-radius: var(--r-sm) 0 0 var(--r-sm);
	}
	.seg-b:nth-child(3) {
		border-radius: 0 var(--r-sm) var(--r-sm) 0;
	}
	.mark {
		position: absolute;
		top: -4px;
		width: 4px;
		height: 16px;
		margin-left: -2px;
		border-radius: var(--r-sm);
		background: var(--ink);
		box-shadow: 0 0 0 2px #fff;
	}
	.kcls {
		font-size: 0.8125rem;
		font-weight: 700;
		color: var(--kc);
	}

	/* Пари */
	.pairs {
		margin: 0 0 0.9rem;
	}
	.pairs h2 {
		margin: 0 0 0.4rem;
		font-size: 1.08rem;
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
		padding: 0.55rem 0;
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
	.nums {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		font-size: 0.9rem;
		color: var(--text-2);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.gain {
		color: #1f8a4c;
		font-weight: 700;
	}
	.more {
		margin-top: 0.5rem;
		padding: 0.35rem 0.9rem;
		border-radius: var(--r-btn);
		border: 1px solid var(--line);
		background: var(--surface);
		font: inherit;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--text-2);
		cursor: pointer;
	}
	.more:hover {
		border-color: var(--navy);
		color: var(--navy);
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
	.det {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		font-size: 0.9rem;
		color: var(--text-2);
	}
	.det b {
		color: var(--ink);
	}
	.note {
		margin: 0.6rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.kpis {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.6rem;
		}
	}
</style>
