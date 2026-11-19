<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { goto, afterNavigate, onNavigate } from '$app/navigation';
	import { tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import { auth, logout, initials, safeNext } from '#lib/auth.svelte.ts';
	import { isReduced, scaleIn, cubicOut } from '#lib/motion.ts';
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

	// --- Плавні переходи між сторінками (View Transitions API). Шапка лишається на місці. ---
	onNavigate((nav) => {
		if (typeof document === 'undefined' || !('startViewTransition' in document) || isReduced()) return;
		// Зміна лише фільтрів / вкладок (той самий шлях) — без переходу, щоб не мерехтіло
		if (nav.from?.url.pathname === nav.to?.url.pathname) return;
		return new Promise<void>((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await nav.complete;
			});
		});
	});

	type NavItem = { href: string; label: string; icon: 'building' | 'pin' | 'battery' | 'sun'; map?: boolean };
	// Основні сценарії продукту
	const primary: NavItem[] = [
		{ href: '/', label: 'Об’єкти', icon: 'building' },
		{ href: '/map', label: 'Мапа', icon: 'pin', map: true },
		{ href: '/independence', label: 'Енергонезалежність', icon: 'battery' },
		{ href: '/solar', label: 'Де ставити СЕС', icon: 'sun' }
	];

	// Аналітика на реальних річних даних UMUNI
	const analytics = [
		{ href: '/overview', label: 'Споживання електроенергії', hint: 'Скільки й хто споживає' },
		{ href: '/rating', label: 'Рейтинг будівель', hint: 'Хто витрачає забагато на 1 м²' },
		{ href: '/defects', label: 'Якість даних', hint: 'Помилки й пропуски в UMUNI' },
		{ href: '/upload', label: 'Оновити дані', hint: 'Завантажити новий файл' }
	];

	function isActive(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/' || p.startsWith('/object/');
		if (href === '/rating' && p.startsWith('/building/')) return true;
		return p === href || p.startsWith(href + '/');
	}
	const analyticsActive = $derived(analytics.find((a) => isActive(a.href)) ?? null);

	// --- Ковзна смужка під активним пунктом меню ---
	let navEl = $state<HTMLElement>();
	let ind = $state({ x: 0, w: 0, show: false, ready: false });

	function measure() {
		if (!navEl) return;
		const cur = navEl.querySelector<HTMLElement>('[data-nav][aria-current="page"], .dd.has-active .dd-btn');
		if (!cur || cur.offsetParent === null) {
			ind.show = false;
			return;
		}
		const nb = navEl.getBoundingClientRect();
		const cb = cur.getBoundingClientRect();
		ind.x = cb.left - nb.left + 10;
		ind.w = Math.max(0, cb.width - 20);
		ind.show = true;
		if (!ind.ready) requestAnimationFrame(() => (ind.ready = true));
	}
	$effect(() => {
		void page.url.pathname;
		void analyticsActive;
		if (!navEl) return;
		tick().then(measure);
		const ro = new ResizeObserver(() => measure());
		ro.observe(navEl);
		return () => ro.disconnect();
	});

	// --- Меню «Аналітика» ---
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

	// --- «Як користуватися»: міні-тур із 3 кроків (перший візит + кнопка «?») ---
	const TOUR_KEY = 'energo.tour.v1';
	const steps = [
		{
			title: 'Що це за сервіс',
			text: 'Карта енергетики будівель Полтавської громади: шкіл, садочків, лікарень, адмінбудівель. Видно, скільки електрики споживає кожна з них.',
			hl: ['/']
		},
		{
			title: 'Знайдіть свою будівлю',
			text: 'Відкрийте «Об’єкти» чи «Мапу» — або просто почніть пошук за назвою чи адресою.',
			hl: ['/', '/map', 'search']
		},
		{
			title: 'Плануйте незалежність',
			text: '«Енергонезалежність» покаже, скільки годин будівля протримається без світла. «Де ставити СЕС» — де сонячні панелі окупляться найшвидше.',
			hl: ['/independence', '/solar']
		}
	];
	let helpOpen = $state(false);
	let step = $state(0);
	let dir = $state(1);
	let helpBtn = $state<HTMLButtonElement>();
	const hl = $derived(helpOpen ? steps[step].hl : []);

	function openHelp() {
		step = 0;
		dir = 1;
		helpOpen = true;
	}
	function closeHelp(focusBtn = false) {
		helpOpen = false;
		try {
			localStorage.setItem(TOUR_KEY, '1');
		} catch {
			/* сховище недоступне */
		}
		if (focusBtn) helpBtn?.focus();
	}
	function go(d: number) {
		dir = d;
		const n = step + d;
		if (n >= steps.length) closeHelp(true);
		else step = Math.max(0, n);
	}
	// Перший візит після входу — показуємо тур самі (раз)
	$effect(() => {
		if (!auth.user || isLogin) return;
		let seen = true;
		try {
			seen = localStorage.getItem(TOUR_KEY) === '1';
		} catch {
			/* приватний режим */
		}
		if (seen) return;
		const t = setTimeout(openHelp, 900);
		return () => clearTimeout(t);
	});

	afterNavigate(() => {
		menuOpen = false;
		navOpen = false;
	});

	function globalKey(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K' || e.code === 'KeyK')) {
			if (!auth.user || isLogin) return;
			e.preventDefault();
			paletteOpen = !paletteOpen;
		} else if (e.key === 'Escape') {
			if (helpOpen) closeHelp(true);
			if (menuOpen || navOpen) {
				menuOpen = false;
				navOpen = false;
			}
		}
	}
	function globalDown(e: PointerEvent) {
		const t = e.target as HTMLElement;
		if (menuOpen && !t.closest?.('.dd')) menuOpen = false;
		if (helpOpen && !t.closest?.('.help-wrap')) closeHelp();
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>City Insight Map · Енергія</title>
</svelte:head>

<svelte:window onkeydown={globalKey} onpointerdown={globalDown} />

{#snippet mapIcon()}
	<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
		<path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4Z" /><path d="M9 4v14M15 6v14" />
	</svg>
{/snippet}

{#if isLogin}
	{@render children()}
{:else if auth.user}
	<a class="skip no-print" href="#main">Перейти до змісту</a>

	<header class="site-header no-print">
		<div class="hdr-bg" aria-hidden="true"></div>
		<div class="wrap head-row">
			<a class="brand" href="/">
				<span class="logo" aria-hidden="true"><Icon name="bolt" size={20} stroke={2.2} /></span>
				<span class="brand-txt">
					<span class="brand-name">City Insight Map <span class="brand-dot">·</span> Енергія</span>
					<span class="brand-sub">Полтавська громада</span>
				</span>
			</a>

			<button
				type="button"
				class="search-btn"
				class:tour-hl={hl.includes('search')}
				onclick={() => (paletteOpen = true)}
				aria-keyshortcuts="Control+K"
				aria-label="Пошук будівлі (Ctrl+K)"
			>
				<Icon name="search" size={18} />
				<span class="search-txt">Знайти будівлю…</span>
				<kbd class="search-kbd" aria-hidden="true">Ctrl K</kbd>
			</button>

			<div class="help-wrap">
				<button
					bind:this={helpBtn}
					type="button"
					class="help-btn"
					aria-expanded={helpOpen}
					aria-controls="help-pop"
					aria-label="Як користуватися"
					title="Як користуватися"
					onclick={() => (helpOpen ? closeHelp() : openHelp())}
				>
					<span aria-hidden="true">?</span>
				</button>
				{#if helpOpen}
					<div
						id="help-pop"
						class="help-pop"
						role="dialog"
						aria-labelledby="help-title"
						transition:scaleIn={{ start: 0.94, duration: 220 }}
					>
						<div class="help-head">
							<span class="eyebrow-dk" id="help-title">Як користуватися · крок {step + 1} з {steps.length}</span>
							<button type="button" class="help-x" aria-label="Закрити підказку" onclick={() => closeHelp(true)}>
								<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="m3 3 8 8m0-8-8 8" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" /></svg>
							</button>
						</div>
						<div class="help-stage" aria-live="polite">
							{#key step}
								<div
									class="help-step"
									in:fly={{ x: isReduced() ? 0 : 28 * dir, duration: isReduced() ? 0 : 320, delay: isReduced() ? 0 : 60, easing: cubicOut }}
									out:fly={{ x: isReduced() ? 0 : -20 * dir, duration: isReduced() ? 0 : 160 }}
								>
									<span class="help-num" aria-hidden="true">{step + 1}</span>
									<div>
										<h2 class="help-title">{steps[step].title}</h2>
										<p class="help-text">{steps[step].text}</p>
									</div>
								</div>
							{/key}
						</div>
						{#if step === steps.length - 1}
							<p class="help-note"><span class="demo-mini">ДЕМО</span> — так позначено змодельовані дані.</p>
						{/if}
						<div class="help-foot">
							<span class="dots" aria-hidden="true">
								{#each steps as _, i (i)}<span class:on={i === step}></span>{/each}
							</span>
							{#if step > 0}
								<button type="button" class="hbtn ghost" onclick={() => go(-1)}>Назад</button>
							{/if}
							<button type="button" class="hbtn" onclick={() => go(1)}>
								{step === steps.length - 1 ? 'Зрозуміло' : 'Далі'}
							</button>
						</div>
					</div>
				{/if}
			</div>

			<div class="user">
				<span class="avatar" aria-hidden="true" title="{auth.user.full_name} · {auth.user.position}">{initials(auth.user.full_name)}</span>
				<span class="who">
					<span class="user-name">{auth.user.full_name}</span>
					<span class="user-role">{auth.user.position}</span>
				</span>
				<button type="button" class="out" onclick={logout} title="Вийти">
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
				<span class="burger-ico" class:x={navOpen} aria-hidden="true"><span></span><span></span><span></span></span>
				Меню
			</button>
		</div>

		<nav id="main-nav" class="wrap main-nav" class:open={navOpen} aria-label="Основне меню" bind:this={navEl}>
			<ul class="primary">
				{#each primary as item (item.href)}
					<li>
						<a
							href={item.href}
							data-nav
							class:tour-hl={hl.includes(item.href)}
							aria-current={isActive(item.href) ? 'page' : undefined}
						>
							{#if item.map}{@render mapIcon()}{:else}<Icon name={item.icon} size={18} />{/if}
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

			<span
				class="nav-ind"
				class:show={ind.show}
				class:ready={ind.ready}
				style:transform="translateX({ind.x}px)"
				style:width="{ind.w}px"
				aria-hidden="true"
			></span>
		</nav>
	</header>

	<CommandPalette bind:open={paletteOpen} />

	<main id="main" class="wrap" tabindex="-1">
		{@render children()}
	</main>

	<footer class="site-footer">
		<div class="wrap foot-row">
			<p>
				Будівлі й річне споживання — реальні дані <Term key="UMUNI" />. Станції, телеметрія й ліміти
				позначені <Term key="ДЕМО-ДАНІ" />. Аналітична оцінка, не офіційний енергосертифікат.
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
		border-radius: 8px;
	}
	.skip:focus {
		left: 0.5rem;
	}

	/* --- Шапка --- */
	.site-header {
		position: relative;
		z-index: 20;
		color: #fff;
		background: linear-gradient(180deg, #10325a 0%, #0c2846 100%);
		box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset, 0 10px 30px -18px rgba(8, 20, 38, 0.6);
		view-transition-name: site-header;
	}
	.hdr-bg {
		position: absolute;
		inset: 0;
		overflow: hidden;
		pointer-events: none;
		background:
			radial-gradient(700px 220px at 88% -60px, rgba(245, 165, 36, 0.22), transparent 70%),
			radial-gradient(500px 200px at 12% 140%, rgba(80, 150, 230, 0.16), transparent 70%);
	}
	/* Ледь помітна «міська сітка» */
	.hdr-bg::after {
		content: '';
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
			linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
		background-size: 32px 32px;
		mask-image: linear-gradient(90deg, transparent, #000 30%, #000 70%, transparent);
	}
	.site-header :global(:focus-visible) {
		outline-color: var(--focus);
		box-shadow: 0 0 0 5px #0c2846;
	}
	.head-row {
		position: relative;
		display: flex;
		align-items: center;
		gap: 1rem 1.25rem;
		padding-top: 0.85rem;
		padding-bottom: 0.6rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		color: #fff;
		text-decoration: none;
		min-width: 0;
	}
	.brand:hover {
		color: #fff;
		text-decoration: none;
	}
	.brand:hover .logo {
		transform: rotate(-8deg) scale(1.06);
	}
	.logo {
		display: grid;
		place-items: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 12px;
		background: linear-gradient(145deg, #ffd978, #f5a524 60%, #e88f05);
		color: #0f2f52;
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.5),
			0 6px 18px -6px rgba(245, 165, 36, 0.7);
		flex: none;
		transition: transform var(--dur-slow) var(--ease-spring);
	}
	.brand-txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.brand-name {
		font-family: var(--font-display);
		font-size: 1.15rem;
		font-weight: 700;
		letter-spacing: -0.005em;
		white-space: nowrap;
		line-height: 1.2;
	}
	.brand-dot {
		color: var(--sun);
	}
	.brand-sub {
		font-size: 0.8125rem;
		color: #a9bdd6;
		line-height: 1.3;
	}
	.search-btn {
		margin-left: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		min-height: 42px;
		min-width: 16rem;
		padding: 0.4rem 0.5rem 0.4rem 0.85rem;
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.16);
		background: rgba(255, 255, 255, 0.07);
		color: #dfe7f1;
		font: inherit;
		font-size: 0.95rem;
		cursor: pointer;
		text-align: left;
		transition:
			background var(--dur-fast),
			border-color var(--dur-fast),
			box-shadow var(--dur-base) var(--ease-out);
	}
	.search-btn:hover {
		background: rgba(255, 255, 255, 0.12);
		border-color: rgba(255, 255, 255, 0.34);
		color: #fff;
		box-shadow: 0 6px 18px -10px rgba(0, 0, 0, 0.5);
	}
	.search-txt {
		flex: 1;
		white-space: nowrap;
	}
	.search-kbd {
		font: inherit;
		font-size: 0.72rem;
		padding: 0.12rem 0.45rem;
		border-radius: 6px;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.2);
		color: #c9d6e6;
		white-space: nowrap;
	}

	/* --- Кнопка «?» і тур --- */
	.help-wrap {
		position: relative;
		flex: none;
	}
	.help-btn {
		display: grid;
		place-items: center;
		width: 42px;
		height: 42px;
		border-radius: 50%;
		border: 1px solid rgba(255, 255, 255, 0.22);
		background: rgba(255, 255, 255, 0.06);
		color: #fff;
		font: inherit;
		font-weight: 700;
		font-size: 1.1rem;
		cursor: pointer;
		transition:
			background var(--dur-fast),
			border-color var(--dur-fast),
			transform var(--dur-base) var(--ease-spring);
	}
	.help-btn:hover {
		background: rgba(245, 165, 36, 0.18);
		border-color: rgba(255, 213, 107, 0.7);
		transform: scale(1.06);
	}
	.help-btn[aria-expanded='true'] {
		background: var(--sun);
		border-color: var(--sun);
		color: #0f2f52;
	}
	.help-pop {
		position: absolute;
		top: calc(100% + 12px);
		right: -0.5rem;
		width: min(25rem, calc(100vw - 2rem));
		padding: 1.1rem 1.2rem 1rem;
		border-radius: 18px;
		background: #fff;
		color: var(--text);
		border: 1px solid var(--card-line);
		box-shadow:
			0 30px 60px -20px rgba(8, 20, 38, 0.55),
			0 0 0 1px rgba(8, 20, 38, 0.04);
		transform-origin: calc(100% - 1.75rem) -8px;
		z-index: 40;
	}
	.help-pop::before {
		content: '';
		position: absolute;
		top: -7px;
		right: 1.35rem;
		width: 14px;
		height: 14px;
		background: #fff;
		border-left: 1px solid var(--card-line);
		border-top: 1px solid var(--card-line);
		transform: rotate(45deg);
	}
	.help-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 0.4rem;
	}
	.eyebrow-dk {
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--sun-ink);
	}
	.help-x {
		display: grid;
		place-items: center;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		border: 0;
		background: var(--neutral-soft);
		color: var(--text-2);
		cursor: pointer;
		transition: background var(--dur-fast);
	}
	.help-x:hover {
		background: #e1e7ef;
	}
	.help-stage {
		display: grid;
		min-height: 8.2rem;
		overflow: hidden;
	}
	.help-step {
		grid-area: 1 / 1;
		display: flex;
		gap: 0.9rem;
		align-items: flex-start;
		padding-top: 0.35rem;
	}
	.help-num {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		flex: none;
		border-radius: 12px;
		background: linear-gradient(145deg, #163d68, #0f2f52);
		color: #ffd56b;
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 1.15rem;
	}
	.help-title {
		font-size: 1.1rem;
		margin: 0.1rem 0 0.3rem;
	}
	.help-text {
		margin: 0;
		color: var(--text-2);
		line-height: 1.5;
	}
	.help-note {
		margin: 0.6rem 0 0;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.demo-mini {
		display: inline-block;
		padding: 0 0.4rem;
		border-radius: 999px;
		font-size: 0.6875rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--sun-ink);
		background: var(--sun-soft);
		border: 1px dashed #d08a1c;
	}
	.help-foot {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.9rem;
	}
	.dots {
		display: inline-flex;
		gap: 6px;
		margin-right: auto;
	}
	.dots span {
		width: 7px;
		height: 7px;
		border-radius: 999px;
		background: #cfd8e3;
		transition:
			width var(--dur-base) var(--ease-out),
			background var(--dur-base);
	}
	.dots span.on {
		width: 22px;
		background: var(--sun);
	}
	.hbtn {
		min-height: 40px;
		padding: 0.4rem 1.1rem;
		border-radius: 11px;
		border: 1px solid var(--navy);
		background: var(--navy);
		color: #fff;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		transition:
			background var(--dur-fast),
			transform var(--dur-base) var(--ease-out);
	}
	.hbtn:hover {
		background: var(--navy-3);
	}
	.hbtn:active {
		transform: scale(0.97);
	}
	.hbtn.ghost {
		background: transparent;
		color: var(--navy);
		border-color: var(--line);
	}
	.hbtn.ghost:hover {
		background: var(--neutral-soft);
	}
	/* Підсвічування пункту меню, про який розповідає тур */
	.tour-hl {
		position: relative;
		color: #fff !important;
		background: rgba(245, 165, 36, 0.16) !important;
		box-shadow: 0 0 0 2px rgba(255, 213, 107, 0.85);
		border-radius: 10px !important;
	}
	@media (prefers-reduced-motion: no-preference) {
		.tour-hl {
			animation: tour-pulse 1.6s var(--ease-in-out) infinite;
		}
		@keyframes tour-pulse {
			50% {
				box-shadow:
					0 0 0 2px rgba(255, 213, 107, 0.85),
					0 0 0 7px rgba(245, 165, 36, 0.18);
			}
		}
	}

	/* --- Користувач --- */
	.user {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		min-width: 0;
		padding-left: 1.1rem;
		border-left: 1px solid rgba(255, 255, 255, 0.12);
	}
	.avatar {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		border-radius: 50%;
		background: linear-gradient(145deg, #2a5a8e, #1b4271);
		box-shadow: 0 0 0 2px rgba(255, 213, 107, 0.65);
		font-weight: 700;
		font-size: 0.875rem;
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
		font-size: 0.95rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 14rem;
	}
	.user-role {
		font-size: 0.78rem;
		color: #a9bdd6;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 14rem;
	}
	.out,
	.burger {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.45rem 0.8rem;
		border-radius: 11px;
		border: 1px solid rgba(255, 255, 255, 0.22);
		background: transparent;
		color: #fff;
		font: inherit;
		font-weight: 600;
		font-size: 0.9rem;
		cursor: pointer;
		min-height: 42px;
		flex: none;
		transition:
			background var(--dur-fast),
			border-color var(--dur-fast);
	}
	.out:hover,
	.burger:hover {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.5);
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
		transition:
			transform var(--dur-base) var(--ease-out),
			opacity var(--dur-fast);
	}
	.burger-ico.x span:nth-child(1) {
		transform: translateY(5px) rotate(45deg);
	}
	.burger-ico.x span:nth-child(2) {
		opacity: 0;
	}
	.burger-ico.x span:nth-child(3) {
		transform: translateY(-5px) rotate(-45deg);
	}

	/* --- Навігація --- */
	.main-nav {
		position: relative;
		display: flex;
		align-items: center;
		gap: 0 0.4rem;
		padding-bottom: 0.15rem;
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
		gap: 0.5rem;
		padding: 0.7rem 0.95rem 0.85rem;
		color: #c3d1e2;
		text-decoration: none;
		font: inherit;
		font-weight: 600;
		font-size: 1rem;
		border: 0;
		border-radius: 10px 10px 0 0;
		background: none;
		cursor: pointer;
		white-space: nowrap;
		transition:
			color var(--dur-fast),
			background var(--dur-fast);
	}
	.primary a :global(.icon),
	.dd-btn :global(.icon) {
		opacity: 0.8;
		transition:
			opacity var(--dur-fast),
			transform var(--dur-base) var(--ease-spring);
	}
	.primary a:hover,
	.dd-btn:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.06);
		text-decoration: none;
	}
	.primary a:hover :global(.icon),
	.dd-btn:hover :global(.icon) {
		opacity: 1;
		transform: translateY(-1px) scale(1.08);
	}
	.primary a[aria-current='page'],
	.dd.has-active .dd-btn {
		color: #fff;
	}
	.primary a[aria-current='page'] :global(.icon),
	.dd.has-active .dd-btn :global(.icon) {
		opacity: 1;
		color: #ffd56b;
	}
	/* Ковзна смужка під активним пунктом */
	.nav-ind {
		position: absolute;
		left: 0;
		bottom: 0;
		height: 3px;
		border-radius: 3px 3px 0 0;
		background: linear-gradient(90deg, #ffd56b, var(--sun));
		box-shadow: 0 -2px 12px rgba(245, 165, 36, 0.55);
		opacity: 0;
		pointer-events: none;
	}
	.nav-ind.show {
		opacity: 1;
	}
	.nav-ind.ready {
		transition:
			transform 420ms var(--ease-out),
			width 420ms var(--ease-out),
			opacity var(--dur-base);
	}
	.divider {
		width: 1px;
		height: 1.5rem;
		background: rgba(255, 255, 255, 0.16);
		margin: 0 0.3rem;
	}
	.dd {
		position: relative;
	}
	.dd-cur {
		font-weight: 500;
		color: #ffd56b;
	}
	.chev {
		transition: transform var(--dur-base) var(--ease-out);
	}
	.dd-btn[aria-expanded='true'] .chev {
		transform: rotate(180deg);
	}
	.dd-mobile-label {
		display: none;
	}
	.dd-menu {
		position: absolute;
		top: calc(100% + 6px);
		left: 0;
		min-width: 20rem;
		padding: 0.4rem;
		background: #fff;
		border-radius: 14px;
		box-shadow: 0 24px 50px -16px rgba(8, 20, 38, 0.5);
		border: 1px solid var(--card-line);
		z-index: 30;
		visibility: hidden;
		opacity: 0;
		transform: translateY(-6px) scale(0.98);
		transform-origin: 20% 0;
		transition:
			opacity var(--dur-fast) var(--ease-out),
			transform var(--dur-base) var(--ease-out),
			visibility 0s linear var(--dur-base);
	}
	.dd-menu.open {
		visibility: visible;
		opacity: 1;
		transform: none;
		transition:
			opacity var(--dur-fast) var(--ease-out),
			transform var(--dur-base) var(--ease-out),
			visibility 0s;
	}
	.dd-menu a {
		display: flex;
		flex-direction: column;
		padding: 0.6rem 0.85rem;
		border-radius: 10px;
		color: var(--text);
		text-decoration: none;
		transition: background var(--dur-fast);
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
		view-transition-name: page;
	}
	main:focus {
		outline: none;
	}
	.site-footer {
		border-top: 1px solid var(--line-soft);
		background: rgba(255, 255, 255, 0.7);
		padding: 1.1rem 0;
		font-size: 0.875rem;
		color: var(--text-2);
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

	@media (max-width: 1280px) {
		.who {
			display: none;
		}
		.user {
			padding-left: 0.9rem;
		}
	}
	@media (max-width: 1120px) {
		.primary a,
		.dd-btn {
			padding-left: 0.7rem;
			padding-right: 0.7rem;
			font-size: 0.95rem;
		}
		.dd-cur {
			display: none;
		}
		.search-btn {
			min-width: 12rem;
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
		.search-txt,
		.brand-sub {
			display: none;
		}
		.user {
			border-left: 0;
			padding-left: 0;
		}
		.nav-ind {
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
			animation: nav-drop var(--dur-base) var(--ease-out);
		}
		@keyframes nav-drop {
			from {
				opacity: 0;
				transform: translateY(-6px);
			}
		}
		.primary {
			flex-direction: column;
		}
		.primary a {
			padding-bottom: 0.7rem;
			border-left: 3px solid transparent;
			border-radius: 0 10px 10px 0;
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
			visibility: visible;
			opacity: 1;
			transform: none;
			position: static;
			min-width: 0;
			padding: 0;
			background: none;
			border: 0;
			box-shadow: none;
		}
		.dd-menu a {
			color: #dfe7f1;
			border-radius: 0 10px 10px 0;
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
			gap: 0.5rem;
		}
		.help-pop {
			position: fixed;
			top: 4.5rem;
			left: 1rem;
			right: 1rem;
			width: auto;
		}
		.help-pop::before {
			display: none;
		}
	}
	@media (max-width: 440px) {
		.brand-name {
			white-space: normal;
			font-size: 0.95rem;
		}
		.avatar {
			display: none;
		}
	}
	@media print {
		.site-footer {
			border-top: 1px solid #999;
		}
		main {
			view-transition-name: none;
		}
	}
</style>
