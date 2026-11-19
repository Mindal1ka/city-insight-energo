<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { goto, afterNavigate, onNavigate } from '$app/navigation';
	import { tick } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { auth, logout, initials, verifySession } from '#lib/auth.svelte.ts';
	import { isInternal, canUpload, roleLabel } from '#lib/roles.ts';
	import { isReduced, scaleIn, cubicOut } from '#lib/motion.ts';
	import Icon from '#lib/Icon.svelte';
	import Term from '#lib/Term.svelte';
	import CommandPalette from '#lib/CommandPalette.svelte';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const isLogin = $derived(page.url.pathname === '/login');

	// Без входу — публічний перегляд: сторінки самі вирішують, що показувати
	const chip = $derived(roleLabel(auth.user));
	const loginHref = $derived.by(() => {
		const back = page.url.pathname + page.url.search;
		return '/login' + (back !== '/' && !isLogin ? `?next=${encodeURIComponent(back)}` : '');
	});

	// Збережений токен перевіряємо один раз (прострочений → публічний режим)
	verifySession();

	function signOut() {
		logout();
		closeSheet(false);
		goto('/', { reset: false });
	}

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

	type NavItem = { href: string; label: string; short: string; icon: 'building' | 'gauge' | 'sun'; map?: boolean };
	// Основні розділи (PLAN_v3)
	const primary: NavItem[] = [
		{ href: '/', label: 'Мапа', short: 'Мапа', icon: 'building', map: true },
		{ href: '/dashboard', label: 'Дашборд', short: 'Дашборд', icon: 'gauge' },
		{ href: '/objects', label: 'Об’єкти', short: 'Об’єкти', icon: 'building' },
		{ href: '/energy', label: 'Розподіл', short: 'Розподіл', icon: 'sun' },
		{ href: '/finance', label: 'Фінанси', short: 'Фінанси', icon: 'gauge' }
	];
	const tabs = primary;

	// Аналітика: частина пунктів — лише для службових ролей
	type Analytic = { href: string; label: string; only?: 'internal' | 'upload' };
	const ANALYTICS: Analytic[] = [
		{ href: '/network', label: 'Баланс мережі' },
		{ href: '/report', label: 'Звіт за місяць' },
		{ href: '/appeals', label: 'Звернення', only: 'internal' },
		{ href: '/overview', label: 'Споживання' },
		{ href: '/rating', label: 'Індекс ефективності' },
		{ href: '/upload', label: 'Оновити дані', only: 'upload' }
	];
	const analytics = $derived(
		ANALYTICS.filter((a) =>
			!a.only ? true : a.only === 'internal' ? isInternal(auth.user) : canUpload(auth.user)
		)
	);

	function isActive(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/' || p === '/map';
		if (href === '/objects') return p.startsWith('/objects') || p.startsWith('/object/');
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

	// --- Мобільне меню (769–899 px: випадне під шапкою) ---
	let navOpen = $state(false);
	let burgerBtn = $state<HTMLButtonElement>();

	// --- Телефон (≤ 768 px): нижня панель вкладок + аркуш «Меню» ---
	let sheetOpen = $state(false);
	let sheetEl = $state<HTMLDivElement>();
	let sheetTrigger: HTMLElement | null = null;
	let dragY = $state(0);
	let dragging = $state(false);
	const tabIndex = $derived.by(() => {
		if (sheetOpen || analyticsActive) return 4;
		return tabs.findIndex((t) => isActive(t.href));
	});

	async function openSheet(e?: Event) {
		sheetTrigger = (e?.currentTarget as HTMLElement | null) ?? (document.activeElement as HTMLElement | null);
		sheetOpen = true;
		dragY = 0;
		await tick();
		sheetEl?.querySelector<HTMLElement>('.sheet-close')?.focus();
	}
	function closeSheet(restore = true) {
		if (!sheetOpen) return;
		sheetOpen = false;
		dragY = 0;
		if (restore) sheetTrigger?.focus?.();
	}
	function sheetKey(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			e.stopPropagation();
			closeSheet();
		} else if (e.key === 'Tab' && sheetEl) {
			// Фокус не виходить за межі аркуша
			const f = [...sheetEl.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')];
			if (!f.length) return;
			const first = f[0];
			const last = f[f.length - 1];
			if (e.shiftKey && (document.activeElement === first || document.activeElement === sheetEl)) {
				e.preventDefault();
				last.focus();
			} else if (!e.shiftKey && document.activeElement === last) {
				e.preventDefault();
				first.focus();
			}
		}
	}
	// Свайп униз за «ручку» чи заголовок закриває аркуш
	let startY = 0;
	function dragStart(e: PointerEvent) {
		if ((e.target as HTMLElement).closest('button')) return;
		startY = e.clientY;
		dragging = true;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
	}
	function dragMove(e: PointerEvent) {
		if (dragging) dragY = Math.max(0, e.clientY - startY);
	}
	function dragEnd() {
		if (!dragging) return;
		dragging = false;
		if (dragY > 90) closeSheet();
		else dragY = 0;
	}
	// Поки аркуш відкритий — сторінка під ним не прокручується
	$effect(() => {
		if (!sheetOpen) return;
		const el = document.documentElement;
		const prev = el.style.overflow;
		el.style.overflow = 'hidden';
		return () => {
			el.style.overflow = prev;
		};
	});
	function helpFromSheet() {
		closeSheet(false);
		openHelp();
	}

	// --- Глобальний пошук ---
	let paletteOpen = $state(false);

	// --- «Як користуватися»: міні-тур із 3 кроків (лише за кнопкою «?») ---
	const steps = [
		{
			title: 'Мапа',
			text: 'Колір точки — наскільки ефективно працює СЕС об’єкта.',
			hl: ['/']
		},
		{
			title: 'Дашборд і об’єкти',
			text: 'Фільтри за класом, типом закладу й періодом. Пошук — Ctrl K.',
			hl: ['/dashboard', '/objects', 'search']
		},
		{
			title: 'Нові СЕС',
			text: 'Де сонячні панелі окупляться найшвидше.',
			hl: ['/solar']
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
		if (focusBtn) helpBtn?.focus();
	}
	function go(d: number) {
		dir = d;
		const n = step + d;
		if (n >= steps.length) closeHelp(true);
		else step = Math.max(0, n);
	}
	afterNavigate(() => {
		menuOpen = false;
		navOpen = false;
		sheetOpen = false;
	});

	function globalKey(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K' || e.code === 'KeyK')) {
			if (isLogin) return;
			e.preventDefault();
			paletteOpen = !paletteOpen;
		} else if (e.key === 'Escape') {
			if (sheetOpen) closeSheet();
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
		if (helpOpen && !t.closest?.('.help-wrap') && !t.closest?.('.sheet')) closeHelp();
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
{:else}
	<a class="skip no-print" href="#main">Перейти до змісту</a>

	<header class="site-header no-print">
		<div class="hdr-bg" aria-hidden="true"></div>
		<div class="wrap head-row">
			<a class="brand" href="/">
				<span class="logo" aria-hidden="true"><Icon name="bolt" size={20} stroke={2.2} /></span>
				<span class="brand-txt">
					<span class="brand-name">City Insight Map <span class="brand-dot">·</span> Енергія</span>
					<span class="brand-short" aria-hidden="true">Енергія</span>
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
				{#if auth.user}
					<span class="avatar" aria-hidden="true" title="{auth.user.full_name} · {auth.user.position}">{initials(auth.user.full_name)}</span>
					<span class="who">
						<span class="user-name" title={auth.user.position}>{auth.user.full_name}</span>
						<span class="role-chip">{chip}</span>
					</span>
					<button type="button" class="out" onclick={signOut} title="Вийти" aria-label="Вийти">
						<Icon name="logout" size={18} /> <span class="out-txt">Вийти</span>
					</button>
				{:else}
					<span class="role-chip pub"><Icon name="users" size={14} /> {chip}</span>
					<a class="in-btn" href={loginHref}><Icon name="lock" size={16} /> Увійти</a>
				{/if}
			</div>

			{#if !auth.user}
				<a class="in-mob" href={loginHref} aria-label="Увійти">Увійти</a>
			{/if}
			<button
				type="button"
				class="me-btn"
				aria-haspopup="dialog"
				aria-expanded={sheetOpen}
				aria-controls="m-sheet"
				aria-label={auth.user ? `Профіль і меню: ${auth.user.full_name}` : 'Меню'}
				onclick={openSheet}
			>
				{#if auth.user}
					<span class="avatar" aria-hidden="true">{initials(auth.user.full_name)}</span>
				{:else}
					<span class="avatar pub" aria-hidden="true"><Icon name="users" size={17} /></span>
				{/if}
			</button>

			<button
				bind:this={burgerBtn}
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

	<!-- Телефон: нижня панель вкладок -->
	<nav class="tabbar no-print" aria-label="Основні розділи">
		<span class="tab-ind" class:show={tabIndex >= 0} style:--i={Math.max(0, tabIndex)} aria-hidden="true"></span>
		{#each tabs as t (t.href)}
			<a
				class="tab"
				href={t.href}
				class:tour-hl={hl.includes(t.href)}
				aria-current={isActive(t.href) && !sheetOpen ? 'page' : undefined}
				aria-label={t.label}
			>
				<span class="tab-ico">{#if t.map}{@render mapIcon()}{:else}<Icon name={t.icon} size={22} />{/if}</span>
				<span class="tab-txt" aria-hidden="true">{t.short}</span>
			</a>
		{/each}
		<button
			type="button"
			class="tab"
			class:on={sheetOpen || !!analyticsActive}
			aria-haspopup="dialog"
			aria-expanded={sheetOpen}
			aria-controls="m-sheet"
			onclick={(e) => (sheetOpen ? closeSheet() : openSheet(e))}
		>
			<span class="tab-ico"><svg class="icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><rect x="4" y="4" width="6.5" height="6.5" rx="1.8" /><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.8" /><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.8" /><circle cx="16.75" cy="16.75" r="3.25" /></svg></span>
			<span class="tab-txt">Меню</span>
		</button>
	</nav>

	{#if sheetOpen}
		<div class="sheet-backdrop no-print" onclick={() => closeSheet()} aria-hidden="true" transition:fade={{ duration: isReduced() ? 0 : 200 }}></div>
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions (Esc і пастка фокусу) -->
		<div
			id="m-sheet"
			class="sheet no-print"
			class:dragging
			role="dialog"
			aria-modal="true"
			aria-labelledby="m-sheet-title"
			tabindex="-1"
			bind:this={sheetEl}
			onkeydown={sheetKey}
			style:transform={dragY ? `translateY(${dragY}px)` : undefined}
			transition:fly={{ y: isReduced() ? 0 : 480, duration: isReduced() ? 0 : 340, easing: cubicOut, opacity: 1 }}
		>
			<!-- svelte-ignore a11y_no_static_element_interactions (свайп униз — дублює кнопку «Закрити») -->
			<div
				class="sheet-top"
				onpointerdown={dragStart}
				onpointermove={dragMove}
				onpointerup={dragEnd}
				onpointercancel={dragEnd}
			>
				<span class="sheet-grab" aria-hidden="true"></span>
				<div class="sheet-head">
					{#if auth.user}
						<span class="avatar lg" aria-hidden="true">{initials(auth.user.full_name)}</span>
						<span class="sheet-who">
							<span class="sheet-name" id="m-sheet-title">{auth.user.full_name}</span>
							<span class="sheet-role">{chip}</span>
						</span>
					{:else}
						<span class="avatar lg pub" aria-hidden="true"><Icon name="users" size={20} /></span>
						<span class="sheet-who">
							<span class="sheet-name" id="m-sheet-title">{chip}</span>
							<span class="sheet-role">Без входу</span>
						</span>
					{/if}
					<button type="button" class="sheet-close" aria-label="Закрити меню" onclick={() => closeSheet()}>
						<svg width="16" height="16" viewBox="0 0 14 14" aria-hidden="true"><path d="m3 3 8 8m0-8-8 8" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" /></svg>
					</button>
				</div>
			</div>

			<div class="sheet-body">
				<p class="sheet-label"><Icon name="chart" size={16} /> Аналітика</p>
				<ul class="sheet-list">
					{#each analytics as item (item.href)}
						<li>
							<a href={item.href} aria-current={isActive(item.href) ? 'page' : undefined}>
								<span class="sl-txt">
									<span class="sl-label">{item.label}</span>
								</span>
								<svg class="sl-chev" width="16" height="16" viewBox="0 0 20 20" aria-hidden="true"><path d="m8 5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
							</a>
						</li>
					{/each}
				</ul>

				<div class="sheet-actions">
					<button type="button" class="sheet-btn" onclick={helpFromSheet}>
						<span class="sb-q" aria-hidden="true">?</span> Як користуватися
					</button>
					{#if auth.user}
						<button type="button" class="sheet-btn out-m" onclick={signOut}>
							<Icon name="logout" size={18} /> Вийти
						</button>
					{:else}
						<a class="sheet-btn in-m" href={loginHref}><Icon name="lock" size={18} /> Увійти</a>
					{/if}
				</div>
			</div>
		</div>
	{/if}

	<main id="main" class="wrap" tabindex="-1">
		{@render children()}
	</main>

	<footer class="site-footer">
		<div class="wrap foot-row">
			<p>
				Дані <Term key="UMUNI" /> · СЕС — <Term key="ДЕМО-ДАНІ">ДЕМО</Term><span class="no-print"> · Poltava Open Data Hackathon</span>
			</p>
		</div>
	</footer>
{/if}

<style>
	:global(.wrap) {
		max-width: 1480px;
		margin: 0 auto;
		padding: 0 calc(var(--gutter, 2rem) + var(--safe-r, 0px)) 0 calc(var(--gutter, 2rem) + var(--safe-l, 0px));
	}
	@media (max-width: 700px) {
		:global(.wrap) {
			--gutter: 1rem;
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
	.role-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		align-self: flex-start;
		margin-top: 0.15rem;
		padding: 0.05rem 0.5rem;
		border-radius: 999px;
		background: rgba(255, 213, 107, 0.16);
		border: 1px solid rgba(255, 213, 107, 0.45);
		color: #ffe3a1;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.01em;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 16rem;
	}
	.role-chip.pub {
		margin-top: 0;
		align-self: center;
		padding: 0.2rem 0.65rem;
		background: rgba(255, 255, 255, 0.08);
		border-color: rgba(255, 255, 255, 0.22);
		color: #dfe7f1;
		font-size: 0.8rem;
	}
	.in-btn,
	.in-mob {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 42px;
		padding: 0.45rem 0.95rem;
		border-radius: 11px;
		border: 1px solid #d98c0b;
		background: linear-gradient(180deg, #ffc54d, var(--sun));
		color: #2a1900;
		font-weight: 700;
		font-size: 0.9rem;
		text-decoration: none;
		white-space: nowrap;
		flex: none;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5), 0 8px 20px -12px rgba(245, 165, 36, 0.9);
		transition:
			transform var(--dur-base) var(--ease-out),
			filter var(--dur-fast);
	}
	.in-btn:hover,
	.in-mob:hover {
		text-decoration: none;
		color: #2a1900;
		filter: brightness(1.05);
		transform: translateY(-1px);
	}
	.in-mob {
		display: none;
	}
	.avatar.pub {
		background: rgba(255, 255, 255, 0.1);
		box-shadow: 0 0 0 1.5px rgba(255, 255, 255, 0.35);
		color: #dfe7f1;
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
	/* ================= Телефон (≤ 768 px): нативний каркас ================= */
	.brand-short,
	.me-btn,
	.tabbar {
		display: none;
	}
	@media (max-width: 768px) {
		.site-header {
			position: sticky;
			top: 0;
			z-index: 30;
			padding-top: var(--safe-t, 0px);
			box-shadow: 0 6px 20px -14px rgba(8, 20, 38, 0.7);
		}
		.hdr-bg::after {
			display: none;
		}
		.head-row {
			height: 56px;
			gap: 0.5rem;
			padding-top: 0;
			padding-bottom: 0;
		}
		.brand {
			gap: 0.6rem;
			margin-right: auto;
		}
		.logo {
			width: 2.1rem;
			height: 2.1rem;
			border-radius: 10px;
		}
		.logo :global(svg) {
			width: 18px;
			height: 18px;
		}
		.brand-name,
		.brand-sub {
			display: none;
		}
		.brand-short {
			display: block;
			font-family: var(--font-display);
			font-weight: 700;
			font-size: 1.15rem;
			letter-spacing: -0.01em;
		}
		.search-btn {
			margin-left: 0;
			width: 44px;
			min-width: 0;
			height: 44px;
			padding: 0;
			justify-content: center;
			border-radius: 50%;
			background: rgba(255, 255, 255, 0.08);
		}
		.search-btn:active,
		.me-btn:active {
			transform: scale(0.94);
		}
		.search-txt,
		.search-kbd {
			display: none;
		}
		.help-btn,
		.user,
		.burger,
		.main-nav,
		.main-nav.open {
			display: none;
		}
		.me-btn {
			display: grid;
			place-items: center;
			width: 44px;
			height: 44px;
			padding: 0;
			border: 0;
			border-radius: 50%;
			background: none;
			color: #fff;
			font: inherit;
			cursor: pointer;
			flex: none;
			transition: transform var(--dur-fast) var(--ease-out);
		}
		.me-btn .avatar {
			width: 2.1rem;
			height: 2.1rem;
			font-size: 0.8rem;
			display: grid;
		}
		.in-mob {
			display: inline-flex;
			min-height: 38px;
			padding: 0.3rem 0.8rem;
			font-size: 0.875rem;
		}
		/* Тур: аркуш над нижньою панеллю (видно підсвічені вкладки) */
		.help-pop {
			position: fixed;
			top: auto;
			left: calc(0.5rem + var(--safe-l, 0px));
			right: calc(0.5rem + var(--safe-r, 0px));
			bottom: calc(var(--tabbar-h, 64px) + 0.5rem);
			width: auto;
			max-height: calc(100dvh - var(--tabbar-h, 64px) - 72px);
			overflow-y: auto;
			padding: 1rem 1rem 0.9rem;
			border-radius: 20px;
			transform-origin: 50% 100%;
		}
		.help-pop::before {
			display: none;
		}
		.help-stage {
			min-height: 7.4rem;
		}
		.hbtn {
			min-height: 44px;
		}
		.help-x {
			width: 40px;
			height: 40px;
		}

		main {
			padding-top: 1rem;
			padding-bottom: 1.5rem;
		}
		.site-footer {
			padding-bottom: calc(1rem + var(--tabbar-h, 64px));
			font-size: 0.8125rem;
		}

		/* --- Нижня панель вкладок --- */
		.tabbar {
			position: fixed;
			left: 0;
			right: 0;
			bottom: 0;
			z-index: 40;
			display: grid;
			grid-template-columns: repeat(5, minmax(0, 1fr));
			height: var(--tabbar-h, 64px);
			padding: 0 var(--safe-r, 0px) var(--safe-b, 0px) var(--safe-l, 0px);
			background: rgba(255, 255, 255, 0.92);
			-webkit-backdrop-filter: saturate(1.6) blur(16px);
			backdrop-filter: saturate(1.6) blur(16px);
			border-top: 1px solid rgba(15, 35, 65, 0.1);
			box-shadow: 0 -8px 24px -18px rgba(8, 20, 38, 0.45);
			view-transition-name: tabbar;
		}
		.tab {
			position: relative;
			z-index: 1;
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			gap: 3px;
			min-width: 0;
			height: 64px;
			padding: 0 2px;
			border: 0;
			background: none;
			color: #5b6878;
			font: inherit;
			text-decoration: none;
			cursor: pointer;
			-webkit-tap-highlight-color: transparent;
			transition: color var(--dur-base);
		}
		.tab:hover {
			color: var(--navy);
			text-decoration: none;
		}
		.tab-ico {
			display: grid;
			place-items: center;
			width: 52px;
			height: 30px;
			transition: transform var(--dur-base) var(--ease-spring);
		}
		.tab:active .tab-ico {
			transform: scale(0.88);
		}
		.tab-txt {
			max-width: 100%;
			font-size: 0.6875rem;
			font-weight: 600;
			line-height: 1.1;
			letter-spacing: -0.015em;
			white-space: nowrap;
		}
		.tab[aria-current='page'],
		.tab.on {
			color: var(--navy);
		}
		.tab[aria-current='page'] .tab-txt,
		.tab.on .tab-txt {
			font-weight: 700;
		}
		.tab[aria-current='page'] :global(.icon),
		.tab.on :global(.icon) {
			stroke-width: 2.1;
		}
		/* Ковзна «пігулка» під значком активної вкладки */
		.tab-ind {
			position: absolute;
			top: 8px;
			left: var(--safe-l, 0px);
			width: calc((100% - var(--safe-l, 0px) - var(--safe-r, 0px)) / 5);
			height: 30px;
			display: grid;
			place-items: center;
			opacity: 0;
			transform: translateX(calc(var(--i, 0) * 100%));
			transition:
				transform 420ms var(--ease-spring),
				opacity var(--dur-base);
			pointer-events: none;
		}
		.tab-ind::before {
			content: '';
			width: 56px;
			height: 30px;
			border-radius: 999px;
			background: linear-gradient(180deg, #ffe7a8, #ffd56b);
			box-shadow: 0 4px 12px -6px rgba(224, 138, 0, 0.8);
		}
		.tab-ind.show {
			opacity: 1;
		}
		.tab.tour-hl {
			color: var(--navy) !important;
			background: rgba(245, 165, 36, 0.14) !important;
			border-radius: 14px !important;
		}

		/* --- Аркуш «Меню» --- */
		.sheet-backdrop {
			position: fixed;
			inset: 0;
			z-index: 60;
			background: rgba(8, 20, 38, 0.48);
			-webkit-backdrop-filter: blur(2px);
			backdrop-filter: blur(2px);
		}
		.sheet {
			position: fixed;
			left: 0;
			right: 0;
			bottom: 0;
			z-index: 61;
			display: flex;
			flex-direction: column;
			max-height: calc(100dvh - 2.5rem - var(--safe-t, 0px));
			padding: 0 calc(1rem + var(--safe-r, 0px)) calc(1rem + var(--safe-b, 0px)) calc(1rem + var(--safe-l, 0px));
			background: var(--surface);
			color: var(--text);
			border-radius: 22px 22px 0 0;
			box-shadow: 0 -20px 50px -20px rgba(8, 20, 38, 0.55);
			transition: transform 260ms var(--ease-out);
			outline: none;
		}
		.sheet.dragging {
			transition: none;
		}
		.sheet-top {
			touch-action: none;
			cursor: grab;
		}
		.sheet-grab {
			display: block;
			width: 40px;
			height: 5px;
			margin: 8px auto 10px;
			border-radius: 999px;
			background: #cfd7e2;
		}
		.sheet-head {
			display: flex;
			align-items: center;
			gap: 0.75rem;
			padding-bottom: 0.85rem;
			border-bottom: 1px solid var(--line-soft);
		}
		.avatar.lg {
			display: grid;
			width: 2.75rem;
			height: 2.75rem;
			color: #fff;
			font-size: 0.95rem;
		}
		.sheet-who {
			display: flex;
			flex-direction: column;
			min-width: 0;
			flex: 1;
			line-height: 1.3;
		}
		.sheet-name {
			font-weight: 700;
			color: var(--ink);
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.sheet-role {
			font-size: 0.85rem;
			color: var(--muted);
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.sheet-close {
			display: grid;
			place-items: center;
			width: 44px;
			height: 44px;
			flex: none;
			border: 0;
			border-radius: 50%;
			background: var(--neutral-soft);
			color: var(--text-2);
			cursor: pointer;
		}
		.sheet-body {
			overflow-y: auto;
			overscroll-behavior: contain;
			margin: 0 -0.25rem;
			padding: 0 0.25rem;
		}
		.sheet-label {
			display: flex;
			align-items: center;
			gap: 0.4rem;
			margin: 0.9rem 0 0.35rem;
			font-size: 0.75rem;
			font-weight: 700;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			color: var(--muted);
		}
		.sheet-list {
			list-style: none;
			margin: 0;
			padding: 0;
			border-radius: 16px;
			background: var(--surface-2);
			border: 1px solid var(--line-soft);
			overflow: hidden;
		}
		.sheet-list li + li {
			border-top: 1px solid var(--line-soft);
		}
		.sheet-list a {
			display: flex;
			align-items: center;
			gap: 0.75rem;
			min-height: 56px;
			padding: 0.55rem 0.9rem;
			color: var(--text);
			text-decoration: none;
			transition: background var(--dur-fast);
		}
		.sheet-list a:active {
			background: var(--accent-soft);
		}
		.sheet-list a[aria-current='page'] {
			background: var(--sun-soft);
			box-shadow: inset 3px 0 0 var(--sun-strong);
		}
		.sl-txt {
			display: flex;
			flex-direction: column;
			flex: 1;
			min-width: 0;
			line-height: 1.3;
		}
		.sl-label {
			font-weight: 600;
		}
		.sl-chev {
			flex: none;
			color: var(--line-strong);
		}
		.sheet-actions {
			display: grid;
			grid-template-columns: 1.5fr 1fr;
			gap: 0.6rem;
			margin-top: 0.9rem;
		}
		.sheet-btn {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			gap: 0.5rem;
			min-height: 48px;
			padding: 0.5rem 0.75rem;
			white-space: nowrap;
			border-radius: 14px;
			border: 1px solid var(--line);
			background: var(--surface);
			color: var(--navy);
			font: inherit;
			font-weight: 600;
			cursor: pointer;
		}
		.sheet-btn:active {
			transform: scale(0.98);
		}
		.sb-q {
			display: grid;
			place-items: center;
			width: 1.4rem;
			height: 1.4rem;
			border-radius: 50%;
			background: var(--navy);
			color: #ffd56b;
			font-size: 0.8rem;
			font-weight: 700;
		}
		.in-m {
			color: #2a1900;
			text-decoration: none;
			border-color: #d98c0b;
			background: linear-gradient(180deg, #ffc54d, var(--sun));
		}
		.avatar.lg.pub {
			background: var(--neutral-soft);
			color: var(--navy);
			box-shadow: none;
		}
		.out-m {
			color: var(--bad);
			border-color: color-mix(in srgb, var(--bad) 30%, var(--line));
		}
	}
	@media (max-width: 768px) and (prefers-reduced-motion: reduce) {
		.tab-ind,
		.sheet {
			transition: none;
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
