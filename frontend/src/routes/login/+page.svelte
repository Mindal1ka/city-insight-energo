<script lang="ts">
	// Вікно входу (тестовий вхід для демонстрації: будь-який непорожній пароль)
	import { login, DEFAULT_POSITION } from '#lib/auth.svelte.ts';
	import Icon from '#lib/Icon.svelte';

	let fullName = $state('');
	let position = $state(DEFAULT_POSITION);
	let password = $state('');
	let tried = $state(false);

	const nameErr = $derived(
		fullName.trim().split(/\s+/).filter(Boolean).length < 2
			? 'Вкажіть щонайменше прізвище та ім’я'
			: ''
	);
	const posErr = $derived(position.trim() ? '' : 'Вкажіть посаду');
	const passErr = $derived(password ? '' : 'Введіть пароль');

	function submit(e: SubmitEvent) {
		e.preventDefault();
		tried = true;
		if (nameErr || posErr || passErr) {
			const first = nameErr ? 'fio' : posErr ? 'pos' : 'pass';
			document.getElementById(first)?.focus();
			return;
		}
		// Переадресацію на ?next= робить +layout, щойно з'являється користувач
		login({ full_name: fullName.trim().replace(/\s+/g, ' '), position: position.trim() });
	}
</script>

<svelte:head><title>Вхід · City Insight Map · Енергія</title></svelte:head>

