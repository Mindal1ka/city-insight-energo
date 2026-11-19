<script lang="ts">
	// Вхід: логін + пароль → POST /api/auth/login. Без входу застосунок недоступний.
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { login, safeNext, LoginError } from '#lib/auth.svelte.ts';
	import Icon from '#lib/Icon.svelte';

	let loginName = $state('');
	let password = $state('');
	let tried = $state(false);
	let busy = $state(false);
	let serverErr = $state('');

	const loginErr = $derived(loginName.trim() ? '' : 'Введіть логін');
	const passErr = $derived(password ? '' : 'Введіть пароль');

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		tried = true;
		serverErr = '';
		const first = loginErr ? 'login' : passErr ? 'pass' : null;
		if (first) {
			document.getElementById(first)?.focus();
			return;
		}
		busy = true;
		try {
			await login({ login: loginName.trim(), password });
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
</script>

<svelte:head><title>Вхід · Insight Tool</title></svelte:head>

<div class="login">
	<div class="bg" aria-hidden="true">
		<span class="orb o1"></span>
		<span class="orb o2"></span>
		<span class="grid"></span>
	</div>

	<main class="wrap-login">
		<header class="brand rise" style="--d: 0ms">
			<span class="logo" aria-hidden="true"><Icon name="bolt" size={26} stroke={2.2} /></span>
			<h1>Insight Tool</h1>
			<p class="city">Полтавська громада</p>
			<p class="one">Управління та деталізація споживання електроенергії комунальними закладами.</p>
		</header>

		<form class="card-form" onsubmit={submit} novalidate>
			<h2>Вхід</h2>

			<div class="f">
				<label for="login">Логін</label>
				<div class="inp">
					<Icon name="users" size={18} />
					<input
						id="login"
						type="text"
						autocomplete="username"
						autocapitalize="none"
						spellcheck="false"
						bind:value={loginName}
						aria-invalid={tried && !!loginErr}
						aria-describedby={tried && loginErr ? 'login-err' : undefined}
					/>
				</div>
				{#if tried && loginErr}<p id="login-err" class="err"><Icon name="alert" size={15} /> {loginErr}</p>{/if}
			</div>

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
		</form>
	</main>
</div>

<style>
	.login {
		position: relative;
		min-height: 100vh;
		min-height: 100dvh;
		display: grid;
		place-items: center;
		padding: calc(2rem + env(safe-area-inset-top, 0px)) calc(1rem + env(safe-area-inset-right, 0px)) calc(2rem + env(safe-area-inset-bottom, 0px)) calc(1rem + env(safe-area-inset-left, 0px));
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
		mask-image: radial-gradient(ellipse at 50% 45%, #000 20%, transparent 75%);
	}
	.wrap-login {
		width: 100%;
		max-width: 27rem;
		display: flex;
		flex-direction: column;
		gap: 1.75rem;
	}

	/* --- Бренд --- */
	.brand {
		text-align: center;
	}
	.logo {
		display: inline-grid;
		place-items: center;
		width: 3.25rem;
		height: 3.25rem;
		margin-bottom: 0.9rem;
		border-radius: 15px;
		background: linear-gradient(145deg, #ffd978, #f5a524 60%, #e88f05);
		color: #0f2f52;
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.5),
			0 8px 24px -6px rgba(245, 165, 36, 0.7);
	}
	h1 {
		color: #fff;
		font-size: clamp(2.25rem, 8vw, 3rem);
		line-height: 1.08;
		letter-spacing: -0.03em;
		margin: 0 0 0.3rem;
	}
	.city {
		margin: 0 0 0.75rem;
		font-size: 1.125rem;
		font-weight: 600;
		color: #ffd56b;
	}
	.one {
		margin: 0 auto;
		max-width: 24rem;
		font-size: 1rem;
		line-height: 1.55;
		color: #c9d6e6;
	}

	/* --- Форма --- */
	.card-form {
		position: relative;
		width: 100%;
		padding: 2rem 1.75rem 1.6rem;
		border-radius: 24px;
		background: rgba(255, 255, 255, 0.98);
		color: var(--text);
		box-shadow:
			0 40px 80px -30px rgba(0, 0, 0, 0.65),
			0 0 0 1px rgba(255, 255, 255, 0.4);
	}
	h2 {
		font-size: 1.5rem;
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
	.srv {
		padding: 0.55rem 0.75rem;
		border-radius: 12px;
		background: color-mix(in srgb, var(--bad) 8%, #fff);
	}
	.go {
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
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.5),
			0 14px 30px -14px rgba(245, 165, 36, 0.9);
		transition:
			transform var(--dur-base) var(--ease-out),
			filter var(--dur-fast);
	}
	.go:hover {
		transform: translateY(-1px);
		filter: saturate(1.1) brightness(1.03);
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
	}

	@media (max-width: 520px) {
		.card-form {
			padding: 1.4rem 1.1rem 1.15rem;
			border-radius: 20px;
		}
		.wrap-login {
			gap: 1.25rem;
		}
		.one {
			font-size: 0.9375rem;
		}
	}
</style>
