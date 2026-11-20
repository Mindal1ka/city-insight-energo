<script lang="ts">
	// Каркас: бокове меню з групами розділів (десктоп) і висувне меню (телефон).
	import '../app.css';
	import '#lib/motion-speed.ts';
	import favicon from '#lib/assets/favicon.svg';
	import { page, navigating } from '$app/state';
	import { untrack } from 'svelte';
	import { goto, afterNavigate, onNavigate } from '$app/navigation';
	import { auth, logout, initials, verifySession } from '#lib/auth.svelte.ts';
	import { isCityWide, isInternal, canUpload, roleLabel } from '#lib/roles.ts';
	import { isReduced, resetWave, navIndicator, autoReveal } from '#lib/motion.ts';
	import Icon from '#lib/Icon.svelte';
	import FreshnessBadge from '#lib/FreshnessBadge.svelte';
	import { startBackgroundData, onUserReady } from '#lib/prefetch.ts';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const isLogin = $derived(page.url.pathname === '/login');
	// Публічні сторінки без каркаса й без входу: /login і презентація /pitch
	const isPublic = $derived(isLogin || page.url.pathname === '/pitch' || page.url.pathname.startsWith('/pitch/'));
	const roleText = $derived(roleLabel(auth.user));

	// Шлюз входу: без користувача доступна лише /login
	$effect(() => {
		if (auth.user || isPublic) return;
		const back = page.url.pathname + page.url.search;
		goto('/login' + (back !== '/' ? `?next=${encodeURIComponent(back)}` : ''), { replace: true, reset: false });
	});

	// Збережений токен перевіряємо один раз (прострочений → вихід → /login)
	verifySession();

	// Фонове завантаження даних усіх розділів ролі + періодичне оновлення «живих» (lib/prefetch.ts)
	startBackgroundData();
	const userKey = $derived(auth.user ? `${auth.user.role}|${auth.user.building_id}|${auth.user.department}|${auth.user.full_name}` : '');
	$effect(() => {
		if (userKey) untrack(onUserReady);
	});

	function signOut() {
		logout();
		drawer = false;
		goto('/login', { replace: true, reset: false });
	}

	// Плавна зміна сторінки (View Transitions API), меню лишається на місці
	onNavigate((nav) => {
		// Кожен перехід (і повторний візит, і «назад») — нова перша хвиля появи для сторінки-цілі
		if (nav.from?.url.pathname !== nav.to?.url.pathname) resetWave(nav.to?.url.pathname);
		if (typeof document === 'undefined' || !('startViewTransition' in document) || isReduced()) return;
		if (nav.from?.url.pathname === nav.to?.url.pathname) return;
		return new Promise<void>((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await nav.complete;
			});
		});
	});

	type IconName = 'gauge' | 'pin' | 'building' | 'bolt' | 'chart' | 'wallet' | 'battery' | 'users' | 'grid';
	type Item = { href: string; label: string; icon: IconName; only?: 'internal' | 'citywide' | 'upload' };
	type Group = { title: string; items: Item[] };

	const GROUPS: Group[] = [
		{
			title: 'Моніторинг',
			items: [
				{ href: '/dashboard', label: 'Огляд громади', icon: 'gauge' },
				{ href: '/', label: 'Мапа', icon: 'pin' },
				{ href: '/objects', label: 'Об’єкти', icon: 'building' },
				{ href: '/energy', label: 'Енергія зараз', icon: 'bolt' },
				{ href: '/overview', label: 'Споживання', icon: 'chart' }
			]
		},
		{
			title: 'Фінанси',
			items: [
				{ href: '/finance', label: 'Бюджет і ліміти', icon: 'wallet' },
				{ href: '/report', label: 'Звіт за місяць', icon: 'chart' }
			]
		},
		{
			title: 'Енергобезпека',
			items: [{ href: '/blackout', label: 'Готовність до блекауту', icon: 'battery', only: 'citywide' }]
		},
		{
			title: 'Робота',
			items: [
				{ href: '/appeals', label: 'Звернення', icon: 'users', only: 'internal' },
				{ href: '/upload', label: 'Оновити дані', icon: 'grid', only: 'upload' }
			]
		}
	];

	const allowed = (i: Item) =>
		!i.only ||
		(i.only === 'internal' ? isInternal(auth.user) : i.only === 'citywide' ? isCityWide(auth.user) : canUpload(auth.user));
	const groups = $derived(GROUPS.map((g) => ({ ...g, items: g.items.filter(allowed) })).filter((g) => g.items.length));

	function isActive(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/' || p === '/map';
		if (href === '/objects') return p.startsWith('/objects') || p.startsWith('/object/');
		return p === href || p.startsWith(href + '/');
	}
	const current = $derived(groups.flatMap((g) => g.items).find((i) => isActive(i.href)) ?? null);

	let drawer = $state(false);
	let paletteOpen = $state(false);
	// Палітра (583 рядки + список будівель) вантажиться лише при першому відкритті або наведенні на пошук
	let paletteWanted = $state(false);
	let paletteMod = $state<Promise<typeof import('#lib/CommandPalette.svelte')> | null>(null);
	$effect(() => {
		if ((paletteWanted || paletteOpen) && !paletteMod) paletteMod = import('#lib/CommandPalette.svelte');
	});
	const warmPalette = () => (paletteWanted = true);

	// Тонка смуга прогресу: з'являється лише якщо перехід триває > 120 мс (швидкі переходи — без шуму)
	let navBar = $state<'idle' | 'on' | 'done'>('idle');
	$effect(() => {
		const busy = !!navigating.to;
		return untrack(() => {
			if (busy) {
				const t = setTimeout(() => (navBar = 'on'), 120);
				return () => clearTimeout(t);
			}
			if (navBar === 'on') {
				navBar = 'done';
				const t = setTimeout(() => (navBar = 'idle'), 400);
				return () => clearTimeout(t);
			}
		});
	});

	afterNavigate(() => {
		drawer = false;
	});

	function globalKey(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K' || e.code === 'KeyK')) {
			if (isLogin) return;
			e.preventDefault();
			paletteOpen = !paletteOpen;
		} else if (e.key === 'Escape' && drawer) {
			drawer = false;
		}
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Insight Tool · Полтавська громада</title>
</svelte:head>