<div class="login">
	<section class="hero" aria-labelledby="hero-h">
		<div class="hero-in">
			<p class="brand">
				<span class="logo" aria-hidden="true"><Icon name="bolt" size={24} stroke={2.2} /></span>
				<span>
					<span class="brand-name">City Insight Map · Енергія</span>
					<span class="brand-sub">Полтавська громада · енергоменеджмент</span>
				</span>
			</p>

			<h1 id="hero-h">Уся енергія громади —<br /> в одному вікні</h1>
			<p class="lead-in">
				Сонячні станції й акумулятори комунальних закладів: скільки згенеровано, скільки спожито і
				чи вистачить енергії до кінця дня.
			</p>

			<ul class="feats">
				<li><span class="fi"><Icon name="building" size={20} /></span>Будівлі громади з реальними даними UMUNI</li>
				<li><span class="fi"><Icon name="sun" size={20} /></span>Генерація й споживання погодинно</li>
				<li><span class="fi"><Icon name="battery" size={20} /></span>Баланс розподілу: «+» чи «−» до кінця дня</li>
			</ul>

			<svg class="art" viewBox="0 0 520 260" aria-hidden="true" focusable="false">
				<defs>
					<radialGradient id="sunglow" cx="0.5" cy="0.5" r="0.5">
						<stop offset="0" stop-color="#ffd56b" stop-opacity="0.55" />
						<stop offset="1" stop-color="#ffd56b" stop-opacity="0" />
					</radialGradient>
					<linearGradient id="pv" x1="0" x2="1" y1="0" y2="1">
						<stop offset="0" stop-color="#2f6db0" />
						<stop offset="1" stop-color="#173f6b" />
					</linearGradient>
				</defs>
				<circle cx="410" cy="70" r="90" fill="url(#sunglow)" />
				<circle cx="410" cy="70" r="34" fill="#f5a524" />
				<!-- хвиля генерації -->
				<path d="M0 210 C 90 210, 120 120, 200 120 S 320 205, 520 190" fill="none" stroke="#f5a524" stroke-width="3" stroke-opacity="0.75" />
				<path d="M0 225 C 110 225, 160 170, 260 175 S 400 215, 520 210" fill="none" stroke="#7fb2e5" stroke-width="2.5" stroke-dasharray="6 6" stroke-opacity="0.7" />
				<!-- будівля зі станцією -->
				<g transform="translate(70 120)">
					<path d="M0 50 L60 18 L120 50 Z" fill="#183c63" />
					<g transform="translate(18 22) skewX(-28)">
						{#each [0, 1, 2] as i (i)}
							{#each [0, 1] as j (j)}
								<rect x={i * 22 + j * 0} y={j * 12} width="20" height="10" rx="1.5" fill="url(#pv)" stroke="#8fc0f0" stroke-width="0.8" />
							{/each}
						{/each}
					</g>
					<rect x="8" y="50" width="104" height="70" fill="#163a60" />
					{#each [0, 1, 2] as i (i)}
						<rect x={22 + i * 30} y="64" width="16" height="16" rx="2" fill="#ffd56b" fill-opacity={i === 1 ? 0.85 : 0.45} />
						<rect x={22 + i * 30} y="92" width="16" height="16" rx="2" fill="#ffd56b" fill-opacity={i === 0 ? 0.8 : 0.35} />
					{/each}
				</g>
			</svg>
		</div>
	</section>

	<section class="side" aria-labelledby="form-h">
		<form class="card-form" onsubmit={submit} novalidate>
			<span class="lock" aria-hidden="true"><Icon name="lock" size={22} /></span>
			<h2 id="form-h">Вхід до системи</h2>
			<p class="sub">Внутрішня версія для фахівців громади.</p>

			<div class="f">
				<label for="fio">ПІБ</label>
				<input
					id="fio"
					type="text"
					autocomplete="name"
					placeholder="Прізвище Ім'я По батькові"
					bind:value={fullName}
					aria-invalid={tried && !!nameErr}
					aria-describedby="fio-hint{tried && nameErr ? ' fio-err' : ''}"
				/>
				<p id="fio-hint" class="hint">Прізвище, ім’я, по батькові</p>
				{#if tried && nameErr}<p id="fio-err" class="err"><Icon name="alert" size={15} /> {nameErr}</p>{/if}
			</div>

			<div class="f">
				<label for="pos">Посада</label>
				<input
					id="pos"
					type="text"
					autocomplete="organization-title"
					bind:value={position}
					aria-invalid={tried && !!posErr}
					aria-describedby={tried && posErr ? 'pos-err' : undefined}
				/>
				{#if tried && posErr}<p id="pos-err" class="err"><Icon name="alert" size={15} /> {posErr}</p>{/if}
			</div>

			<div class="f">
				<label for="pass">Пароль</label>
				<input
					id="pass"
					type="password"
					autocomplete="current-password"
					bind:value={password}
					aria-invalid={tried && !!passErr}
					aria-describedby={tried && passErr ? 'pass-err' : undefined}
				/>
				{#if tried && passErr}<p id="pass-err" class="err"><Icon name="alert" size={15} /> {passErr}</p>{/if}
			</div>

			<button class="btn go" type="submit">Увійти <Icon name="arrow-right" size={18} /></button>

			<p class="test-note">
				<Icon name="info" size={16} />
				<span><strong>Тестовий вхід для демонстрації.</strong> Підійде будь-який непорожній пароль; дані входу зберігаються лише в цій вкладці браузера.</span>
			</p>
		</form>
	</section>
</div>

<style>
	.login {
		min-height: 100vh;
		display: grid;
		grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
		background: var(--bg);
	}
	.hero {
		position: relative;
		overflow: hidden;
		color: #fff;
		background:
			radial-gradient(900px 500px at 90% 0%, rgba(245, 165, 36, 0.22), transparent 60%),
			radial-gradient(700px 500px at 0% 100%, rgba(47, 109, 176, 0.35), transparent 60%),
			linear-gradient(160deg, #123862, #0b2440);
		display: flex;
		align-items: center;
	}
	.hero-in {
		width: 100%;
		max-width: 44rem;
		margin: 0 auto;
		padding: 3rem 3.5rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		margin-bottom: 3rem;
	}
	.logo {
		display: grid;
		place-items: center;
		width: 2.9rem;
		height: 2.9rem;
		border-radius: 14px;
		background: linear-gradient(145deg, #ffd56b, #f5a524);
		color: #0f2f52;
	}
	.brand-name {
		display: block;
		font-weight: 700;
		font-size: 1.2rem;
	}
	.brand-sub {
		display: block;
		color: var(--navy-ink);
		font-size: 0.875rem;
	}
	h1 {
		font-size: clamp(2rem, 3.2vw, 3.1rem);
		font-weight: 750;
		letter-spacing: -0.02em;
		line-height: 1.1;
		margin-bottom: 1rem;
	}
	.lead-in {
		font-size: 1.15rem;
		color: #d6e1ee;
		max-width: 36rem;
		margin-bottom: 1.75rem;
	}
	.feats {
		list-style: none;
		padding: 0;
		margin: 0 0 1.5rem;
		display: grid;
		gap: 0.7rem;
	}
	.feats li {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		color: #eef3f9;
	}
	.fi {
		display: grid;
		place-items: center;
		width: 2.3rem;
		height: 2.3rem;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.09);
		border: 1px solid rgba(255, 255, 255, 0.14);
		color: #ffd56b;
	}
	.art {
		display: block;
		width: 100%;
		max-width: 34rem;
		height: auto;
		margin-top: 0.5rem;
	}
	.side {
		display: grid;
		place-items: center;
		padding: 2.5rem 1.5rem;
	}
	.card-form {
		width: 100%;
		max-width: 28rem;
		background: #fff;
		border: 1px solid #e3e8ef;
		border-radius: 20px;
		box-shadow: var(--shadow-lg);
		padding: 2.25rem 2.25rem 1.75rem;
	}
	.lock {
		display: grid;
		place-items: center;
		width: 3rem;
		height: 3rem;
		border-radius: 14px;
		background: #e6eef8;
		color: var(--navy-3);
		margin-bottom: 1rem;
	}
	h2 {
		font-size: 1.6rem;
		margin-bottom: 0.25rem;
	}
	.sub {
		color: var(--muted);
		margin-bottom: 1.5rem;
	}
	.f {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		margin-bottom: 1.1rem;
	}
	.f input {
		font: inherit;
		min-height: 48px;
		padding: 0.6rem 0.85rem;
		border: 1px solid var(--line-strong);
		border-radius: 12px;
		background: #fff;
		color: var(--text);
		transition:
			border-color 0.15s,
			box-shadow 0.15s;
	}
	.f input::placeholder {
		color: #6b7686;
	}
	.f input:hover {
		border-color: #6b7686;
	}
	.f input:focus-visible {
		border-color: var(--accent);
		box-shadow: 0 0 0 4px rgba(11, 92, 173, 0.18);
		outline: 3px solid var(--focus);
		outline-offset: 1px;
	}
	.f input[aria-invalid='true'] {
		border-color: var(--bad);
	}
	.hint {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.err {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--bad);
	}
	.go {
		width: 100%;
		justify-content: center;
		min-height: 50px;
		font-size: 1.05rem;
		border-radius: 12px;
		margin-top: 0.4rem;
		background: var(--navy);
		border-color: var(--navy);
	}
	.go:hover {
		background: var(--navy-3);
	}
	.test-note {
		display: flex;
		gap: 0.5rem;
		margin: 1.25rem 0 0;
		padding: 0.75rem 0.85rem;
		border-radius: 12px;
		background: var(--sun-soft);
		border: 1px dashed #d08a1c;
		font-size: 0.85rem;
		line-height: 1.45;
		color: #4a3200;
	}
	.test-note :global(.icon) {
		margin-top: 0.1rem;
		color: var(--sun-ink);
	}
	@media (max-width: 960px) {
		.login {
			grid-template-columns: 1fr;
		}
		.hero-in {
			padding: 2rem 1.5rem;
		}
		.brand {
			margin-bottom: 1.5rem;
		}
		.art {
			display: none;
		}
	}
</style>
