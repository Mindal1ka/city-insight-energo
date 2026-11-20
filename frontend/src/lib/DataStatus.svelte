<script lang="ts">
	// «Оновити дані»: свіжість кожного джерела + журнал завантажень (справжні й ДЕМО).
	import { api, errMessage, type UploadHistory } from './api.ts';
	import { fresh, loadFreshness, STATUS_SHORT, ago } from './freshness.svelte.ts';
	import { date, dateTime, num } from './format.ts';
	import Icon from './Icon.svelte';
	import DemoPill from './DemoPill.svelte';

	let { version = 0 }: { version?: number } = $props();

	let hist = $state<UploadHistory | null>(null);
	let histErr = $state<string | null>(null);
	let showAll = $state(false);

	$effect(() => {
		void version; // нове завантаження → перечитати обидва блоки
		loadFreshness(version > 0);
		api
			.uploadHistory(60)
			.then((h) => {
				hist = h;
				histErr = null;
			})
			.catch((e) => (histErr = errMessage(e)));
	});

	const items = $derived(hist ? (showAll ? hist.items : hist.items.slice(0, 8)) : []);
	const PERIOD_DAYS: Record<string, number> = { annual: 35, buildings: 100, meters: 100, sem: 190 };
</script>

<section class="card ds" id="freshness" aria-labelledby="fr-h">
	<div class="ds-head">
		<h2 id="fr-h">Свіжість джерел</h2>
		{#if fresh.data}
			<span class="muted small">перевірено {dateTime(fresh.data.checked_at)}</span>
		{/if}
	</div>

	{#if fresh.data}
		<div class="tbl-wrap">
			<table class="tbl">
				<thead>
					<tr>
						<th scope="col">Джерело</th>
						<th scope="col">Дані на</th>
						<th scope="col">Оновлювати</th>
						<th scope="col">Стан</th>
						<th scope="col">Як оновити</th>
					</tr>
				</thead>
				<tbody>
					{#each fresh.data.sources as s (s.key)}
						{@const days = PERIOD_DAYS[s.kind]}
						<tr>
							<th scope="row">
								{s.label}
								{#if s.demo}<span class="demo-tag" title="Дата взята з ДЕМО-журналу завантажень">демо</span>{/if}
							</th>
							<td>
								{#if s.kind === 'openbudget' || s.kind === 'spending'}
									{s.detail}
								{:else}
									{date(s.as_of)} <span class="muted">· {ago(s.age_days)}</span>
								{/if}
							</td>
							<td>{s.period}</td>
							<td>
								<span class="st {s.status}"><span class="dot" aria-hidden="true"></span>{STATUS_SHORT[s.status]}</span>
								{#if days && s.age_days !== null && s.status === 'fresh'}
									<span class="muted small nxt">ще {Math.max(0, days - s.age_days)} дн.</span>
								{/if}
							</td>
							<td class="muted small">{s.how_hint}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else if fresh.error}
		<p class="muted">Не вдалося отримати стан джерел.</p>
	{:else}
		<p class="muted">Завантаження…</p>
	{/if}
</section>

<section class="card ds" aria-labelledby="hist-h">
	<div class="ds-head">
		<h2 id="hist-h">Історія завантажень</h2>
		{#if hist && hist.demo}
			<DemoPill
				text="Частина записів — ДЕМО: правдоподібний щомісячний ритм на основі справжніх дат вивантажень UMUNI. Справжні завантаження з цієї сторінки додаються в журнал автоматично."
			/>
		{/if}
	</div>

	{#if histErr}
		<p class="muted">{histErr}</p>
	{:else if hist}
		<ol class="log">
			{#each items as it, i (i)}
				<li class:bad={!it.ok}>
					<span class="ic {it.ok ? 'ok' : 'no'}" aria-hidden="true"><Icon name={it.ok ? 'check' : 'x'} size={14} stroke={2.6} /></span>
					<span class="l-main">
						<span class="l-t">
							<strong>{it.ok ? it.kind_label : 'Файл не прийнято'}</strong>
							{#if it.channel === 'script'}<span class="chip">скрипт</span>{/if}
							{#if it.demo}<span class="demo-tag">демо</span>{/if}
						</span>
						<span class="l-f">{it.file}{#if it.ok && it.rows} · {num(it.rows)} рядків{/if}</span>
						{#if it.error}<span class="l-e">{it.error}</span>{/if}
					</span>
					<span class="l-meta">
						<span>{dateTime(it.at)}</span>
						<span class="muted">{it.user}</span>
					</span>
				</li>
			{/each}
		</ol>
		{#if hist.items.length > 8}
			<button type="button" class="btn btn-secondary more" onclick={() => (showAll = !showAll)}>
				{showAll ? 'Згорнути' : `Показати всі (${hist.items.length})`}
			</button>
		{/if}
	{:else}
		<p class="muted">Завантаження…</p>
	{/if}
</section>

<style>
	.ds {
		margin: 1.25rem 0 0;
	}
	.ds-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 1rem;
		margin-bottom: 0.75rem;
	}
	.ds-head h2 {
		margin: 0;
		font-size: 1.15rem;
	}
	.tbl-wrap {
		overflow-x: auto;
	}
	.tbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	.tbl th,
	.tbl td {
		padding: 0.55rem 0.6rem;
		text-align: left;
		vertical-align: top;
		border-bottom: 1px solid var(--line-soft);
	}
	.tbl thead th {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--muted);
		white-space: nowrap;
	}
	.tbl tbody th {
		font-weight: 600;
	}
	.st {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
		white-space: nowrap;
	}
	.dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
	}
	.st.fresh {
		color: var(--ok);
	}
	.st.due {
		color: var(--warn);
	}
	.st.stale {
		color: var(--bad);
	}
	.st .dot {
		background: currentColor;
	}
	.nxt {
		display: block;
	}
	.demo-tag {
		display: inline-block;
		margin-left: 0.35rem;
		padding: 0 0.4rem;
		border-radius: var(--r-pill);
		border: 1px dashed #d08a1c;
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		vertical-align: middle;
	}
	.chip {
		display: inline-block;
		margin-left: 0.35rem;
		padding: 0 0.4rem;
		border-radius: var(--r-pill);
		background: var(--neutral-soft);
		color: var(--muted);
		font-size: 0.7rem;
		font-weight: 600;
		vertical-align: middle;
	}
	.log {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.log li {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		gap: 0.75rem;
		align-items: start;
		padding: 0.65rem 0;
		border-bottom: 1px solid var(--line-soft);
	}
	.log li:last-child {
		border-bottom: 0;
	}
	.ic {
		display: grid;
		place-items: center;
		width: 1.6rem;
		height: 1.6rem;
		border-radius: 50%;
		font-size: 0.8rem;
		font-weight: 700;
		color: #fff;
	}
	.ic.ok {
		background: var(--ok);
	}
	.ic.no {
		background: var(--bad);
	}
	.l-main {
		display: flex;
		flex-direction: column;
		min-width: 0;
		gap: 0.1rem;
	}
	.l-f {
		font-size: 0.82rem;
		color: var(--muted);
		overflow-wrap: anywhere;
	}
	.l-e {
		font-size: 0.82rem;
		color: var(--bad);
	}
	.l-meta {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		font-size: 0.8rem;
		white-space: nowrap;
	}
	.more {
		margin-top: 0.75rem;
	}
	@media (max-width: 640px) {
		.log li {
			grid-template-columns: auto minmax(0, 1fr);
		}
		.l-meta {
			grid-column: 2;
			align-items: flex-start;
			flex-direction: row;
			gap: 0.5rem;
		}
		.tbl th:nth-child(5),
		.tbl td:nth-child(5),
		.tbl th:nth-child(3),
		.tbl td:nth-child(3) {
			display: none;
		}
	}
</style>
