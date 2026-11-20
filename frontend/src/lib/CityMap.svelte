<script lang="ts">
	// Мапа комунальних об'єктів громади (Leaflet + світла підкладка CARTO/OSM).
	// Leaflet вантажимо лише в браузері (динамічний import в onMount) — компонент безпечний для SSR.
	// Правило безпеки: мапа НЕ показує СЕС, акумулятори, генератори чи резервне живлення —
	// тільки тип закладу, споживання, сонячний потенціал і якість даних (див. api-map.ts).
	import 'leaflet/dist/leaflet.css';
	import { onMount, untrack } from 'svelte';
	import type * as Leaflet from 'leaflet';

	const ALERT_SVG =
		'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5 2.5 20h19L12 3.5Z"/><path d="M12 10v4.5M12 17.2h.01"/></svg>';
	import {
		type MapPoint,
		type ColorBy,
		type Scale,
		type LatLngBounds,
		POLTAVA,
		CATEGORIES,
		buildScale,
		pointStyle,
		categoryMeta,
		hasCoords,
		isApprox,
		keyFigure,
		PRECISION_TEXT
	} from '#lib/api-map.ts';

	interface Props {
		/** Усі об'єкти для показу (без координат — просто ігноруються) */
		points: MapPoint[];
		/** Вибраний об'єкт: мапа плавно перелітає до нього й відкриває картку */
		selectedId?: number | null;
		/** Підсвітка (наприклад, наведення на рядок списку) */
		highlightId?: number | null;
		colorBy?: ColorBy;
		/** Шкала легенди; якщо не передати — рахується з points */
		scale?: Scale | null;
		/** Клік по маркеру (id) або закриття картки (null) */
		onselect?: (id: number | null) => void;
		/** Наведення миші на маркер (id) / відведення (null) */
		onhover?: (id: number | null) => void;
		/** CSS-висота, напр. '420px'; за замовчуванням 100% батька */
		height?: string;
		/** Компактний режим для вбудовування: без зуму коліщатком, менші маркери, міні-легенда */
		compact?: boolean;
		/** Початкові межі [[пд, зх], [пн, сх]]; якщо немає — за точками */
		bounds?: LatLngBounds | null;
		/** Підпис для читачів екрана */
		label?: string;
		/** false — не відкривати картку Leaflet (сторінка показує власну, напр. на телефоні) */
		popup?: boolean;
		/** Скільки пікселів знизу мапи закрито (шторка/картка): вибраний маркер центруємо у видимій частині */
		padBottom?: number;
	}

	let {
		points,
		selectedId = null,
		highlightId = null,
		colorBy = 'category',
		scale = undefined,
		onselect,
		onhover,
		height = '100%',
		compact = false,
		bounds = null,
		label = 'Мапа комунальних об’єктів Полтавської громади',
		popup: usePopup = true,
		padBottom = 0
	}: Props = $props();
	const skipId = `cm-after-${Math.random().toString(36).slice(2, 8)}`;

	const activeScale = $derived(scale === undefined ? buildScale(points, colorBy) : scale);
	const visible = $derived(points.filter(hasCoords));

	let el: HTMLDivElement;
	let L: typeof Leaflet | null = null;
	let map: Leaflet.Map | null = null;
	let layer: Leaflet.LayerGroup | null = null;
	let ready = $state(false);
	let failed = $state(false);

	interface Entry {
		m: Leaflet.Marker;
		p: MapPoint;
		key: string;
	}
	const markers = new Map<number, Entry>();
	let current: number | null = null;
	let hl: number | null = null;
	let firstPaint = true;

	const reduced =
		typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

	function esc(s: string): string {
		return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
	}

	// Кілька об'єктів з однаковими координатами (одне село / одна вулиця) розкладаємо
	// «соняшником» на кілька десятків метрів, щоб кожен було видно й можна було клацнути.
	function spread(list: (MapPoint & { lat: number; lon: number })[]): Map<number, [number, number]> {
		const groups = new Map<string, typeof list>();
		for (const p of list) {
			const k = `${p.lat.toFixed(5)},${p.lon.toFixed(5)}`;
			const g = groups.get(k);
			if (g) g.push(p);
			else groups.set(k, [p]);
		}
		const out = new Map<number, [number, number]>();
		const GOLDEN = Math.PI * (3 - Math.sqrt(5));
		for (const g of groups.values()) {
			g.sort((a, b) => a.id - b.id);
			g.forEach((p, i) => {
				if (g.length === 1) return out.set(p.id, [p.lat, p.lon]);
				const r = 0.00032 * Math.sqrt(i + 0.6);
				const a = i * GOLDEN;
				out.set(p.id, [p.lat + r * Math.sin(a), p.lon + (r * Math.cos(a)) / Math.cos((p.lat * Math.PI) / 180)]);
			});
		}
		return out;
	}

	function pinHtml(p: MapPoint, delay: number | null): string {
		const st = pointStyle(p, colorBy, activeScale);
		const cls = ['cm-pin'];
		if (isApprox(p)) cls.push('cm-approx');
		// delay ≥ 0 — перша поява «хвилею» від центру; -1 — тиха поява після зміни фільтра
		if (delay !== null) cls.push(delay < 0 ? 'cm-fade' : 'cm-in');
		return `<span class="${cls.join(' ')}" style="--c:${st.color};--ink:${st.ink};--sz:${st.size}px;--d:${delay ?? 0}ms"><svg viewBox="0 0 10 10" aria-hidden="true"><path d="${st.glyph}"/></svg></span>`;
	}

	function pinOf(id: number): HTMLElement | null {
		return (markers.get(id)?.m.getElement()?.querySelector('.cm-pin') as HTMLElement) ?? null;
	}

	/** Оновлює колір/розмір наявного маркера без повторної анімації появи */
	function restyle(e: Entry) {
		const pin = pinOf(e.p.id);
		if (!pin) return;
		const st = pointStyle(e.p, colorBy, activeScale);
		pin.style.setProperty('--c', st.color);
		pin.style.setProperty('--ink', st.ink);
		pin.style.setProperty('--sz', `${st.size}px`);
		pin.querySelector('path')?.setAttribute('d', st.glyph);
		pin.classList.toggle('cm-approx', isApprox(e.p));
	}

	function syncMarkers() {
		if (!L || !map || !layer) return;
		const pos = spread(visible);
		const keep = new Set(visible.map((p) => p.id));
		for (const [id, e] of markers) {
			if (!keep.has(id)) {
				markers.delete(id);
				// Фільтр: маркер згасає за 120 мс, а не зникає стрибком (reduced — одразу)
				const pin = e.m.getElement()?.querySelector('.cm-pin');
				if (reduced || !pin) layer.removeLayer(e.m);
				else {
					pin.classList.add('cm-out');
					const lyr = layer;
					setTimeout(() => lyr.removeLayer(e.m), 130);
				}
			}
		}
		// Поява хвилею від центру мапи до околиць
		const c = map.getCenter();
		const fresh = visible
			.filter((p) => !markers.has(p.id))
			.map((p) => ({ p, d: (p.lat - c.lat) ** 2 + ((p.lon - c.lng) * 0.65) ** 2 }))
			.sort((a, b) => a.d - b.d);
		// Єдиний «момент» мапи: перша поява розходиться від центру за ≤ 360 мс (+240 мс на маркер).
		// Далі (фільтри, режими) нові маркери лише проявляються, без хвилі.
		const animate = !reduced;
		const step = Math.min(4, 360 / Math.max(1, fresh.length));
		const wave = firstPaint;
		fresh.forEach(({ p }, i) => {
			const ll = pos.get(p.id)!;
			const m = L!.marker(ll, {
				icon: L!.divIcon({
					className: 'cm-mk',
					iconSize: [0, 0],
					iconAnchor: [0, 0],
					html: pinHtml(p, !animate ? null : wave ? Math.round(i * step) : -1)
				}),
				keyboard: false,
				riseOnHover: true,
				riseOffset: 500
			});
			m.bindTooltip(esc(p.name), {
				direction: 'top',
				offset: [0, -12],
				className: 'cm-tip',
				opacity: 1
			});
			m.on('click', () => {
				m.closeTooltip();
				choose(p.id);
			});
			m.on('mouseover', () => onhover?.(p.id));
			m.on('mouseout', () => onhover?.(null));
			m.on('add', () => {
				const pin = m.getElement()?.querySelector('.cm-pin');
				pin?.addEventListener('animationend', () => pin.classList.remove('cm-in', 'cm-fade'), { once: true });
			});
			m.addTo(layer!);
			markers.set(p.id, { m, p, key: `${ll[0]},${ll[1]}` });
		});
		// Наявні: нова позиція (після фільтра «соняшник» міг змінитися) та колір режиму
		for (const p of visible) {
			const e = markers.get(p.id)!;
			e.p = p;
			const ll = pos.get(p.id)!;
			const key = `${ll[0]},${ll[1]}`;
			if (key !== e.key) {
				e.m.setLatLng(ll);
				e.key = key;
			}
			restyle(e);
		}
		firstPaint = false;
		// Вибраний об'єкт міг зникнути з мапи через фільтр; інакше — оновлюємо число в картці під режим
		if (current !== null && !markers.has(current)) map.closePopup();
		else if (current !== null && openPopup?.isOpen()) openPopup.setContent(card(markers.get(current)!.p));
		markSel(current);
		markHl(hl);
	}

	function markSel(id: number | null) {
		// Клас не знімаємо з того самого маркера — інакше імпульс-кільце перезапускалося б при кожному оновленні
		const target = id !== null ? pinOf(id) : null;
		for (const pin of el.querySelectorAll('.cm-pin.cm-sel')) if (pin !== target) pin.classList.remove('cm-sel');
		for (const e of markers.values()) e.m.setZIndexOffset(e.p.id === id ? 1000 : e.p.id === hl ? 800 : 0);
		target?.classList.add('cm-sel');
	}

	function markHl(id: number | null) {
		for (const pin of el.querySelectorAll('.cm-pin.cm-hl')) pin.classList.remove('cm-hl');
		hl = id;
		if (id !== null) {
			pinOf(id)?.classList.add('cm-hl');
			markers.get(id)?.m.setZIndexOffset(id === current ? 1000 : 800);
		}
	}

	function card(p: MapPoint): HTMLElement {
		const cat = categoryMeta(p.category_short);
		const fig = keyFigure(p, colorBy);
		const root = document.createElement('div');
		root.className = 'cm-card';
		const type = document.createElement('div');
		type.className = 'cm-card-type';
		type.innerHTML = `<span class="cm-sw" style="--c:${cat.color};--ink:${cat.ink}"><svg viewBox="0 0 10 10" aria-hidden="true"><path d="${cat.glyph}"/></svg></span>`;
		type.append(document.createTextNode(p.category_short || cat.label));
		const name = document.createElement('div');
		name.className = 'cm-card-name';
		name.textContent = p.name;
		const addr = document.createElement('div');
		addr.className = 'cm-card-addr';
		addr.textContent = p.address;
		const f = document.createElement('div');
		f.className = 'cm-card-fig';
		if (fig.unit) f.innerHTML = `<span class="cm-v">${esc(fig.value)}</span> <span class="cm-u">${esc(fig.unit)}</span><span class="cm-l">${esc(fig.label)}</span>`;
		else {
			f.classList.add('cm-card-fig-empty');
			f.textContent = fig.label[0].toUpperCase() + fig.label.slice(1);
		}
		root.append(type, name, addr, f);
		const notes: string[] = [];
		if (isApprox(p) && p.precision) notes.push(`≈ Розташування ${PRECISION_TEXT[p.precision].replace('приблизно: ', 'приблизне: ')}`);
		if (!p.data_ok || p.defects_count > 0)
			notes.push(`!${p.defects_count > 0 ? `${p.defects_count} зауваж. до даних` : 'Є зауваження до даних'}`);
		for (const n of notes) {
			const d = document.createElement('div');
			d.className = 'cm-card-note';
			if (n.startsWith('!')) {
				// значок-попередження тим самим лінійним стилем, що й Icon.svelte (статичний SVG)
				d.innerHTML = ALERT_SVG;
				d.append(n.slice(1));
			} else d.textContent = n;
			root.append(d);
		}
		const a = document.createElement('a');
		a.className = 'cm-card-btn';
		a.href = `/object/${encodeURIComponent(p.id)}`;
		a.textContent = 'Відкрити об’єкт →';
		root.append(a);
		return root;
	}

	function choose(id: number | null) {
		current = id;
		applySelection(id, true);
		onselect?.(id);
	}

	let applied: number | null = null;
	let openPopup: Leaflet.Popup | null = null;
	function applySelection(id: number | null, force = false) {
		if (!L || !map) return;
		if (!force && id === applied) return;
		applied = id;
		current = id;
		markSel(id);
		const e = id !== null ? markers.get(id) : undefined;
		if (!e) {
			map.closePopup();
			return;
		}
		const ll = e.m.getLatLng();
		const z = Math.max(map.getZoom(), compact ? 14 : 15.5);
		if (!usePopup) {
			// Без картки Leaflet: маркер — у центрі видимої частини (над шторкою)
			map.closePopup();
			const t = map.unproject(map.project(ll, z).add([0, padBottom / 2]), z);
			if (reduced) map.setView(t, z, { animate: false });
			else map.flyTo(t, z, { duration: 0.7, easeLinearity: 0.2 });
			return;
		}
		// Маркер трохи нижче центру, щоб над ним вмістилася картка
		const shift = compact ? 70 : 110;
		const target = map.unproject(map.project(ll, z).subtract([0, shift]), z);
		if (reduced) map.setView(target, z, { animate: false });
		else map.flyTo(target, z, { duration: 0.85, easeLinearity: 0.2 });
		const popup = L.popup({
			className: 'cm-popup',
			offset: [0, -10],
			autoPan: false,
			maxWidth: 300,
			minWidth: 260,
			closeButton: true
		})
			.setLatLng(ll)
			.setContent(card(e.p));
		openPopup = popup;
		popup.on('remove', () => {
			if (current === id) {
				current = null;
				applied = null;
				markSel(null);
				onselect?.(null);
			}
		});
		popup.openOn(map);
		const btn = popup.getElement()?.querySelector<HTMLAnchorElement>('.leaflet-popup-close-button');
		if (btn) {
			btn.setAttribute('aria-label', 'Закрити картку');
			btn.title = 'Закрити';
		}
	}

	function initialBounds(): Leaflet.LatLngBoundsExpression | null {
		if (bounds) return bounds;
		if (!visible.length) return null;
		let s = 90, w = 180, n = -90, e = -180;
		for (const p of visible) {
			s = Math.min(s, p.lat);
			n = Math.max(n, p.lat);
			w = Math.min(w, p.lon);
			e = Math.max(e, p.lon);
		}
		return [[s, w], [n, e]];
	}

	/** Стартовий вигляд: «ядро» громади без кількох віддалених сіл (вся громада — кнопкою) */
	function coreBounds(): Leaflet.LatLngBoundsExpression | null {
		if (visible.length < 20) return initialBounds();
		const q = (arr: number[], t: number) => arr[Math.min(arr.length - 1, Math.max(0, Math.floor(t * arr.length)))];
		const la = visible.map((p) => p.lat).sort((a, b) => a - b);
		const lo = visible.map((p) => p.lon).sort((a, b) => a - b);
		return [
			[q(la, 0.06), q(lo, 0.06)],
			[q(la, 0.94), q(lo, 0.94)]
		];
	}

	export function resetView() {
		if (!map) return;
		const b = initialBounds();
		if (b) map.flyToBounds(b, { padding: compact ? [16, 16] : [36, 36], duration: reduced ? 0 : 0.4, animate: !reduced });
		else map.setView(POLTAVA, 12);
	}

	function zoomScale() {
		if (!map) return;
		const z = map.getZoom();
		const s = z <= 11 ? 0.66 : z <= 12 ? 0.8 : z <= 13 ? 0.92 : z <= 14.5 ? 1.05 : 1.2;
		el.style.setProperty('--mk-z', String(compact ? s * 0.9 : s));
	}

	onMount(() => {
		let disposed = false;
		const ro = new ResizeObserver(() => map?.invalidateSize({ animate: false }));
		(async () => {
			try {
				const mod = await import('leaflet');
				if (disposed) return;
				L = ((mod as unknown as { default?: typeof Leaflet }).default ?? mod) as typeof Leaflet;
				map = L.map(el, {
					zoomControl: false,
					scrollWheelZoom: !compact,
					zoomSnap: 0.25,
					zoomDelta: 0.5,
					wheelPxPerZoomLevel: 100,
					minZoom: 9,
					maxZoom: 19,
					fadeAnimation: !reduced,
					zoomAnimation: !reduced,
					markerZoomAnimation: !reduced
				});
				map.attributionControl.setPrefix(false);
				L.control.zoom({ position: 'topright', zoomInTitle: 'Наблизити', zoomOutTitle: 'Віддалити' }).addTo(map);

				// Підкладка OpenStreetMap (українські назви вулиць), приглушена CSS-фільтром до
				// спокійної світлої гами, щоб кольорові маркери читалися першими.
				// (CARTO без API-ключа тепер малює водяні знаки — тому не використовуємо.)
				L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
					maxZoom: 19,
					attribution:
						'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">учасники OpenStreetMap</a>'
				}).addTo(map);

				layer = L.layerGroup().addTo(map);
				const b = coreBounds();
				if (b) map.fitBounds(b, { padding: compact ? [16, 16] : [36, 36], animate: false });
				else map.setView(POLTAVA, 12, { animate: false });
				map.on('zoomend', zoomScale);
				// Без карток Leaflet дотик по порожній мапі знімає вибір
				map.on('click', () => {
					if (!usePopup && current !== null) choose(null);
				});
				zoomScale();
				ro.observe(el);
				ready = true;
			} catch {
				failed = true;
			}
		})();
		return () => {
			disposed = true;
			ro.disconnect();
			map?.remove();
			map = null;
			markers.clear();
		};
	});

	// Точки, режим кольору чи шкала змінилися — оновлюємо маркери
	$effect(() => {
		if (!ready) return;
		void visible;
		void colorBy;
		void activeScale;
		untrack(syncMarkers);
	});

	// Вибір іззовні (зі списку)
	$effect(() => {
		if (!ready) return;
		const id = selectedId;
		untrack(() => applySelection(id));
	});

	$effect(() => {
		if (!ready) return;
		const id = highlightId;
		untrack(() => markHl(id));
	});

	// Міні-легенда для компактного режиму
	const presentCats = $derived.by(() => {
		const keys = new Set(visible.map((p) => categoryMeta(p.category_short).key));
		return CATEGORIES.filter((c) => keys.has(c.key));
	});
	const anyApprox = $derived(visible.some(isApprox));
	const srList = $derived(compact ? [...points].sort((a, b) => a.name.localeCompare(b.name, 'uk')) : []);
