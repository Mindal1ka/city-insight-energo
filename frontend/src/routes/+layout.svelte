<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { goto, afterNavigate } from '$app/navigation';
	import { tick } from 'svelte';
	import { auth, logout, initials, safeNext } from '#lib/auth.svelte.ts';
	import Icon from '#lib/Icon.svelte';
	import Term from '#lib/Term.svelte';
	import CommandPalette from '#lib/CommandPalette.svelte';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const isLogin = $derived(page.url.pathname === '/login');

	// Клієнтський «замок»: без тестового входу всі сторінки ведуть на /login
	$effect(() => {
		if (!auth.user && !isLogin) {
			const back = page.url.pathname + page.url.search;
			goto('/login' + (back !== '/' ? `?next=${encodeURIComponent(back)}` : ''), { replace: true });
		} else if (auth.user && isLogin) {
			goto(safeNext(page.url), { replace: true });
		}
	});

	// Основні сценарії продукту: електроенергія, сонце, енергонезалежність
	const primary = [
		{ href: '/', label: 'Об’єкти', icon: 'building' },
		{ href: '/independence', label: 'Енергонезалежність', icon: 'battery' },
		{ href: '/solar', label: 'Де ставити СЕС', icon: 'sun' }
	] as const;

	// Аналітика на реальних річних даних UMUNI
	const analytics = [
		{ href: '/overview', label: 'Споживання електроенергії', hint: 'Скільки й хто споживає' },
		{ href: '/rating', label: 'Рейтинг будівель', hint: 'Порівняння за кВт·год/м²' },
		{ href: '/defects', label: 'Якість даних', hint: 'Помилки й пропуски в UMUNI' },
		{ href: '/upload', label: 'Оновити дані', hint: 'Завантажити новий файл' }
	];

	function isActive(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/' || p.startsWith('/object/');
		// Паспорт даних будівлі логічно належить до рейтингу
		if (href === '/rating' && p.startsWith('/building/')) return true;
		return p === href || p.startsWith(href + '/');
	}
	const analyticsActive = $derived(analytics.find((a) => isActive(a.href)) ?? null);

	// --- Меню «Аналітика» (розкривний список посилань) ---
	let menuOpen = $state(false);
	let menuBtn = $state<HTMLButtonElement>();
	let menuEl = $state<HTMLUListElement>();

	async function openMenu(focusIdx: number | null = null) {
		menuOpen = true;
		if (focusIdx === null) return;
		await tick();
		const links = menuEl?.querySelectorAll<HTMLAnchorElement>('a');
		if (links?.length) links[(focusIdx + links.length) % links.length].focus();
	}
	function closeMenu(focusBtn = false) {
		menuOpen = false;
		if (focusBtn) menuBtn?.focus();
	}
	function menuBtnKey(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			openMenu(0);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			openMenu(-1);
		}
	}
	function menuKey(e: KeyboardEvent) {
		const links = [...(menuEl?.querySelectorAll<HTMLAnchorElement>('a') ?? [])];
		const i = links.indexOf(document.activeElement as HTMLAnchorElement);
		if (e.key === 'Escape') {
			e.preventDefault();
			closeMenu(true);
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			links[(i + 1) % links.length]?.focus();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			links[(i - 1 + links.length) % links.length]?.focus();
		} else if (e.key === 'Home') {
			e.preventDefault();
			links[0]?.focus();
		} else if (e.key === 'End') {
			e.preventDefault();
			links.at(-1)?.focus();
		}
	}
	function menuFocusOut(e: FocusEvent) {
		const next = e.relatedTarget as Node | null;
		const root = (e.currentTarget as HTMLElement).closest('.dd');
		if (next && root && !root.contains(next)) menuOpen = false;
	}

	// --- Мобільне меню (< 900 px) ---
	let navOpen = $state(false);

	// --- Глобальний пошук ---
	let paletteOpen = $state(false);

	afterNavigate(() => {
		menuOpen = false;
		navOpen = false;
	});

	function globalKey(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K' || e.code === 'KeyK')) {
			if (!auth.user || isLogin) return;
			e.preventDefault();
			paletteOpen = !paletteOpen;
		} else if (e.key === 'Escape' && (menuOpen || navOpen)) {
			menuOpen = false;
			navOpen = false;
		}
	}
	function globalDown(e: PointerEvent) {
		if (menuOpen && !(e.target as HTMLElement).closest?.('.dd')) menuOpen = false;
	}

	function signOut() {
		logout();
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>City Insight Map · Енергія</title>
</svelte:head>

<svelte:window onkeydown={globalKey} onpointerdown={globalDown} />

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
					<span class="brand-sub">Полтавська громада · електроенергія та енергонезалежність</span>
				</span>
			</a>

			<button type="button" class="search-btn" onclick={() => (paletteOpen = true)} aria-keyshortcuts="Control+K" aria-label="Пошук будівлі (Ctrl+K)">
				<Icon name="search" size={18} />
				<span class="search-txt">Пошук будівлі…</span>
				<kbd class="search-kbd" aria-hidden="true">Ctrl K</kbd>
			</button>

			<div class="user">
				<span class="avatar" aria-hidden="true">{initials(auth.user.full_name)}</span>
				<span class="who">
					<span class="user-name">{auth.user.full_name}</span>
					<span class="user-role">{auth.user.position}</span>
				</span>
				<button type="button" class="out" onclick={signOut}>
					<Icon name="logout" size={18} /> <span class="out-txt">Вийти</span>
				</button>
			</div>

			<button
				type="button"
				class="burger"
				aria-expanded={navOpen}
				aria-controls="main-nav"
				onclick={() => (navOpen = !navOpen)}
			>
				<span class="burger-ico" aria-hidden="true"><span></span><span></span><span></span></span>
				Меню
			</button>
		</div>

		<nav id="main-nav" class="wrap main-nav" class:open={navOpen} aria-label="Основне меню">
			<ul class="primary">
				{#each primary as item (item.href)}
					<li>
						<a href={item.href} aria-current={isActive(item.href) ? 'page' : undefined}>
							<Icon name={item.icon} size={18} />
							{item.label}
						</a>
					</li>
				{/each}
			</ul>

			<span class="divider" aria-hidden="true"></span>

			<div class="dd" class:has-active={!!analyticsActive}>
				<button
					bind:this={menuBtn}
					type="button"
					class="dd-btn"
					aria-expanded={menuOpen}
					aria-controls="nav-analytics"
					onclick={() => (menuOpen ? closeMenu() : openMenu())}
					onkeydown={menuBtnKey}
				>
					<Icon name="chart" size={18} />
					<span>Аналітика{#if analyticsActive}<span class="dd-cur">: {analyticsActive.label}</span>{/if}</span>
					<svg class="chev" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
						<path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
					</svg>
				</button>
				<span class="dd-mobile-label" aria-hidden="true"><Icon name="chart" size={16} /> Аналітика</span>
				<!-- svelte-ignore a11y_no_noninteractive_element_interactions (стрілки між посиланнями меню) -->
				<ul
					id="nav-analytics"
					class="dd-menu"
					class:open={menuOpen}
					bind:this={menuEl}
					onkeydown={menuKey}
					onfocusout={menuFocusOut}
				>
					{#each analytics as item (item.href)}
						<li>
							<a href={item.href} aria-current={isActive(item.href) ? 'page' : undefined}>
								<span class="dd-label">{item.label}</span>
								<span class="dd-hint">{item.hint}</span>
							</a>
						</li>
					{/each}
				</ul>
			</div>
		</nav>
	</header>

	<CommandPalette bind:open={paletteOpen} />

	<main id="main" class="wrap" tabindex="-1">
		{@render children()}
	</main>

	<footer class="site-footer">
		<div class="wrap foot-row">
			<p>
				Будівлі й річне споживання електроенергії — реальні дані <Term key="UMUNI" />. Станції,
				телеметрія й ліміти позначені <Term key="ДЕМО-ДАНІ" />. Аналітична оцінка, не офіційний
				енергосертифікат.
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
		position: relative;
		z-index: 20;
		background:
			radial-gradient(1200px 300px at 85% -120px, rgba(245, 165, 36, 0.18), transparent 60%),
			linear-gradient(180deg, #0f2f52, #0d2947);
		color: #fff;
	}
	.site-header :global(:focus-visible) {
		outline-color: var(--focus);
		box-shadow: 0 0 0 5px #0d2947;
	}
	.head-row {
		display: flex;
		align-items: center;
		gap: 1rem 1.5rem;
		padding-top: 0.9rem;
		padding-bottom: 0.7rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		color: #fff;
		text-decoration: none;
		min-width: 0;
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
		flex: none;
	}
	.brand-name {
		display: block;
		font-size: 1.2rem;
		font-weight: 700;
		letter-spacing: 0.01em;
		white-space: nowrap;
	}
	.brand-sub {
		display: block;
		font-size: 0.85rem;
		color: var(--navy-ink);
	}
	.search-btn {
		margin-left: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		min-height: 42px;
		min-width: 15rem;
		padding: 0.4rem 0.6rem 0.4rem 0.85rem;
		border-radius: 10px;
		border: 1px solid rgba(255, 255, 255, 0.22);
		background: rgba(255, 255, 255, 0.08);
		color: #dfe7f1;
		font: inherit;
		font-size: 0.95rem;
		cursor: pointer;
		text-align: left;
	}
	.search-btn:hover {
		background: rgba(255, 255, 255, 0.14);
		border-color: rgba(255, 255, 255, 0.4);
		color: #fff;
	}
	.search-txt {
		flex: 1;
		white-space: nowrap;
	}
	.search-kbd {
		font: inherit;
		font-size: 0.75rem;
		padding: 0.1rem 0.4rem;
		border-radius: 5px;
		border: 1px solid rgba(255, 255, 255, 0.3);
		color: #c9d6e6;
		white-space: nowrap;
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
		max-width: 16rem;
	}
	.user-role {
		font-size: 0.8125rem;
		color: var(--navy-ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 16rem;
	}
	.out,
	.burger {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.45rem 0.85rem;
		border-radius: 10px;
		border: 1px solid rgba(255, 255, 255, 0.35);
		background: transparent;
		color: #fff;
		font: inherit;
		font-weight: 600;
		font-size: 0.9rem;
		cursor: pointer;
		min-height: 42px;
		flex: none;
	}
	.out:hover,
	.burger:hover {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.6);
	}
	.burger {
		display: none;
	}
	.burger-ico {
		display: inline-flex;
		flex-direction: column;
		gap: 3px;
	}
	.burger-ico span {
		display: block;
		width: 16px;
		height: 2px;
		border-radius: 2px;
		background: currentColor;
	}

	/* --- Навігація --- */
	.main-nav {
		display: flex;
		align-items: center;
		gap: 0 0.5rem;
	}
	.main-nav ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.primary {
		display: flex;
		gap: 0.15rem;
	}
	.primary a,
	.dd-btn {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.7rem 0.9rem;
		color: #dfe7f1;
		text-decoration: none;
		font: inherit;
		font-weight: 600;
		font-size: 1.02rem;
		border: 0;
		border-bottom: 3px solid transparent;
		border-radius: 8px 8px 0 0;
		background: none;
		cursor: pointer;
		white-space: nowrap;
	}
	.primary a:hover,
	.dd-btn:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.07);
	}
	.primary a[aria-current='page'],
	.dd.has-active .dd-btn {
		color: #fff;
		font-weight: 700;
		border-bottom-color: var(--sun);
	}
	.divider {
		width: 1px;
		height: 1.6rem;
		background: rgba(255, 255, 255, 0.2);
		margin: 0 0.25rem;
	}
	.dd {
		position: relative;
	}
	.dd-cur {
		font-weight: 500;
		color: #ffd56b;
	}
	.chev {
		transition: transform 0.15s;
	}
	.dd-btn[aria-expanded='true'] .chev {
		transform: rotate(180deg);
	}
	.dd-mobile-label {
		display: none;
	}
	.dd-menu {
		display: none;
		position: absolute;
		top: calc(100% + 4px);
		left: 0;
		min-width: 19rem;
		padding: 0.4rem;
		background: #fff;
		border-radius: 12px;
		box-shadow: 0 18px 40px -10px rgba(8, 20, 38, 0.45);
		border: 1px solid #dfe5ec;
		z-index: 30;
	}
	.dd-menu.open {
		display: block;
	}
	.dd-menu a {
		display: flex;
		flex-direction: column;
		padding: 0.55rem 0.8rem;
		border-radius: 8px;
		color: var(--text);
		text-decoration: none;
	}
	.dd-menu a:hover,
	.dd-menu a:focus-visible {
		background: var(--accent-soft);
	}
	.dd-menu a:focus-visible {
		box-shadow: 0 0 0 2px var(--accent);
		outline-offset: -3px;
	}
	.dd-menu a[aria-current='page'] {
		background: var(--sun-soft);
		box-shadow: inset 3px 0 0 var(--sun-strong);
	}
	.dd-label {
		font-weight: 600;
	}
	.dd-hint {
		font-size: 0.85rem;
		color: var(--muted);
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

	@media (max-width: 1200px) {
		.brand-sub,
		.user-role {
			display: none;
		}
		.search-btn {
			min-width: 12rem;
		}
	}
	@media (max-width: 1100px) {
		.who {
			display: none;
		}
	}
	@media (max-width: 899px) {
		.burger {
			display: inline-flex;
		}
		.search-btn {
			min-width: 0;
		}
		.search-kbd,
		.search-txt {
			display: none;
		}
		.main-nav {
			display: none;
			flex-direction: column;
			align-items: stretch;
			padding-bottom: 0.75rem;
		}
		.main-nav.open {
			display: flex;
		}
		.primary {
			flex-direction: column;
		}
		.primary a {
			border-bottom: 0;
			border-left: 3px solid transparent;
			border-radius: 0 8px 8px 0;
		}
		.primary a[aria-current='page'] {
			border-left-color: var(--sun);
			background: rgba(255, 255, 255, 0.06);
		}
		.divider {
			width: 100%;
			height: 1px;
			margin: 0.4rem 0;
		}
		.dd-btn {
			display: none;
		}
		.dd-mobile-label {
			display: inline-flex;
			align-items: center;
			gap: 0.35rem;
			padding: 0.3rem 0.9rem;
			font-size: 0.75rem;
			font-weight: 700;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			color: #9fb3cb;
		}
		.dd-menu,
		.dd-menu.open {
			display: block;
			position: static;
			min-width: 0;
			padding: 0;
			background: none;
			border: 0;
			box-shadow: none;
		}
		.dd-menu a {
			color: #dfe7f1;
			border-radius: 0 8px 8px 0;
			border-left: 3px solid transparent;
		}
		.dd-menu a:hover {
			background: rgba(255, 255, 255, 0.07);
		}
		.dd-menu a[aria-current='page'] {
			background: rgba(255, 255, 255, 0.06);
			border-left-color: var(--sun);
			box-shadow: none;
			color: #fff;
		}
		.dd-hint {
			color: #9fb3cb;
		}
	}
	@media (max-width: 600px) {
		.brand-name {
			font-size: 1rem;
		}
		.search-txt,
		.out-txt {
			display: none;
		}
		.head-row {
			gap: 0.6rem;
		}
	}
	@media print {
		.site-footer {
			border-top: 1px solid #999;
		}
	}
</style>
