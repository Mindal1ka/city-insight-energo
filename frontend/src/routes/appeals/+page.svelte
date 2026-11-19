<script lang="ts">
	// «Звернення»: список, фільтри, зміна статусу, створення. Потрібен вхід.
	import { page } from '$app/state';
	import { ApiError, errMessage } from '#lib/api.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import {
		fetchAppeals,
		createAppeal,
		updateAppeal,
		APPEAL_TYPES,
		APPEAL_STATUSES,
		DEPARTMENTS,
		type Appeal,
		type AppealType,
		type AppealStatus
	} from '#lib/api-v2.ts';
	import { fetchSes, type SesItem } from '#lib/api-ses.ts';
	import { dateTime } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';
	import Skeleton from '#lib/Skeleton.svelte';

	let items = $state<Appeal[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let needLogin = $state(false);

	async function load() {
		loading = true;
		error = null;
		needLogin = false;
		try {
			items = (await fetchAppeals()).items;
		} catch (e) {
			if (e instanceof ApiError && e.status === 401) needLogin = true;
			else error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		void auth.user?.token;
		load();
	});

	const canChange = $derived(['energy_manager', 'department', 'finance'].includes(auth.user?.role ?? ''));
	let fStatus = $state('');
	let fTo = $state('');
	const rows = $derived(items.filter((a) => (!fStatus || a.status === fStatus) && (!fTo || a.to === fTo)));

	const TYPE_ICON: Record<AppealType, 'panel' | 'sun' | 'alert' | 'bolt' | 'info'> = {
		expand: 'panel',
		surplus: 'sun',
		over_limit: 'alert',
		repair: 'bolt',
		other: 'info'
	};
	const TYPE_TONE: Record<AppealType, string> = { expand: 'info', surplus: 'ok', over_limit: 'bad', repair: 'warn', other: 'neu' };
	const ST_TONE: Record<AppealStatus, string> = { нове: 'info', 'в роботі': 'warn', виконано: 'ok', відхилено: 'bad' };

	async function setStatus(a: Appeal, s: AppealStatus) {
		try {
			const u = await updateAppeal(a.id, s);
			items = items.map((x) => (x.id === a.id ? { ...x, ...u } : x));
		} catch (e) {
			error = errMessage(e);
		}
	}

	// ---------- форма ----------
	const sp = page.url.searchParams;
	const qBuilding = Number(sp.get('building')) || null;
	const qType = sp.get('type') as AppealType | null;
	const qKw = sp.get('kw');

	let open = $state(!!qBuilding);
	let buildings = $state<SesItem[]>([]);
	let bId = $state<number | null>(qBuilding);
	let bQuery = $state('');
	let fType = $state<AppealType>(qType && qType in APPEAL_TYPES ? qType : 'expand');
	let to = $state('');
	let toTouched = $state(false);
	let kw = $state(qKw ?? '');
	let text = $state('');
	let sending = $state(false);
	let formErr = $state<string | null>(null);

	$effect(() => {
		if (open && !buildings.length) {
			fetchSes()
				.then((d) => (buildings = d.items))
				.catch((e) => (formErr = errMessage(e)));
		}
	});
	const norm = (s: string) => s.toLocaleLowerCase('uk').replace(/[’ʼ`´']/g, '');
	const picked = $derived(buildings.find((b) => b.id === bId) ?? null);
	const found = $derived.by(() => {
		const nq = norm(bQuery.trim());
		if (!nq) return [];
		return buildings.filter((b) => norm(b.name).includes(nq) || String(b.id) === nq).slice(0, 8);
	});
	$effect(() => {
		if (!toTouched && picked?.department) to = picked.department;
	});

	async function submit(e: Event) {
		e.preventDefault();
		if (!bId) {
			formErr = 'Оберіть будівлю';
			return;
		}
		sending = true;
		formErr = null;
		try {
			const k = kw.trim() === '' ? null : Number(kw.replace(',', '.'));
			await createAppeal({ building_id: bId, type: fType, to: to || undefined, kw: k != null && isFinite(k) ? k : null, text: text.trim() });
			text = '';
			kw = '';
			open = false;
			await load();
		} catch (err) {
			formErr = errMessage(err);
		} finally {
			sending = false;
		}
	}
</script>

<svelte:head><title>Звернення · Енергія</title></svelte:head>

<div class="pg">
	<header class="hd">
		<h1><Icon name="users" size={26} /> Звернення</h1>
		{#if !needLogin}
			<button type="button" class="prim" onclick={() => (open = !open)}>{open ? '×' : '+ Нове'}</button>
		{/if}
	</header>

	{#if needLogin}
		<div class="state login">
			<Icon name="lock" size={22} />
			<a href="/login?next=/appeals">Увійти</a>
		</div>
	{:else}
		{#if open}
			<form class="form" onsubmit={submit}>
				<div class="f">
					<label for="bq">Будівля</label>
					{#if picked}
						<div class="picked">
							<span>{picked.name}</span>
							<button type="button" onclick={() => (bId = null)} aria-label="Змінити">×</button>
						</div>
					{:else}
						<input id="bq" type="search" placeholder="Назва або №" bind:value={bQuery} autocomplete="off" />
						{#if found.length}
							<ul class="pick">
								{#each found as b (b.id)}
									<li><button type="button" onclick={() => { bId = b.id; bQuery = ''; toTouched = false; }}>{b.name}</button></li>
								{/each}
							</ul>
						{/if}
					{/if}
				</div>
				<div class="f">
					<label for="ft">Тип</label>
					<select id="ft" bind:value={fType}>
						{#each Object.entries(APPEAL_TYPES) as [k, l] (k)}<option value={k}>{l}</option>{/each}
					</select>
				</div>
				<div class="f">
					<label for="fto">Кому</label>
					<select id="fto" bind:value={to} onchange={() => (toTouched = true)}>
						<option value="">—</option>
						{#each DEPARTMENTS as d (d)}<option value={d}>{d}</option>{/each}
					</select>
				</div>
				<div class="f sm">
					<label for="fkw">кВт</label>
					<input id="fkw" type="text" inputmode="decimal" bind:value={kw} />
				</div>
				<div class="f wide">
					<label for="ftx">Текст</label>
					<textarea id="ftx" rows="3" bind:value={text}></textarea>
				</div>
				{#if formErr}<div class="err" role="alert">{formErr}</div>{/if}
				<div class="f"><button type="submit" class="prim" disabled={sending}>Надіслати</button></div>
			</form>
		{/if}

		<div class="filters">
			<select bind:value={fStatus} aria-label="Статус">
				<option value="">Усі статуси</option>
				{#each APPEAL_STATUSES as s (s)}<option value={s}>{s}</option>{/each}
			</select>
			<select bind:value={fTo} aria-label="Кому">
				<option value="">Усі департаменти</option>
				{#each DEPARTMENTS as d (d)}<option value={d}>{d}</option>{/each}
			</select>
			<span class="cnt">{rows.length}</span>
		</div>

		{#if error}<div class="state err" role="alert">{error} <button type="button" onclick={load}>Повторити</button></div>{/if}

		{#if loading && !items.length}
			<Skeleton variant="table" rows={5} />
		{:else}
			<ul class="list">
				{#each rows as a (a.id)}
					<li class="ap">
						<div class="l1">
							<span class="badge {TYPE_TONE[a.type]}" title={a.type_name}><Icon name={TYPE_ICON[a.type]} size={14} /> {a.type_name}</span>
							<a href="/object/{a.building_id}">{a.building_name}</a>
							<span class="to">→ {a.to}</span>
							{#if a.kw != null}<b class="kw">{a.kw} кВт</b>{/if}
						</div>
						{#if a.text}<p>{a.text}</p>{/if}
						{#if a.answer}<p class="ans">{a.answer}</p>{/if}
						<div class="l3">
							{#if canChange}
								<select value={a.status} onchange={(e) => setStatus(a, e.currentTarget.value as AppealStatus)} aria-label="Статус" class="st {ST_TONE[a.status]}">
									{#each APPEAL_STATUSES as s (s)}<option value={s}>{s}</option>{/each}
								</select>
							{:else}
								<span class="badge {ST_TONE[a.status]}">{a.status}</span>
							{/if}
							<span class="meta">{a.author} · {dateTime(a.created_at)}</span>
						</div>
					</li>
				{:else}
					<li class="empty">—</li>
				{/each}
			</ul>
		{/if}
	{/if}
</div>

<style>
	.pg { max-width: 1000px; margin: 0 auto; padding: 1rem; }
	.hd { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 1rem; }
	h1 { margin: 0; font-size: var(--fs-xl); display: flex; align-items: center; gap: 0.5rem; }
	input, select, textarea, button { font: inherit; padding: 0.4rem 0.6rem; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); color: var(--text); max-width: 100%; }
	button { cursor: pointer; }
	.prim { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; }
	.prim:disabled { opacity: 0.6; }
	.state.login { display: flex; gap: 0.75rem; align-items: center; padding: 1.25rem; background: var(--accent-soft); border-radius: var(--radius); }
	.state.login a { font-weight: 700; color: var(--accent); }
	.state.err, .err { padding: 0.75rem 1rem; background: var(--bad-soft); color: var(--bad); border-radius: var(--radius); margin: 0.5rem 0; }
	.form { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; padding: 1rem; background: var(--surface); border: 1px solid var(--card-line); border-radius: var(--radius); margin-bottom: 1rem; position: relative; }
	.f { display: flex; flex-direction: column; gap: 0.25rem; position: relative; }
	.f label { font-size: var(--fs-xs); color: var(--muted); }
	.f.wide, .form .err { grid-column: 1 / -1; }
	.picked { display: flex; justify-content: space-between; gap: 0.5rem; align-items: center; padding: 0.4rem 0.6rem; background: var(--accent-soft); border-radius: var(--radius-sm); }
	.picked button { border: 0; background: none; padding: 0 0.3rem; }
	.pick { list-style: none; margin: 0; padding: 0; position: absolute; top: 100%; left: 0; right: 0; z-index: 5; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-sm); box-shadow: var(--shadow-md); }
	.pick button { width: 100%; text-align: left; border: 0; border-radius: 0; }
	.pick button:hover { background: var(--accent-soft); }
	.filters { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-bottom: 0.75rem; }
	.cnt { color: var(--muted); font-size: var(--fs-sm); }
	.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.6rem; }
	.ap { padding: 0.8rem; background: var(--surface); border: 1px solid var(--card-line); border-radius: var(--radius); display: flex; flex-direction: column; gap: 0.4rem; }
	.ap p { margin: 0; font-size: var(--fs-sm); }
	.ans { color: var(--ok); }
	.l1, .l3 { display: flex; flex-wrap: wrap; gap: 0.5rem 0.75rem; align-items: center; }
	.l1 a { font-weight: 600; color: var(--accent); text-decoration: none; }
	.to, .meta { color: var(--muted); font-size: var(--fs-sm); }
	.kw { font-variant-numeric: tabular-nums; }
	.badge, .st { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: var(--fs-xs); font-weight: 600; }
	.info { background: var(--accent-soft); color: var(--accent-dark); }
	.ok { background: var(--ok-soft); color: var(--ok); }
	.warn { background: var(--warn-soft); color: var(--warn); }
	.bad { background: var(--bad-soft); color: var(--bad); }
	.neu { background: var(--line-soft); color: var(--muted); }
	.empty { text-align: center; color: var(--muted); padding: 1rem; }
</style>