</script>

<div class="cm-root" class:compact style:height>
	<a
		class="cm-skip"
		href="#{skipId}"
		onclick={(e) => {
			e.preventDefault();
			document.getElementById(skipId)?.focus();
		}}>Пропустити мапу</a
	>
	<div
		bind:this={el}
		class="cm-map"
		role="region"
		aria-label={label + (compact ? '' : '. Той самий перелік об’єктів доступний списком поруч.')}
	></div>

	{#if !ready && !failed}
		<div class="cm-loading" aria-hidden="true"><span class="cm-shimmer"></span></div>
	{/if}
	{#if failed}
		<div class="cm-failed" role="status">Не вдалося завантажити мапу. Перевірте з’єднання з інтернетом.</div>
	{/if}

	{#if ready}
		<button type="button" class="cm-reset" onclick={resetView} title="Показати всю громаду">
			<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"
				><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg
			>
			<span>Уся громада</span>
		</button>
	{/if}

	{#if compact && ready}
		<div class="cm-mini-legend" aria-hidden="true">
			{#if colorBy === 'category' || !activeScale}
				{#each presentCats as c (c.key)}
					<span class="cm-li"><span class="cm-sw" style="--c:{c.color};--ink:{c.ink}"><svg viewBox="0 0 10 10"><path d={c.glyph} /></svg></span>{c.label}</span>
				{/each}
			{:else}
				<span class="cm-li cm-li-title">{activeScale.colorBy === 'consumption' ? 'Споживання' : 'Потенціал сонця'}:</span>
				{#each activeScale.stops as s (s.label)}
					<span class="cm-li"><span class="cm-sw" style="--c:{s.color}"></span>{s.label}</span>
				{/each}
			{/if}
			{#if anyApprox}<span class="cm-li"><span class="cm-sw cm-sw-approx"></span>розташування приблизне</span>{/if}
		</div>
		<ul class="cm-sr">
			{#each srList as p (p.id)}
				<li><a href="/object/{p.id}" tabindex="-1">{p.name}, {p.address}</a></li>
			{/each}
		</ul>
	{/if}
	<span id={skipId} class="cm-after" tabindex="-1"></span>
</div>

<style>
	.cm-root {
		position: relative;
		width: 100%;
		min-height: 240px;
		overflow: hidden;
		background: #eef1f4;
		isolation: isolate;
		--mk-z: 1;
	}
	.cm-map {
		position: absolute;
		inset: 0;
		background: #eef1f4;
		font: inherit;
	}
	.cm-map:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: -3px;
		box-shadow: none;
	}

	/* ---------- Маркери ---------- */
	.cm-root :global(.cm-mk) {
		background: none;
		border: 0;
	}
	.cm-root :global(.cm-pin) {
		position: absolute;
		left: 0;
		top: 0;
		width: calc(var(--sz) * var(--mk-z));
		height: calc(var(--sz) * var(--mk-z));
		transform: translate(-50%, -50%);
		border-radius: 50%;
		background: var(--c);
		color: var(--ink);
		border: 1.5px solid #fff;
		box-shadow:
			0 0 0 0.5px rgba(15, 23, 42, 0.35),
			0 1px 3px rgba(15, 23, 42, 0.3);
		display: grid;
		place-items: center;
		cursor: pointer;
		/* Зміна режиму кольору — перехід кольору 220 мс; розмір — миттєво (без анімації геометрії) */
		transition:
			background-color var(--dur-base) var(--ease-out),
			color var(--dur-base) var(--ease-out),
			scale var(--dur-fast) var(--ease-out),
			opacity var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast) var(--ease-out);
	}
	.cm-root :global(.cm-pin svg) {
		width: 62%;
		height: 62%;
		fill: currentColor;
		display: block;
	}
	.cm-root :global(.cm-pin.cm-in) {
		animation: cm-pop 240ms var(--ease-emph) var(--d) both;
	}
	@keyframes -global-cm-pop {
		from {
			opacity: 0;
			transform: translate(-50%, -50%) scale(0.4);
		}
		to {
			opacity: 1;
			transform: translate(-50%, -50%) scale(1);
		}
	}
	/* Після зміни фільтра: тихе проявлення / згасання на місці (перехресне, без повторної «хвилі») */
	.cm-root :global(.cm-pin.cm-fade) {
		animation: cm-appear var(--dur-fast) var(--ease-out) both;
	}
	.cm-root :global(.cm-pin.cm-out) {
		opacity: 0;
		pointer-events: none;
	}
	@keyframes -global-cm-appear {
		from {
			opacity: 0;
		}
	}
	/* Приблизне розташування: пунктирне кільце */
	.cm-root :global(.cm-pin.cm-approx::after) {
		content: '';
		position: absolute;
		inset: calc(-4px - 2px * var(--mk-z));
		border-radius: 50%;
		border: 1.5px dashed var(--c);
		background: rgba(255, 255, 255, 0.35);
		z-index: -1;
		filter: saturate(1.2) brightness(0.8);
	}
	.cm-root :global(.cm-pin:hover),
	.cm-root :global(.cm-pin.cm-hl) {
		scale: 1.4;
		box-shadow:
			0 0 0 3px rgba(255, 255, 255, 0.9),
			0 0 0 5px var(--c),
			0 4px 10px rgba(15, 23, 42, 0.35);
	}
	.cm-root :global(.cm-pin.cm-sel) {
		scale: 1.55;
		box-shadow:
			0 0 0 2.5px #fff,
			0 0 0 5px var(--c),
			0 6px 14px rgba(15, 23, 42, 0.4);
	}
	.cm-root :global(.cm-pin.cm-sel::before) {
		content: '';
		position: absolute;
		inset: -4px;
		border-radius: 50%;
		border: 2px solid var(--c);
		/* Одне кільце-імпульс у момент вибору — «ось він», без нескінченного миготіння */
		animation: cm-pulse 600ms var(--ease-out) 1 both;
		pointer-events: none;
	}
	@keyframes -global-cm-pulse {
		0% {
			opacity: 0.8;
			transform: scale(1);
		}
		100% {
			opacity: 0;
			transform: scale(2.4);
		}
	}

	/* ---------- Підказка й картка ---------- */
	.cm-root :global(.leaflet-tooltip.cm-tip) {
		background: #142235;
		color: #fff;
		border: 0;
		border-radius: var(--r-btn);
		padding: 0.3rem 0.6rem;
		font: inherit;
		font-size: 0.8125rem;
		font-weight: 600;
		max-width: 18rem;
		white-space: normal;
		width: max-content;
		box-shadow: 0 6px 16px -6px rgba(8, 20, 38, 0.5);
	}
	.cm-root :global(.leaflet-tooltip-top.cm-tip::before) {
		border-top-color: #142235;
	}
	.cm-root :global(.cm-popup .leaflet-popup-content-wrapper) {
		border-radius: var(--r-card);
		padding: 0;
		box-shadow:
			0 2px 4px rgba(16, 24, 40, 0.06),
			0 18px 40px -12px rgba(16, 24, 40, 0.35);
		animation: cm-slide var(--dur-base) var(--ease-emph) both;
		transform-origin: 50% 100%;
	}
	.cm-root :global(.cm-popup .leaflet-popup-tip-container) {
		animation: cm-fade var(--dur-base) var(--ease-out) both;
	}
	@keyframes -global-cm-slide {
		from {
			opacity: 0;
			transform: translateY(8px); /* виїжджає вгору від свого маркера */
		}
		to {
			opacity: 1;
			transform: none;
		}
	}
	@keyframes -global-cm-fade {
		from {
			opacity: 0;
		}
	}
	.cm-root :global(.cm-popup .leaflet-popup-content) {
		margin: 0;
		min-width: 260px;
		font: inherit;
		line-height: 1.4;
	}
	.cm-root :global(.cm-popup .leaflet-popup-close-button) {
		top: 6px;
		right: 6px;
		width: 28px;
		height: 28px;
		border-radius: var(--r-btn);
		font-size: 20px;
		line-height: 26px;
		color: var(--muted);
	}
	.cm-root :global(.cm-popup .leaflet-popup-close-button:hover) {
		background: var(--neutral-soft);
		color: var(--text);
	}
	.cm-root :global(.cm-card) {
		padding: 0.85rem 1rem 0.9rem;
		color: var(--text);
	}
	.cm-root :global(.cm-card-type) {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--muted);
		padding-right: 1.6rem;
	}
	.cm-root :global(.cm-card-name) {
		margin-top: 0.3rem;
		font-weight: 650;
		font-size: 0.98rem;
		line-height: 1.3;
	}
	.cm-root :global(.cm-card-addr) {
		font-size: 0.8125rem;
		color: var(--muted);
		margin-top: 0.15rem;
	}
	.cm-root :global(.cm-card-fig) {
		margin-top: 0.65rem;
		padding: 0.55rem 0.7rem;
		border-radius: var(--r-card);
		background: var(--neutral-soft);
	}
	.cm-root :global(.cm-card-fig-empty) {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.cm-root :global(.cm-v) {
		font-size: 1.35rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		letter-spacing: -0.01em;
	}
	.cm-root :global(.cm-u) {
		font-weight: 600;
		color: var(--muted);
		font-size: 0.875rem;
	}
	.cm-root :global(.cm-l) {
		display: block;
		font-size: 0.78rem;
		color: var(--muted);
	}
	.cm-root :global(.cm-card-note) {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin-top: 0.45rem;
		font-size: 0.78rem;
		color: var(--warn);
	}
	.cm-root :global(.cm-card-note svg) {
		flex: none;
	}
	.cm-root :global(.cm-card-btn) {
		display: flex;
		justify-content: center;
		margin-top: 0.75rem;
		padding: 0.5rem 0.8rem;
		border-radius: var(--r-btn);
		background: var(--accent);
		color: #fff !important;
		font-weight: 650;
		font-size: 0.9rem;
		text-decoration: none;
		transition: background-color 0.15s;
	}
	.cm-root :global(.cm-card-btn:hover) {
		background: var(--accent-dark);
	}
	.cm-root :global(.cm-sw) {
		display: inline-grid;
		place-items: center;
		flex: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--c);
		color: var(--ink, #fff);
		box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.18);
	}
	.cm-root :global(.cm-sw svg) {
		width: 64%;
		height: 64%;
		fill: currentColor;
	}

	/* ---------- Елементи керування Leaflet ---------- */
	.cm-root :global(.leaflet-control-zoom) {
		border: 0;
		border-radius: var(--r-btn);
		overflow: hidden;
		box-shadow: var(--shadow-md);
	}
	.cm-root :global(.leaflet-control-zoom a) {
		width: 36px;
		height: 36px;
		line-height: 34px;
		color: var(--text);
		font-size: 20px;
	}
	.cm-root :global(.leaflet-control-attribution) {
		font-size: 0.6875rem;
		background: rgba(255, 255, 255, 0.82);
		border-top-left-radius: 6px;
	}
	.cm-root :global(.leaflet-container) {
		font: inherit;
		background: #eef1f4;
	}
	.cm-root :global(.leaflet-tile-pane) {
		filter: grayscale(0.88) brightness(1.06) contrast(0.86) sepia(0.06);
	}
	.cm-root :global(.leaflet-container a.leaflet-popup-close-button:focus-visible),
	.cm-root :global(.leaflet-control-zoom a:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: -3px;
		box-shadow: none;
	}

	.cm-reset {
		position: absolute;
		z-index: 500;
		top: 92px;
		right: 10px;
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 36px;
		padding: 0.35rem 0.75rem;
		border: 0;
		border-radius: var(--r-btn);
		background: #fff;
		color: var(--text);
		font: inherit;
		font-size: 0.85rem;
		font-weight: 600;
		box-shadow: var(--shadow-md);
		cursor: pointer;
	}
	.cm-reset:hover {
		background: var(--accent-soft);
		color: var(--accent-dark);
	}
	.compact .cm-reset span {
		display: none;
	}
	@media (max-width: 600px) {
		.cm-reset span {
			display: none;
		}
	}

	.cm-loading {
		position: absolute;
		inset: 0;
		z-index: 600;
		background: #eef1f4;
		overflow: hidden;
	}
	.cm-shimmer {
		position: absolute;
		inset: 0;
		background: linear-gradient(100deg, transparent 30%, rgba(255, 255, 255, 0.6) 50%, transparent 70%);
		background-size: 200% 100%;
		animation: cm-shim 1.4s linear infinite;
	}
	@keyframes cm-shim {
		from {
			background-position: 150% 0;
		}
		to {
			background-position: -50% 0;
		}
	}
	.cm-failed {
		position: absolute;
		inset: 0;
		z-index: 600;
		display: grid;
		place-items: center;
		padding: 1rem;
		text-align: center;
		color: var(--muted);
		background: #eef1f4;
	}

	.cm-mini-legend {
		position: absolute;
		z-index: 500;
		left: 10px;
		bottom: 22px;
		right: 60px;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.75rem;
		width: max-content;
		max-width: calc(100% - 70px);
		padding: 0.4rem 0.65rem;
		border-radius: var(--r-card);
		background: rgba(255, 255, 255, 0.92);
		box-shadow: var(--shadow-md);
		font-size: 0.75rem;
		color: var(--text);
		pointer-events: none;
	}
	.cm-li {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		white-space: nowrap;
	}
	.cm-li-title {
		font-weight: 650;
	}
	.cm-sw-approx {
		background: transparent !important;
		border: 1.5px dashed var(--muted);
		box-shadow: none !important;
	}
	.cm-skip {
		position: absolute;
		z-index: 1100;
		top: 8px;
		left: 8px;
		padding: 0.45rem 0.8rem;
		border-radius: var(--r-btn);
		background: var(--navy, #10325a);
		color: #fff;
		font-weight: 650;
		text-decoration: none;
		transform: translateY(-160%);
		transition: transform 0.15s;
	}
	.cm-skip:focus-visible,
	.cm-skip:focus {
		transform: none;
		outline: 3px solid var(--focus);
	}
	.cm-after {
		position: absolute;
		bottom: 0;
		left: 0;
		width: 1px;
		height: 1px;
		outline: none;
	}
	/* Нижні елементи Leaflet (авторство) — над шторкою/кутами, якщо сторінка задала відступ */
	.cm-root :global(.leaflet-bottom) {
		bottom: var(--cm-inset-b, 0px);
	}
	.cm-sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	@media (prefers-reduced-motion: reduce) {
		.cm-root :global(.cm-pin),
		.cm-root :global(.cm-pin.cm-in),
		.cm-root :global(.cm-pin.cm-fade),
		.cm-root :global(.cm-pin.cm-sel::before),
		.cm-root :global(.cm-popup .leaflet-popup-content-wrapper),
		.cm-root :global(.cm-popup .leaflet-popup-tip-container),
		.cm-shimmer {
			animation: none !important;
			transition: none !important;
		}
	}
</style>
