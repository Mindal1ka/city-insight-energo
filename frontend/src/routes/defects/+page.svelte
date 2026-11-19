<script lang="ts">
	// Сторінка «Якість даних»: перелік дефектів і аномалій з фільтрами та вивантаженням у CSV
	import { api, errMessage, type Defect } from '#lib/api.ts';
	import { num } from '#lib/format.ts';
	import Status from '#lib/Status.svelte';

	let defects = $state<Defect[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);

	let fType = $state('');
	let fRule = $state('');
	let fSet = $state('');
	let query = $state('');
	const LIMIT = 300; // скільки рядків показувати одразу, щоб сторінка не гальмувала
	let showAll = $state(false);

	async function load() {
		loading = true;
		error = null;
		try {
			defects = await api.defects();
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	load();

	/** Групуємо схожі правила: числа в тексті правила різні для кожної будівлі */
	function ruleGroup(rule: string): string {
		return rule
			.replace(/\s*\(\+?\d+%\)/g, '')
			.replace(/в \d+ разів/g, 'в 10 і більше разів')
			.trim();
	}

	function kindOf(d: Defect): string {
		return d.тип ?? 'дефект даних';
	}

	function countBy(list: Defect[], f: (d: Defect) => string): [string, number][] {
		const m = new Map<string, number>();
		for (const d of list) m.set(f(d), (m.get(f(d)) ?? 0) + 1);
		return [...m.entries()].sort((a, b) => b[1] - a[1]);
	}

	const hasTypes = $derived(defects.some((d) => d.тип));
	const types = $derived(countBy(defects, kindOf));
	const rules = $derived(countBy(defects, (d) => ruleGroup(d.правило)));
	const sets = $derived(countBy(defects, (d) => d.набір));

	const filtered = $derived.by(() => {
		const q = query.trim().toLocaleLowerCase('uk');
		return defects.filter(
			(d) =>
				(!fType || kindOf(d) === fType) &&
				(!fRule || ruleGroup(d.правило) === fRule) &&
				(!fSet || d.набір === fSet) &&
				(!q || String(d.будівля).toLocaleLowerCase('uk').includes(q))
		);
	});
	const shown = $derived(showAll ? filtered : filtered.slice(0, LIMIT));
	const buildingsAffected = $derived(new Set(filtered.map((d) => d.будівля_id)).size);

	function reset() {
		fType = fRule = fSet = query = '';
	}

	function isId(v: number | string): boolean {
		return v !== '' && v !== null && !Number.isNaN(Number(v));
	}
</script>

<svelte:head><title>Якість даних · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Якість даних</h1>
		<p class="lead">
			Помилки й пропуски у вивантаженнях UMUNI, які ми знайшли автоматично: немає площі, немає
			координат, підозрілі стрибки споживання тощо. Для кожного запису є порада, що виправити.
		</p>
	</div>
	<a class="btn" href="/api/defects.csv" download="data-defects.csv">Завантажити data-defects.csv</a>
</div>

<Status {loading} {error} retry={load} />

{#if !loading && !error}
	<div class="toolbar card filters">
		{#if hasTypes}
			<div class="field">
				<label for="f-type">Тип</label>
				<select id="f-type" bind:value={fType}>
					<option value="">Усі типи ({defects.length})</option>
					{#each types as [t, n] (t)}<option value={t}>{t} ({n})</option>{/each}
				</select>
			</div>
		{/if}
		<div class="field">
			<label for="f-rule">Правило</label>
			<select id="f-rule" bind:value={fRule}>
				<option value="">Усі правила ({defects.length})</option>
				{#each rules as [r, n] (r)}<option value={r}>{r} ({n})</option>{/each}
			</select>
		</div>
		<div class="field">
			<label for="f-set">Набір даних</label>
			<select id="f-set" bind:value={fSet}>
				<option value="">Усі набори</option>
				{#each sets as [s, n] (s)}<option value={s}>{s} ({n})</option>{/each}
			</select>
		</div>
		<div class="field">
			<label for="f-q">Будівля</label>
			<input id="f-q" type="search" bind:value={query} placeholder="Частина назви" />
		</div>
		<button type="button" class="btn btn-secondary" onclick={reset}>Скинути фільтри</button>
	</div>

	<p aria-live="polite">
		Знайдено <strong>{num(filtered.length)}</strong> записів на <strong>{num(buildingsAffected)}</strong> будівлях.
	</p>

	<div class="table-wrap">
		<table>
			<caption class="visually-hidden">Дефекти даних і аномалії споживання</caption>
			<thead>
				<tr>
					{#if hasTypes}<th scope="col">Тип</th>{/if}
					<th scope="col">Будівля</th>
					<th scope="col">Правило</th>
					<th scope="col">Поле</th>
					<th scope="col">Значення</th>
					<th scope="col">Що робити</th>
					<th scope="col">Набір даних</th>
				</tr>
			</thead>
			<tbody>
				{#each shown as d, i (i)}
					<tr>
						{#if hasTypes}
							<td><span class="pill {kindOf(d) === 'аномалія споживання' ? 'pill-bad' : 'pill-warn'}">{kindOf(d)}</span></td>
						{/if}
						<td>
							{#if isId(d.будівля_id)}<a href="/building/{d.будівля_id}">{d.будівля}</a>{:else}{d.будівля || '—'}{/if}
						</td>
						<td>{d.правило}</td>
						<td>{d.поле}</td>
						<td class="val">{d.значення === '' || d.значення === null ? '—' : d.значення}</td>
						<td>{d.що_робити}</td>
						<td class="small muted">{d.набір}</td>
					</tr>
				{:else}
					<tr><td colspan="7" class="muted">Записів за цими фільтрами немає.</td></tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if filtered.length > LIMIT && !showAll}
		<p class="more">
			Показано перші {LIMIT} з {num(filtered.length)}.
			<button type="button" class="btn btn-secondary" onclick={() => (showAll = true)}>Показати всі</button>
			або завантажте повний перелік у CSV.
		</p>
	{/if}
{/if}

<style>
	.filters {
		padding: 1rem;
	}
	.filters select {
		max-width: 26rem;
	}
	.val {
		word-break: break-word;
		max-width: 16rem;
	}
	.more {
		margin-top: 1rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}
</style>
