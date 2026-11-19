<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { auth, logout, initials, safeNext } from '#lib/auth.svelte.ts';
	import Icon from '#lib/Icon.svelte';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const isLogin = $derived(page.url.pathname === '/login');

	// Клієнтський «замок»: без тестового входу всі сторінки ведуть на /login
	$effect(() => {
		if (!auth.user && !isLogin) {
			const back = page.url.pathname + page.url.search;
			goto('/login' + (back !== '/' ? `?next=${encodeURIComponent(back)}` : ''), { replace: true });
		} else if (auth.user && isLogin) {
			// Після входу (або якщо вже увійшли) — на сторінку, з якої прийшли
			goto(safeNext(page.url), { replace: true });
		}
	});

	// Аналітичні сторінки на реальних даних UMUNI
	const analytics = [
		{ href: '/overview', label: 'Огляд споживання' },
		{ href: '/rating', label: 'Рейтинг' },
		{ href: '/defects', label: 'Якість даних' },
		{ href: '/solar', label: 'Нові СЕС' },
		{ href: '/upload', label: 'Оновити дані' }
	];

	function isActive(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/' || p.startsWith('/object/');
		// Картка будівлі логічно належить до рейтингу
		if (href === '/rating' && p.startsWith('/building/')) return true;
		return p === href || p.startsWith(href + '/');
	}

	// Після виходу «замок» сам відкриє /login (з ?next=, щоб повернутися туди ж)
	function signOut() {
		logout();
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>City Insight Map · Енергія</title>
</svelte:head>

{#if isLogin}
	{@render children()}
{:else if auth.user}
	<a class="skip no-print" href="#main">Перейти до змісту</a>

	<header class="site-header no-print">
		<div class="wrap head-row">
			<a class="brand" href="/">
				<span class="logo" aria-hidden="true"><Icon name="bolt" size={22} stroke={2.2} /></span>
				<span>
					<span class="brand-name">City Insight Map · Енергія</span>
					<span class="brand-sub">Полтавська громада · енергоменеджмент</span>
				</span>
			</a>
			<div class="user">
				<span class="avatar" aria-hidden="true">{initials(auth.user.full_name)}</span>
				<span class="who">
					<span class="user-name">{auth.user.full_name}</span>
					<span class="user-role">{auth.user.position}</span>
				</span>
				<button type="button" class="out" onclick={signOut}>
					<Icon name="logout" size={18} /> Вийти
				</button>
			</div>
		</div>
		<nav class="wrap main-nav" aria-label="Основне меню">
			<ul class="primary">
				<li>
					<a href="/" aria-current={isActive('/') ? 'page' : undefined}>
						<Icon name="building" size={18} /> Об’єкти
					</a>
				</li>
			</ul>
			<span class="divider" aria-hidden="true"></span>
			<div class="group" role="group" aria-labelledby="nav-analytics">
				<span id="nav-analytics" class="group-label"><Icon name="chart" size={16} /> Аналітика</span>
				<ul>
					{#each analytics as item (item.href)}
						<li>
							<a href={item.href} aria-current={isActive(item.href) ? 'page' : undefined}>{item.label}</a>
						</li>
					{/each}
				</ul>
			</div>
		</nav>
	</header>

	<main id="main" class="wrap" tabindex="-1">
		{@render children()}
	</main>

	<footer class="site-footer">
		<div class="wrap foot-row">
			<p>
				Будівлі й річне споживання — реальні дані UMUNI. Станції, телеметрія й ліміти позначені
				«ДЕМО-ДАНІ». Аналітична оцінка, не офіційний енергосертифікат.
			</p>
			<p class="muted small no-print">Poltava Open Data Hackathon · трек 2 «Енергетичний менеджмент»</p>
		</div>
	</footer>
{/if}

<style>
	:global(.wrap) {
		max-width: 1480px;
		margin: 0 auto;
		padding: 0 2rem;
	}
	@media (max-width: 700px) {
		:global(.wrap) {
			padding: 0 1rem;
		}
	}
	.skip {
		position: absolute;
		left: -9999px;
		top: 0.5rem;
		background: #fff;
		padding: 0.5rem 1rem;
		z-index: 100;
	}
	.skip:focus {
		left: 0.5rem;
	}
	.site-header {
		background:
			radial-gradient(1200px 300px at 85% -120px, rgba(245, 165, 36, 0.18), transparent 60%),
			linear-gradient(180deg, #0f2f52, #0d2947);
		color: #fff;
		box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset;
	}
	.head-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		padding-top: 0.9rem;
		padding-bottom: 0.7rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		color: #fff;
		text-decoration: none;
	}
	.brand:hover {
		color: #fff;
	}
	.logo {
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 12px;
		background: linear-gradient(145deg, #ffd56b, #f5a524);
		color: #0f2f52;
		box-shadow: 0 4px 14px -4px rgba(245, 165, 36, 0.6);
	}
	.brand-name {
		display: block;
		font-size: 1.2rem;
		font-weight: 700;
		letter-spacing: 0.01em;
	}
	.brand-sub {
		display: block;
		font-size: 0.85rem;
		color: var(--navy-ink);
	}
	.user {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
	}
	.avatar {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		border-radius: 50%;
		background: #24507f;
		border: 2px solid rgba(255, 213, 107, 0.7);
		font-weight: 700;
		font-size: 0.9rem;
		flex: none;
	}
	.who {
		display: flex;
		flex-direction: column;
		line-height: 1.25;
		min-width: 0;
	}
	.user-name {
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 22rem;
	}
	.user-role {
		font-size: 0.8125rem;
		color: var(--navy-ink);
	}
	.out {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: 0.4rem;
		padding: 0.45rem 0.85rem;
		border-radius: 10px;
		border: 1px solid rgba(255, 255, 255, 0.35);
		background: transparent;
		color: #fff;
		font: inherit;
		font-weight: 600;
		font-size: 0.9rem;
		cursor: pointer;
		min-height: 40px;
	}
	.out:hover {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.6);
	}
	.main-nav {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0 0.75rem;
	}
	.main-nav ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.15rem;
	}
	.main-nav a {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.65rem 0.85rem;
		color: #dfe7f1;
		text-decoration: none;
		font-weight: 500;
		border-bottom: 3px solid transparent;
		border-radius: 8px 8px 0 0;
	}
	.main-nav a:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.07);
	}
	.main-nav a[aria-current='page'] {
		color: #fff;
		font-weight: 700;
		border-bottom-color: var(--sun);
	}
	.primary a {
		font-size: 1.05rem;
		font-weight: 700;
		color: #fff;
	}
	.divider {
		width: 1px;
		height: 1.6rem;
		background: rgba(255, 255, 255, 0.2);
		margin: 0 0.35rem;
	}
	.group {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0 0.25rem;
	}
	.group-label {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #9fb3cb;
		margin-right: 0.15rem;
	}
	.group a {
		font-size: 0.925rem;
	}
	main {
		padding-top: 1.75rem;
		padding-bottom: 3rem;
		min-height: 70vh;
	}
	main:focus {
		outline: none;
	}
	.site-footer {
		border-top: 1px solid var(--line);
		background: var(--surface);
		padding: 1rem 0;
		font-size: 0.875rem;
	}
	.foot-row {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.25rem 2rem;
	}
	.site-footer p {
		margin: 0.2rem 0;
	}
	@media (max-width: 1000px) {
		.brand-sub,
		.user-role {
			display: none;
		}
	}
	@media (max-width: 760px) {
		.who {
			display: none;
		}
		.divider {
			display: none;
		}
		.group-label {
			width: 100%;
			padding: 0.25rem 0 0 0.85rem;
		}
	}
	@media print {
		.site-footer {
			border-top: 1px solid #999;
		}
	}
</style>