<svelte:window onkeydown={globalKey} />

{#if isPublic}
	{@render children()}
{:else if auth.user}
	<a class="skip no-print" href="#main">Перейти до змісту</a>

	<!-- Телефон: верхня смуга -->
	<header class="mbar no-print">
		<button type="button" class="mbar-btn" aria-label="Меню" aria-expanded={drawer} aria-controls="side" onclick={() => (drawer = !drawer)}>
			<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
		</button>
		<span class="mbar-title">{current?.label ?? 'Insight Tool'}</span>
		<button type="button" class="mbar-btn" aria-label="Пошук будівлі" onclick={() => (paletteOpen = true)}>
			<Icon name="search" size={18} />
		</button>
	</header>

	{#if drawer}
		<div class="scrim no-print" onclick={() => (drawer = false)} aria-hidden="true"></div>
	{/if}

	<aside id="side" class="side no-print" class:open={drawer} aria-label="Навігація">
		<a class="brand" href="/dashboard">
			<span class="logo" aria-hidden="true"><Icon name="bolt" size={16} stroke={2.2} /></span>
			<span class="brand-txt">
				<span class="brand-name">Insight Tool</span>
				<span class="brand-sub">Полтавська громада</span>
			</span>
		</a>

		<button type="button" class="search" onclick={() => (paletteOpen = true)} onpointerenter={warmPalette} onfocus={warmPalette} aria-keyshortcuts="Control+K">
			<Icon name="search" size={16} />
			<span>Знайти будівлю</span>
			<kbd>Ctrl K</kbd>
		</button>

		<nav class="nav" aria-label="Розділи" use:navIndicator>
			{#each groups as g (g.title)}
				<p class="g-title">{g.title}</p>
				<ul>
					{#each g.items as i (i.href)}
						<li>
							<a href={i.href} aria-current={isActive(i.href) ? 'page' : undefined}>
								<Icon name={i.icon} size={17} />
								<span>{i.label}</span>
							</a>
						</li>
					{/each}
				</ul>
			{/each}
		</nav>

		<FreshnessBadge />

		<div class="me">
			<span class="avatar" aria-hidden="true">{initials(auth.user.full_name)}</span>
			<span class="me-txt">
				<span class="me-name">{auth.user.full_name}</span>
				{#if roleText !== auth.user.full_name}<span class="me-role">{roleText}</span>{/if}
			</span>
			<button type="button" class="out" onclick={signOut} title="Вийти" aria-label="Вийти">
				<Icon name="logout" size={17} />
			</button>
		</div>
	</aside>

	{#if paletteMod}
		{#await paletteMod then { default: CommandPalette }}
			<CommandPalette bind:open={paletteOpen} />
		{/await}
	{/if}
	<div class="nav-progress no-print" class:on={navBar === 'on'} class:done={navBar === 'done'} aria-hidden="true"></div>

	<div class="shell">
		<main id="main" class="wrap" tabindex="-1" use:autoReveal>
			{@render children()}
		</main>
	</div>
{/if}

<style>
	:global(:root) {
		--side-w: 248px;
		--side-offset: var(--side-w);
		--header-h: 0px;
		--tabbar-h: 0px;
	}
	:global(.wrap) {
		max-width: 1440px;
		margin: 0 auto;
		padding: 0 calc(var(--gutter, 2rem) + var(--safe-r, 0px)) 0 calc(var(--gutter, 2rem) + var(--safe-l, 0px));
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

	/* ---------- бокове меню ---------- */
	.side {
		position: fixed;
		inset: 0 auto 0 0;
		width: var(--side-w);
		display: flex;
		flex-direction: column;
		background: #fff;
		border-right: 1px solid var(--card-line);
		z-index: 40;
		padding: 1rem 0.75rem 0.75rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding: 0.25rem 0.5rem 1rem;
		text-decoration: none;
		color: var(--ink);
		border-bottom: 1px solid var(--line-soft);
		margin-bottom: 0.75rem;
	}
	.logo {
		width: 30px;
		height: 30px;
		border-radius: var(--radius);
		background: var(--navy);
		color: var(--sun);
		display: grid;
		place-items: center;
		flex: none;
	}
	.brand-txt {
		display: flex;
		flex-direction: column;
		line-height: 1.2;
	}
	.brand-name {
		font-weight: 700;
		font-size: 1rem;
	}
	.brand-sub {
		font-size: 0.78rem;
		color: var(--muted);
	}
	.search {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.45rem 0.6rem;
		margin-bottom: 0.5rem;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		background: var(--surface-2);
		color: var(--muted);
		font: inherit;
		font-size: 0.875rem;
		cursor: pointer;
		text-align: left;
	}
	.search span {
		flex: 1;
	}
	.search:hover {
		border-color: var(--line-strong);
	}
	kbd {
		font: inherit;
		font-size: 0.7rem;
		padding: 0.05rem 0.35rem;
		border: 1px solid var(--line);
		border-radius: var(--radius-sm);
		background: #fff;
	}
	.nav {
		flex: 1;
		overflow-y: auto;
		margin: 0 -0.25rem;
		padding: 0 0.25rem;
	}
	.g-title {
		margin: 1rem 0.5rem 0.3rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: #7a8696;
	}
	.nav ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.nav a {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.45rem 0.6rem;
		border-radius: var(--radius);
		color: var(--text-2);
		text-decoration: none;
		font-size: 0.92rem;
		font-weight: 500;
		position: relative;
	}
	.nav a:hover {
		background: var(--surface-2);
		color: var(--ink);
	}
	.nav a[aria-current='page'] {
		background: var(--accent-soft);
		color: var(--accent-dark);
		font-weight: 600;
	}
	.nav a[aria-current='page']::before {
		content: '';
		position: absolute;
		left: -0.25rem;
		top: 0.4rem;
		bottom: 0.4rem;
		width: 3px;
		border-radius: var(--r-sm);
		background: var(--accent);
	}
	.me {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.75rem 0.4rem 0.1rem;
		border-top: 1px solid var(--line-soft);
	}
	.avatar {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: var(--neutral-soft);
		color: var(--navy);
		font-weight: 700;
		font-size: 0.75rem;
		display: grid;
		place-items: center;
		flex: none;
	}
	.me-txt {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		line-height: 1.25;
	}
	.me-name {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--ink);
	}
	.me-role {
		font-size: 0.75rem;
		color: var(--muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.out {
		border: 1px solid transparent;
		background: none;
		color: var(--muted);
		border-radius: var(--radius);
		padding: 0.35rem;
		cursor: pointer;
		display: grid;
		place-items: center;
	}
	.out:hover {
		border-color: var(--line);
		color: var(--bad);
	}

	/* ---------- вміст ---------- */
	.shell {
		margin-left: var(--side-w);
		min-height: 100vh;
		overflow-x: clip;
	}
	main {
		padding-top: 1.75rem;
		padding-bottom: 3rem;
		view-transition-name: page;
	}
	main:focus {
		outline: none;
	}

	/* ---------- телефон / вузький екран ---------- */
	.mbar,
	.scrim {
		display: none;
	}
	@media (max-width: 1024px) {
		:global(:root) {
			--header-h: 52px;
			--side-offset: 0px;
		}
		.mbar {
			position: sticky;
			top: 0;
			z-index: 30;
			display: flex;
			align-items: center;
			gap: 0.5rem;
			height: 52px;
			padding: 0 0.5rem;
			background: #fff;
			border-bottom: 1px solid var(--card-line);
		}
		.mbar-title {
			flex: 1;
			font-weight: 600;
			color: var(--ink);
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.mbar-btn {
			width: 40px;
			height: 40px;
			display: grid;
			place-items: center;
			border: 0;
			background: none;
			color: var(--ink);
			border-radius: var(--radius);
			cursor: pointer;
		}
		.mbar-btn:hover {
			background: var(--surface-2);
		}
		/* Меню: відкриття — 260 мс --ease-emph (виїжджає з-за краю), закриття — 160 мс --ease-in */
		.side {
			transform: translateX(-100%);
			transition: transform 320ms var(--ease-in);
			box-shadow: none;
		}
		.side.open {
			transition: transform 520ms var(--ease-emph);
		}
		.side.open {
			transform: none;
			box-shadow: 0 0 0 100vmax rgba(10, 31, 56, 0);
		}
		.scrim {
			display: block;
			position: fixed;
			inset: 0;
			background: rgba(10, 31, 56, 0.35);
			z-index: 35;
			animation: scrim-in var(--dur-base) var(--ease-out);
		}
		@keyframes scrim-in {
			from {
				opacity: 0;
			}
		}
		.shell {
			margin-left: 0;
		}
		main {
			padding-top: 1.25rem;
		}
	}
	@media (max-width: 700px) {
		:global(.wrap) {
			--gutter: 1rem;
		}
	}
	@media print {
		.shell {
			margin-left: 0;
		}
		main {
			view-transition-name: none;
			padding-top: 0;
		}
	}
</style>
