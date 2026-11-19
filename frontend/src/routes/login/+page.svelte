<script lang="ts">
	// Вхід: ПІБ, посада, роль (+ заклад / управління), пароль → POST /api/auth/login.
	// «Переглянути як мешканець» — публічний режим без входу.
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { login, logout, fetchRoles, safeNext, LoginError, DEFAULT_POSITION } from '#lib/auth.svelte.ts';
	import { ROLES, DEPARTMENTS, type RoleInfo, type RoleId, type Department } from '#lib/roles.ts';
	import { api, type Building } from '#lib/api.ts';
	import Icon from '#lib/Icon.svelte';

	let fullName = $state('');
	let position = $state(DEFAULT_POSITION);
	let password = $state('');
	let roles = $state<RoleInfo[]>(ROLES);
	let roleId = $state<RoleId>('energy_manager');
	let department = $state<Department | ''>('');
	let tried = $state(false);
	let busy = $state(false);
	let serverErr = $state('');

	const role = $derived(roles.find((r) => r.id === roleId) ?? roles[0]);
	// Короткий підпис ролі (локальний), довгий опис бекенду — запасний
	const roleDesc = $derived(ROLES.find((r) => r.id === roleId)?.description ?? role?.description ?? '');

	fetchRoles().then((list) => {
		roles = list;
		if (!list.some((r) => r.id === roleId)) roleId = list[0]?.id ?? 'energy_manager';
	});

	// --- Пошук закладу (для керівника закладу) ---
	let buildings = $state<Building[]>([]);
	let bLoading = $state(false);
	let bQuery = $state('');
	let buildingId = $state<number | null>(null);
	let bOpen = $state(false);
	let bActive = $state(0);
	const chosen = $derived(buildings.find((b) => b.id === buildingId) ?? null);

	$effect(() => {
		if (!role?.needs_building || buildings.length || bLoading) return;
		bLoading = true;
		api
			.buildings()
			.then((list) => (buildings = list))
			.catch(() => (buildings = []))
			.finally(() => (bLoading = false));
	});

	function norm(s: string) {
		return s.toLocaleLowerCase('uk').replace(/[’'ʼ`]/g, '').replace(/\s+/g, ' ').trim();
	}
	const matches = $derived.by(() => {
		const q = norm(bQuery);
		if (!q || (chosen && bQuery === chosen.name)) return buildings.slice(0, 0);
		const words = q.split(' ');
		return buildings
			.filter((b) => {
				const hay = norm(`${b.name} ${b.address} ${b.id}`);
				return words.every((w) => hay.includes(w));
			})
			.slice(0, 8);
	});
	function pick(b: Building) {
		buildingId = b.id;
		bQuery = b.name;
		bOpen = false;
	}
	function bKey(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			bOpen = true;
			bActive = Math.min(bActive + 1, matches.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			bActive = Math.max(bActive - 1, 0);
		} else if (e.key === 'Enter' && bOpen && matches[bActive]) {
			e.preventDefault();
			pick(matches[bActive]);
		} else if (e.key === 'Escape') {
			bOpen = false;
		}
	}
	function bInput() {
		buildingId = null;
		bOpen = true;
		bActive = 0;
	}

	const nameErr = $derived(fullName.trim() ? '' : 'Вкажіть ПІБ');
	const passErr = $derived(password ? '' : 'Введіть пароль');
	const bErr = $derived(role?.needs_building && !buildingId ? 'Оберіть заклад зі списку' : '');
	const dErr = $derived(role?.needs_department && !department ? 'Оберіть управління' : '');

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		tried = true;
		serverErr = '';
		const first = nameErr ? 'fio' : bErr ? 'bld' : dErr ? 'dep-0' : passErr ? 'pass' : null;
		if (first) {
			document.getElementById(first)?.focus();
			return;
		}
		busy = true;
		try {
			await login({
				full_name: fullName.trim().replace(/\s+/g, ' '),
				position: position.trim().replace(/\s+/g, ' ') || DEFAULT_POSITION,
				role: roleId,
				building_id: role?.needs_building ? buildingId : null,
				department: role?.needs_department ? (department as Department) : null,
				password
			});
			goto(safeNext(page.url), { replace: true, reset: false });
		} catch (err) {
			serverErr = err instanceof LoginError ? err.message : 'Не вдалося увійти';
			busy = false;
			if (err instanceof LoginError && (err.status === 401 || err.status === 403)) {
				password = '';
				document.getElementById('pass')?.focus();
			}
		}
	}

	function asResident() {
		logout();
		goto(safeNext(page.url), { replace: true, reset: false });
	}

	// Вогники міста на схемі: [x, y, затримка]
	const lights: [number, number, number][] = [
		[118, 182, 0], [162, 150, 0.6], [214, 196, 1.2], [262, 140, 0.3], [300, 214, 1.8],
		[338, 166, 0.9], [382, 204, 2.4], [420, 150, 1.5], [196, 236, 2.1], [352, 246, 0.4]
	];
</script>

<svelte:head><title>Вхід · City Insight Map · Енергія</title></svelte:head>

<div class="login">
	<div class="bg" aria-hidden="true">
		<span class="orb o1"></span>
		<span class="orb o2"></span>
		<span class="grid"></span>
	</div>

	<section class="hero" aria-labelledby="hero-h">
		<p class="brand rise" style="--d: 0ms">
			<span class="logo" aria-hidden="true"><Icon name="bolt" size={22} stroke={2.2} /></span>
			<span>
				<span class="brand-name">City Insight Map <span class="dot">·</span> Енергія</span>
				<span class="brand-sub">Полтавська громада</span>
			</span>
		</p>

		<h1 id="hero-h" class="rise" style="--d: 80ms">Енергія громади —<br /><span class="hl">видно з першого погляду</span></h1>
		<p class="one rise" style="--d: 160ms">Ефективність сонячних станцій комунальних об’єктів.</p>
		<svg class="art rise" style="--d: 240ms" viewBox="0 0 520 300" aria-hidden="true" focusable="false">
			<defs>
				<radialGradient id="lg-sun" cx="0.5" cy="0.5" r="0.5">
					<stop offset="0" stop-color="#ffd56b" stop-opacity="0.55" />
					<stop offset="1" stop-color="#ffd56b" stop-opacity="0" />
				</radialGradient>
				<linearGradient id="lg-pv" x1="0" x2="1" y1="0" y2="1">
					<stop offset="0" stop-color="#3a7bc2" />
					<stop offset="1" stop-color="#173f6b" />
				</linearGradient>
				<linearGradient id="lg-flow" x1="0" x2="1">
					<stop offset="0" stop-color="#ffd56b" />
					<stop offset="1" stop-color="#f5a524" />
				</linearGradient>
			</defs>

			<!-- Сонце -->
			<g class="sun">
				<circle cx="430" cy="72" r="96" fill="url(#lg-sun)" class="glow" />
				<circle cx="430" cy="72" r="32" fill="#f5a524" />
				<g class="rays" stroke="#ffd56b" stroke-width="3" stroke-linecap="round" opacity="0.8">
					{#each { length: 8 } as _, i (i)}
						<line x1="430" y1="22" x2="430" y2="10" transform="rotate({i * 45} 430 72)" />
					{/each}
				</g>
			</g>

			<!-- Мережа міста -->
			<g stroke="#5f8fc4" stroke-opacity="0.35" stroke-width="1.2" fill="none">
				<path d="M118 182 L162 150 L262 140 L338 166 L420 150 M162 150 L214 196 L300 214 L382 204 L420 150 M214 196 L196 236 L352 246 L382 204 M262 140 L300 214 M338 166 L382 204" />
			</g>
			<!-- Потік енергії від сонця до будівель -->
			<path class="flow" d="M408 96 C 360 130, 330 150, 262 140" stroke="url(#lg-flow)" />
			<path class="flow f2" d="M416 104 C 400 150, 330 190, 300 214" stroke="url(#lg-flow)" />

			{#each lights as [x, y, d] (x + '-' + y)}
				<circle cx={x} cy={y} r="9" fill="#f5a524" opacity="0.18" class="pulse" style="animation-delay:{d}s" />
				<circle cx={x} cy={y} r="4" fill="#ffd56b" class="light" style="animation-delay:{d}s" />
			{/each}

			<!-- Будівля зі станцією -->
			<g transform="translate(20 168)">
				<path d="M0 44 L54 16 L108 44 Z" fill="#1c4675" />
				<g transform="translate(16 20) skewX(-28)">
					{#each [0, 1, 2] as i (i)}
						{#each [0, 1] as j (j)}
							<rect x={i * 20} y={j * 11} width="18" height="9" rx="1.5" fill="url(#lg-pv)" stroke="#9ccaf5" stroke-width="0.7" class="cell" style="animation-delay:{(i + j * 3) * 0.18}s" />
						{/each}
					{/each}
				</g>
				<rect x="8" y="44" width="92" height="80" fill="#163a60" />
				{#each [0, 1, 2] as i (i)}
					<rect x={20 + i * 26} y="58" width="14" height="14" rx="2" fill="#ffd56b" class="win" style="animation-delay:{i * 0.7}s" />
					<rect x={20 + i * 26} y="86" width="14" height="14" rx="2" fill="#ffd56b" class="win" style="animation-delay:{1.2 + i * 0.5}s" />
				{/each}
			</g>
		</svg>
	</section>

	<section class="side" aria-labelledby="form-h">
		<form class="card-form" onsubmit={submit} novalidate>
			<h2 id="form-h">Вхід</h2>

			<div class="f">
				<label for="fio">ПІБ</label>
				<div class="inp">
					<Icon name="users" size={18} />
					<input
						id="fio"
						type="text"
						autocomplete="name"
						placeholder="Коваленко Олена Петрівна"
						bind:value={fullName}
						aria-invalid={tried && !!nameErr}
						aria-describedby={tried && nameErr ? 'fio-err' : undefined}
					/>
				</div>
				{#if tried && nameErr}<p id="fio-err" class="err"><Icon name="alert" size={15} /> {nameErr}</p>{/if}
			</div>

			<div class="f">
				<label for="pos">Посада</label>
				<div class="inp">
					<Icon name="building" size={18} />
					<input id="pos" type="text" autocomplete="organization-title" bind:value={position} />
				</div>
			</div>

			<div class="f">
				<label for="role">Роль</label>
				<div class="inp sel">
					<Icon name="lock" size={18} />
					<select id="role" bind:value={roleId}>
						{#each roles as r (r.id)}<option value={r.id}>{r.name}</option>{/each}
					</select>
				</div>
				{#if roleDesc}<p class="hint">{roleDesc}</p>{/if}
			</div>

			{#if role?.needs_building}
				<div class="f">
					<label for="bld">Ваш заклад</label>
					<div class="inp combo">
						<Icon name="search" size={18} />
						<input
							id="bld"
							type="text"
							role="combobox"
							autocomplete="off"
							placeholder={bLoading ? 'Завантаження…' : 'Назва, адреса або id'}
							bind:value={bQuery}
							oninput={bInput}
							onkeydown={bKey}
							onfocus={() => (bOpen = true)}
							onblur={() => setTimeout(() => (bOpen = false), 150)}
							aria-expanded={bOpen && matches.length > 0}
							aria-controls="bld-list"
							aria-autocomplete="list"
							aria-activedescendant={bOpen && matches[bActive] ? `bld-${matches[bActive].id}` : undefined}
							aria-invalid={tried && !!bErr}
						/>
						{#if chosen}<span class="ok-mark" aria-label="Обрано"><Icon name="check" size={16} /></span>{/if}
						{#if bOpen && matches.length}
							<ul id="bld-list" class="combo-list" role="listbox">
								{#each matches as b, i (b.id)}
									<li
										id="bld-{b.id}"
										role="option"
										aria-selected={i === bActive}
										class:act={i === bActive}
										onmousedown={(e) => {
											e.preventDefault();
											pick(b);
										}}
									>
										<span class="cl-name">{b.name}</span>
										<span class="cl-addr">{b.address}</span>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
					{#if tried && bErr}<p class="err"><Icon name="alert" size={15} /> {bErr}</p>{:else if chosen}<p class="hint">{chosen.address}</p>{/if}
				</div>
			{/if}

			{#if role?.needs_department}
				<fieldset class="f dep">
					<legend>Управління</legend>
					<div class="seg">
						{#each DEPARTMENTS as d, i (d.id)}
							<label class="seg-opt" class:on={department === d.id}>
								<input id="dep-{i}" type="radio" name="dep" value={d.id} bind:group={department} />
								{d.id === 'освіта' ? 'Освіта' : 'Охорона здоров’я'}
							</label>
						{/each}
					</div>
					{#if tried && dErr}<p class="err"><Icon name="alert" size={15} /> {dErr}</p>{/if}
				</fieldset>
			{/if}

			<div class="f">
				<label for="pass">Пароль</label>
				<div class="inp">
					<Icon name="lock" size={18} />
					<input
						id="pass"
						type="password"
						autocomplete="current-password"
						bind:value={password}
						aria-invalid={tried && !!passErr}
						aria-describedby={tried && passErr ? 'pass-err' : undefined}
					/>
				</div>
				{#if tried && passErr}<p id="pass-err" class="err"><Icon name="alert" size={15} /> {passErr}</p>{/if}
			</div>

			{#if serverErr}<p class="err srv" role="alert"><Icon name="alert" size={15} /> {serverErr}</p>{/if}

			<button class="go" type="submit" disabled={busy} aria-busy={busy}>
				<span>{busy ? 'Входимо…' : 'Увійти'}</span>
				<span class="go-ico"><Icon name="arrow-right" size={18} /></span>
			</button>

			<div class="or" aria-hidden="true"><span>або</span></div>

			<button class="pub" type="button" onclick={asResident}>
				<Icon name="users" size={20} />
				<span>Переглянути як мешканець</span>
			</button>
		</form>
		<p class="foot">Poltava Open Data Hackathon · трек 2</p>
	</section>
</div>

<style>
	.login {
		position: relative;
		min-height: 100vh;
		display: grid;
		grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
		align-items: center;
		gap: 2rem 4rem;
		padding: 3rem clamp(1.25rem, 5vw, 5.5rem);
		color: #fff;
		background: linear-gradient(160deg, #0d2b4d 0%, #0a1f38 55%, #08182c 100%);
		isolation: isolate;
	}
	.bg {
		position: absolute;
		inset: 0;
		z-index: -1;
		overflow: hidden;
		pointer-events: none;
	}
	.orb {
		position: absolute;
		border-radius: 50%;
		filter: blur(60px);
	}
	.o1 {
		width: 520px;
		height: 520px;
		right: -180px;
		top: -300px;
		background: rgba(70, 140, 230, 0.16);
		mix-blend-mode: screen;
	}
	.o2 {
		width: 640px;
		height: 640px;
		left: -260px;
		bottom: -300px;
		background: rgba(60, 130, 220, 0.22);
		mix-blend-mode: screen;
	}
	.grid {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
			linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
		background-size: 44px 44px;
		mask-image: radial-gradient(ellipse at 35% 45%, #000 20%, transparent 75%);
	}

	/* --- Ліва частина --- */
	.hero {
		max-width: 40rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		margin: 0 0 2.5rem;
	}
	.logo {
		display: grid;
		place-items: center;
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 13px;
		background: linear-gradient(145deg, #ffd978, #f5a524 60%, #e88f05);
		color: #0f2f52;
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.5),
			0 8px 24px -6px rgba(245, 165, 36, 0.7);
	}
	.brand-name {
		display: block;
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 1.2rem;
	}
	.dot {
		color: var(--sun);
	}
	.brand-sub {
		display: block;
		font-size: 0.875rem;
		color: #a9bdd6;
	}
	h1 {
		color: #fff;
		font-size: clamp(2rem, 3.4vw, 3.25rem);
		line-height: 1.08;
		letter-spacing: -0.03em;
		margin: 0 0 1.1rem;
	}
	.hl {
		background: linear-gradient(90deg, #ffd56b, #f5a524 60%, #ffb648);
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
	}
	.one {
		font-size: 1.125rem;
		line-height: 1.6;
		color: #c9d6e6;
		max-width: 36rem;
		margin: 0;
	}
	.art {
		display: block;
		width: 100%;
		max-width: 34rem;
		height: auto;
		margin-top: 2rem;
		overflow: visible;
	}
	.flow {
		fill: none;
		stroke-width: 2.5;
		stroke-linecap: round;
		stroke-dasharray: 4 10;
		opacity: 0.9;
	}

	/* --- Форма --- */
	.side {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
	}
	.card-form {
		position: relative;
		width: 100%;
		max-width: 27rem;
		padding: 2.1rem 2rem 1.6rem;
		border-radius: 24px;
		background: rgba(255, 255, 255, 0.98);
		color: var(--text);
		box-shadow:
			0 40px 80px -30px rgba(0, 0, 0, 0.65),
			0 0 0 1px rgba(255, 255, 255, 0.4);
	}
	h2 {
		font-size: 1.75rem;
		margin: 0 0 1.1rem;
	}
	.f {
		margin-bottom: 1rem;
	}
	.f label {
		display: block;
		margin-bottom: 0.35rem;
	}
	.inp {
		position: relative;
		display: flex;
		align-items: center;
		color: var(--muted);
	}
	.inp :global(.icon) {
		position: absolute;
		left: 0.85rem;
		pointer-events: none;
		transition: color var(--dur-fast);
	}
	.inp:focus-within :global(.icon) {
		color: var(--accent);
	}
	.inp input {
		width: 100%;
		min-height: 50px;
		padding-left: 2.6rem;
		border-radius: 13px;
		font-size: 1rem;
		background: var(--surface-2);
		border-color: var(--line);
	}
	.inp input:focus {
		background: #fff;
		box-shadow: 0 0 0 4px rgba(11, 92, 173, 0.12);
	}
	.inp input[aria-invalid='true'] {
		border-color: var(--bad);
	}
	.err {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0.35rem 0 0;
		color: var(--bad);
		font-size: 0.875rem;
		font-weight: 600;
	}
	.go {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		width: 100%;
		min-height: 52px;
		margin-top: 0.6rem;
		border-radius: 14px;
		border: 1px solid #d98c0b;
		background: linear-gradient(180deg, #ffc54d, var(--sun));
		color: #2a1900;
		font: inherit;
		font-weight: 700;
		font-size: 1.0625rem;
		cursor: pointer;
		overflow: hidden;
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.5),
			0 14px 30px -14px rgba(245, 165, 36, 0.9);
		transition:
			transform var(--dur-base) var(--ease-out),
			box-shadow var(--dur-base) var(--ease-out),
			filter var(--dur-fast);
	}
	.go:hover {
		transform: translateY(-1px);
		filter: saturate(1.1) brightness(1.03);
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.5),
			0 18px 36px -14px rgba(245, 165, 36, 1);
	}
	.go:active {
		transform: scale(0.985);
	}
	.go:disabled {
		cursor: progress;
	}
	.go-ico {
		display: grid;
		place-items: center;
		transition: transform var(--dur-base) var(--ease-spring);
	}
	.go:hover .go-ico {
		transform: translateX(4px);
	}
	/* Відблиск, що пробігає кнопкою */
	.go::after {
		content: '';
		position: absolute;
		top: 0;
		bottom: 0;
		width: 40%;
		left: -60%;
		background: linear-gradient(100deg, transparent, rgba(255, 255, 255, 0.55), transparent);
		transform: skewX(-20deg);
	}
	.foot {
		margin: 0;
		font-size: 0.8125rem;
		color: #8ea5c2;
	}

	.hint {
		margin: 0.3rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
		line-height: 1.35;
	}
	.sel select {
		width: 100%;
		min-height: 50px;
		padding-left: 2.6rem;
		border-radius: 13px;
		font-size: 1rem;
		background-color: var(--surface-2);
		border-color: var(--line);
	}
	.sel select:focus {
		background-color: #fff;
		box-shadow: 0 0 0 4px rgba(11, 92, 173, 0.12);
	}
	.combo input {
		padding-right: 2.4rem;
	}
	.ok-mark {
		position: absolute;
		right: 0.8rem;
		display: grid;
		place-items: center;
		color: var(--good, #1a7f4b);
	}
	.ok-mark :global(.icon) {
		position: static;
	}
	.combo-list {
		position: absolute;
		z-index: 5;
		top: calc(100% + 6px);
		left: 0;
		right: 0;
		margin: 0;
		padding: 0.3rem;
		list-style: none;
		max-height: 16rem;
		overflow-y: auto;
		border-radius: 14px;
		background: #fff;
		border: 1px solid var(--line);
		box-shadow: 0 20px 40px -18px rgba(8, 20, 38, 0.45);
	}
	.combo-list li {
		display: flex;
		flex-direction: column;
		padding: 0.45rem 0.65rem;
		border-radius: 10px;
		cursor: pointer;
		line-height: 1.3;
	}
	.combo-list li.act,
	.combo-list li:hover {
		background: var(--sun-soft);
	}
	.cl-name {
		font-weight: 600;
		font-size: 0.9rem;
		color: var(--text);
	}
	.cl-addr {
		font-size: 0.78rem;
		color: var(--muted);
	}
	fieldset.dep {
		border: 0;
		padding: 0;
		min-width: 0;
	}
	.dep legend {
		padding: 0;
		margin-bottom: 0.35rem;
		font-weight: 600;
	}
	.seg {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.4rem;
	}
	.seg-opt {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 46px;
		padding: 0.3rem 0.6rem;
		border-radius: 12px;
		border: 1px solid var(--line);
		background: var(--surface-2);
		font-weight: 600;
		font-size: 0.9rem;
		text-align: center;
		cursor: pointer;
		transition:
			background var(--dur-fast),
			border-color var(--dur-fast),
			color var(--dur-fast);
	}
	.seg-opt input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}
	.seg-opt:has(input:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: 2px;
	}
	.seg-opt.on {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.srv {
		padding: 0.55rem 0.75rem;
		border-radius: 12px;
		background: color-mix(in srgb, var(--bad) 8%, #fff);
	}
	.or {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin: 1rem 0 0.8rem;
		color: var(--muted);
		font-size: 0.8125rem;
	}
	.or::before,
	.or::after {
		content: '';
		flex: 1;
		height: 1px;
		background: var(--line);
	}
	.pub {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		width: 100%;
		min-height: 52px;
		border-radius: 14px;
		border: 1.5px solid var(--navy);
		background: #fff;
		color: var(--navy);
		font: inherit;
		font-weight: 700;
		font-size: 1.0625rem;
		cursor: pointer;
		transition:
			background var(--dur-fast),
			transform var(--dur-base) var(--ease-out);
	}
	.pub:hover {
		background: var(--accent-soft, #eaf2fb);
		transform: translateY(-1px);
	}
	.pub:active {
		transform: scale(0.985);
	}

	/* --- Анімації --- */
	@media (prefers-reduced-motion: no-preference) {
		.rise {
			animation: rise 0.8s var(--ease-out) var(--d, 0ms) backwards;
		}
		.card-form {
			animation: card-in 0.9s var(--ease-out) 0.18s backwards;
		}
		@keyframes rise {
			from {
				opacity: 0;
				transform: translateY(18px);
			}
		}
		@keyframes card-in {
			from {
				opacity: 0;
				transform: translateY(26px) scale(0.97);
			}
		}
		.o1 {
			animation: drift 14s ease-in-out infinite alternate;
		}
		.o2 {
			animation: drift 18s ease-in-out infinite alternate-reverse;
		}
		@keyframes drift {
			to {
				transform: translate(60px, 40px) scale(1.1);
			}
		}
		.glow {
			transform-origin: 430px 72px;
			animation: glow 4s ease-in-out infinite;
		}
		@keyframes glow {
			50% {
				transform: scale(1.12);
				opacity: 0.75;
			}
		}
		.rays {
			transform-origin: 430px 72px;
			animation: spin 40s linear infinite;
		}
		@keyframes spin {
			to {
				transform: rotate(360deg);
			}
		}
		.flow {
			animation: flow 1.6s linear infinite;
		}
		.f2 {
			animation-duration: 2.1s;
		}
		@keyframes flow {
			to {
				stroke-dashoffset: -28;
			}
		}
		.pulse {
			transform-box: fill-box;
			transform-origin: center;
			animation: pulse 3s ease-out infinite;
		}
		@keyframes pulse {
			0% {
				transform: scale(0.6);
				opacity: 0.5;
			}
			80%,
			100% {
				transform: scale(2.2);
				opacity: 0;
			}
		}
		.light {
			animation: twinkle 3s ease-in-out infinite;
		}
		@keyframes twinkle {
			50% {
				opacity: 0.55;
			}
		}
		.win {
			animation: win 5s ease-in-out infinite;
		}
		@keyframes win {
			0%,
			100% {
				opacity: 0.85;
			}
			50% {
				opacity: 0.35;
			}
		}
		.cell {
			animation: cell 3.2s ease-in-out infinite;
		}
		@keyframes cell {
			50% {
				fill: #5b9be0;
			}
		}
		.go::after {
			animation: shine 4.5s var(--ease-in-out) 1.4s infinite;
		}
		@keyframes shine {
			0% {
				left: -60%;
			}
			30%,
			100% {
				left: 130%;
			}
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.win {
			opacity: 0.7;
		}
	}

	@media (max-width: 980px) {
		.login {
			grid-template-columns: minmax(0, 1fr);
			align-content: start;
			gap: 2rem;
			padding-top: 2rem;
		}
		.hero {
			max-width: none;
		}
		.brand {
			margin-bottom: 1.5rem;
		}
		.art {
			display: none;
		}
	}
	@media (max-width: 520px) {
		.card-form {
			padding: 1.5rem 1.25rem 1.25rem;
			border-radius: 20px;
		}
		.one {
			font-size: 1rem;
		}
	}
	@media (pointer: coarse) {
	}
	/* Телефон: усе на одному-півтора екранах, форма — головне */
	@media (max-width: 640px) {
		.login {
			min-height: 100dvh;
			gap: 1rem;
			align-content: center;
			padding: calc(1rem + env(safe-area-inset-top, 0px)) calc(1rem + env(safe-area-inset-right, 0px)) calc(1rem + env(safe-area-inset-bottom, 0px)) calc(1rem + env(safe-area-inset-left, 0px));
		}
		.brand {
			margin-bottom: 0.9rem;
			gap: 0.65rem;
		}
		.logo {
			width: 2.4rem;
			height: 2.4rem;
			border-radius: 12px;
		}
		.brand-name {
			font-size: 1.02rem;
		}
		.brand-sub {
			font-size: 0.8rem;
		}
		h1 {
			font-size: 1.5rem;
			margin-bottom: 0;
		}
		h1 br {
			display: none;
		}
		.one {
			display: none;
		}
		.card-form {
			padding: 1.1rem 1rem 1rem;
			border-radius: 20px;
		}
		.card-form h2 {
			font-size: 1.35rem;
			margin-bottom: 0.25rem;
		}
		.f {
			margin-bottom: 0.75rem;
		}
		.inp input {
			min-height: 48px;
		}
		/* Підказки посади — один ряд із прокруткою */
		.foot {
			font-size: 0.75rem;
			text-align: center;
		}
	}
</style>
