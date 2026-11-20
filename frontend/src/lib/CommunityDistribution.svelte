<script lang="ts">
	// «Розподілення енергії» для всієї громади: зведення по об'єктах з СЕС + де дефіцит, де надлишок
	import { api, errMessage, type SiteItem, type ViewKey } from './api.ts';
	import { aggregate, type Community } from './community.ts';
	import { num, signed, moment } from './format.ts';
	import { withView } from './view.ts';
	import Distribution from './Distribution.svelte';
	import HourlyChart from './HourlyChart.svelte';
	import DemoPill from './DemoPill.svelte';
	import Status from './Status.svelte';

	let { items, view, now }: { items: SiteItem[]; view: ViewKey; now: string } = $props();

	let data = $state<Community | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	const ses = $derived(items.filter((i) => i.has_ses));
	const deficit = $derived(
		ses.filter((i) => i.status === 'deficit').sort((a, b) => (a.balance_kwh_today ?? 0) - (b.balance_kwh_today ?? 0))
	);
	const surplus = $derived(
		ses.filter((i) => i.status === 'surplus').sort((a, b) => (b.balance_kwh_today ?? 0) - (a.balance_kwh_today ?? 0))
	);
	const maxAbs = $derived(Math.max(1, ...ses.map((i) => Math.abs(i.balance_kwh_today ?? 0))));
	const m = $derived(moment(now));

	let seq = 0;
	async function load(ids: number[], v: ViewKey) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const details = await Promise.all(ids.map((id) => api.site(id, v)));
			if (my === seq) data = aggregate(details);
		} catch (e) {
			if (my === seq) error = errMessage(e);
		} finally {
			if (my === seq) loading = false;
		}
	}
	// Рядок-ключ: перезавантажуємо лише коли справді змінився набір об'єктів або момент
	const idsKey = $derived(ses.map((i) => i.id).join(','));
	$effect(() => {
		load(idsKey ? idsKey.split(',').map(Number) : [], view);
	});
</script>

<Status loading={loading && !data} {error} retry={() => load(ses.map((i) => i.id), view)} />

{#if data}
	<div class="community fade-in" class:stale={loading}>
		<p class="scope">
			Зведення по <strong>{data.count}</strong> об’єктах громади з сонячними станціями — так, ніби
			енергію можна було б перерозподіляти між ними.
		</p>

		<Distribution
			d={data.distribution}
			scope="community"
			peakNote="Сумарне навантаження об’єктів з СЕС"
		/>

		<section class="panel chart" aria-labelledby="c-chart-h">
			<div class="panel-head">
				<div>
					<h2 id="c-chart-h">Громада за добу, погодинно</h2>
					<p class="muted small">Сума по {data.count} об’єктах з СЕС · заряд — середньозважений</p>
				</div>
				<DemoPill />
			</div>
			<HourlyChart
				hours={data.hourly}
				nowHour={m?.hour ?? null}
				nowMinute={m?.minute ?? 0}
				peakHour={data.distribution.peak_hour}
			/>
		</section>

		<div class="lists">
			{#each [{ key: 'deficit', title: 'Де дефіцит', list: deficit, empty: 'Жоден об’єкт не в дефіциті' }, { key: 'surplus', title: 'Де надлишок', list: surplus, empty: 'Зараз жоден об’єкт не має надлишку — так буває взимку. Перемкніть на «Літній день».' }] as col (col.key)}
				<section class="panel list {col.key}" aria-labelledby="l-{col.key}">
					<div class="panel-head">
						<h2 id="l-{col.key}">
							<span class="lsign" aria-hidden="true">{col.key === 'deficit' ? '−' : '+'}</span>
							{col.title}
							<span class="count">{col.list.length}</span>
						</h2>
						<span class="muted small">баланс за сьогодні, кВт·год</span>
					</div>
					{#if col.list.length}
						<ol>
							{#each col.list as it (it.id)}
								<li>
									<a href={withView(`/object/${it.id}`, view, { tab: 'distribution' })}>
										<span class="nm" title={it.name}>{it.name}</span>
										<span class="bar-wrap" aria-hidden="true">
											<span class="bar" style="width: {(Math.abs(it.balance_kwh_today ?? 0) / maxAbs) * 100}%"></span>
										</span>
										<span class="v tnum">{signed(it.balance_kwh_today, 1)}</span>
									</a>
								</li>
							{/each}
						</ol>
					{:else}
						<p class="empty">{col.empty}</p>
					{/if}
				</section>
			{/each}
		</div>
		<p class="muted small">
			Пари «дефіцит — надлишок» показують, між ким енергокооператив громади міг би обмінюватися енергією в майбутньому.
			Сумарний надлишок сьогодні: <strong class="tnum">{num(surplus.reduce((a, i) => a + (i.balance_kwh_today ?? 0), 0), 1)} кВт·год</strong>.
		</p>
	</div>
{/if}

<style>
	.community {
		display: grid;
		gap: 1.25rem;
		transition: opacity 0.2s;
	}
	.stale {
		opacity: 0.55;
	}
	.scope {
		margin: 0;
		color: #3d4857;
	}
	.chart h2 {
		margin: 0;
	}
	.chart .small {
		margin: 0.15rem 0 0;
	}
	.lists {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1.25rem;
	}
	.list h2 {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		font-size: 1.2rem;
	}
	.lsign {
		display: grid;
		place-items: center;
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 50%;
		color: #fff;
		font-weight: 800;
	}
	.deficit .lsign {
		background: var(--deficit);
	}
	.surplus .lsign {
		background: var(--surplus);
	}
	.count {
		font-size: 0.85rem;
		font-weight: 700;
		padding: 0.05rem 0.55rem;
		border-radius: var(--r-pill);
		background: var(--neutral-soft);
		color: #3d4857;
	}
	ol {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 27rem;
		overflow: auto;
		padding-bottom: 1.5rem;
		mask-image: linear-gradient(to bottom, #000 calc(100% - 2rem), transparent);
	}
	li a {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 7rem 4.5rem;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 0.6rem;
		border-radius: var(--r-btn);
		color: var(--text);
		text-decoration: none;
	}
	li a:hover {
		background: #f3f6fa;
		color: var(--text);
	}
	li + li {
		border-top: 1px solid #edf1f5;
	}
	.nm {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 500;
	}
	.bar-wrap {
		height: 10px;
		border-radius: var(--r-sm);
		background: #edf1f5;
		overflow: hidden;
	}
	.bar {
		display: block;
		height: 100%;
		border-radius: var(--r-sm);
	}
	.deficit .bar {
		background: var(--deficit);
	}
	.surplus .bar {
		background: var(--surplus);
	}
	.v {
		text-align: right;
		font-weight: 700;
	}
	.deficit .v {
		color: var(--deficit-ink);
	}
	.surplus .v {
		color: var(--surplus-ink);
	}
	.empty {
		display: flex;
		gap: 0.6rem;
		align-items: flex-start;
		color: #3d4857;
		margin: 0;
	}
	@media (max-width: 900px) {
		.lists {
			grid-template-columns: 1fr;
		}
	}
</style>
