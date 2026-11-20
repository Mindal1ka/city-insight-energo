<script lang="ts">
	// Повноекранна мапа ефективності СЕС (Leaflet). Колір + форма маркера = клас K
	// (у публічному режимі — тип закладу). Маркери «хвилею» з'являються від центру,
	// вибраний об'єкт — плавний flyTo. prefers-reduced-motion вимикає анімації.
	import 'leaflet/dist/leaflet.css';
	import 'leaflet.markercluster/dist/MarkerCluster.css';
	import { onMount, untrack } from 'svelte';
	import type * as Leaflet from 'leaflet';
	import { kClassMeta, kText, type KClass, type SesItem } from './api-ses.ts';
	import { categoryMeta, POLTAVA } from './api-map.ts';
	import type { Zone } from './api-v2.ts';
	import { ZONE_COLORS } from './zone-meta.ts';

	interface Props {
		items: SesItem[];
		/** 'class' — за класом K; 'category' — за типом закладу (публічний режим) */
		colorBy?: 'class' | 'category';
		selectedId?: number | null;
		onselect?: (id: number | null) => void;
		/** Зміна ключа — повторна «хвиля» (наприклад, зміна періоду) */
		waveKey?: string;
		/** Різниця «закрито знизу − закрито зверху» (px): вибраний маркер центруємо у видимій смузі */
		padBottom?: number;
		/** Зони обміну надлишком (кола навколо якоря) */
		zones?: Zone[];
		showZones?: boolean;
		selectedZoneId?: number | null;
		onzone?: (id: number | null) => void;
		/** Підказка кнопки «Зони»: зведення по зонах */
		zoneSummary?: string;
		/** Клік по кнопці «Зони» на мапі */
		ontogglezones?: () => void;
	}

	let { items, colorBy = 'class', selectedId = null, onselect, waveKey = '', padBottom = 0, zones = [], showZones = true, selectedZoneId = null, onzone, zoneSummary = '', ontogglezones }: Props = $props();

	let el: HTMLDivElement;
	let L: typeof Leaflet | null = null;
	let map: Leaflet.Map | null = null;
	let layer: Leaflet.MarkerClusterGroup | null = null;
	let zoneGroup: Leaflet.LayerGroup | null = null;
	let ready = $state(false);
	const markers = new Map<number, Leaflet.Marker>();
	const byId = new Map<number, SesItem>();
	let prevSel: number | null = null;
	let lastWave: string | null = null;
	let fitted = false;
	/** Поки користувач сам не рухав мапу — підганяємо вид під усі точки при зміні розміру */
	let autoFit = true;

	function fitAll(animate: boolean) {
		if (!map || !L) return;
		const pts = items.filter((i) => i.lat != null && i.lon != null && !i.approximate);
		const use = pts.length ? pts : items.filter((i) => i.lat != null);
		if (!use.length) return;
		const b = L.latLngBounds(use.map((p) => [p.lat!, p.lon!] as [number, number]));
		const narrow = el.clientWidth < 700;
		const opts = {
			paddingTopLeft: [20, narrow ? 190 : 120] as [number, number],
			paddingBottomRight: [20, 20] as [number, number]
		};
		if (animate && !reduced) map.flyToBounds(b, { ...opts, duration: 0.8 });
		else map.fitBounds(b, { ...opts, animate: false });
	}

	const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

	function esc(s: string): string {
		return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
	}

	function look(it: SesItem) {
		if (colorBy === 'class' && it.k_class) {
			const m = kClassMeta(it.k_class);
			return { color: m.color, glyph: m.glyph, word: m.short };
		}
		const c = categoryMeta(it.category_short);
		return { color: c.color, glyph: c.glyph, word: c.label };
	}

	function title(it: SesItem): string {
		const l = look(it);
		const k = colorBy === 'class' && it.k != null ? `, покриття ${kText(it.k)}` : '';
		return `${it.name} — ${l.word}${k}`;
	}

	function clsKey(it: SesItem): string {
		return colorBy === 'class' && it.k_class ? it.k_class : 'cat:' + it.category_short;
	}

	function isMute(it: SesItem): boolean {
		return colorBy === 'class' && (it.k_class === 'Без СЕС' || it.k_class === 'Немає даних');
	}

	function mkHtml(it: SesItem, sel: boolean, wave = false, delay = 0): string {
		const l = look(it);
		return `<span class="sm-mk${isMute(it) ? ' mute' : ''}${wave ? ' wave' : ''}${sel ? ' sel' : ''}" style="--c:${l.color};--d:${delay}ms"><svg viewBox="0 0 10 10" aria-hidden="true"><path d="${l.glyph}"/></svg></span>`;
	}

	/** Колір сегмента кластера за ключем класу */
	function keyColor(k: string): string {
		if (k.startsWith('cat:')) return categoryMeta(k.slice(4)).color;
		return kClassMeta(k as KClass).color;
	}

	function clusterIcon(c: Leaflet.MarkerCluster): Leaflet.DivIcon {
		const counts = new Map<string, number>();
		const kids = c.getAllChildMarkers();
		for (const m of kids) {
			const k = (m.options as { kcls?: string }).kcls ?? '';
			counts.set(k, (counts.get(k) ?? 0) + 1);
		}
		const n = kids.length;
		let acc = 0;
		const stops: string[] = [];
		for (const [k, v] of [...counts].sort((a, b) => b[1] - a[1])) {
			const from = (acc / n) * 360;
			acc += v;
			stops.push(`${keyColor(k)} ${from}deg ${(acc / n) * 360}deg`);
		}
		const size = n < 10 ? 34 : n < 50 ? 40 : 46;
		return L!.divIcon({
			className: 'sm-icon',
			html: `<span class="sm-cl" style="background:conic-gradient(${stops.join(',')});width:${size}px;height:${size}px"><b>${n}</b></span>`,
			iconSize: [size, size]
		});
	}

	/** Роль і підпис для клавіатури; викликати після кожного setIcon (Leaflet створює новий елемент) */
	function a11y(m: Leaflet.Marker, id: number) {
		const icon = m.getElement();
		const it = byId.get(id);
		if (!icon || !it || icon.dataset.a11y) return;
		icon.dataset.a11y = '1';
		icon.setAttribute('role', 'button');
		icon.setAttribute('aria-label', title(it));
		icon.addEventListener('keydown', (e) => {
			if (e.key === 'Enter' || e.key === ' ') {
				e.preventDefault();
				e.stopPropagation();
				onselect?.(id);
			}
		});
	}

	/** Ключ вигляду маркера: якщо не змінився — маркер не чіпаємо (без setIcon і перемальовування) */
	const lookKey = new Map<number, string>();
	function keyOf(it: SesItem): string {
		const l = look(it);
		return `${l.color}|${l.glyph}|${isMute(it) ? 1 : 0}|${title(it)}`;
	}

	/**
	 * Маркери оновлюються різницею за id: нові додаються пакетом, зниклі — пакетом прибираються,
	 * наявні лише змінюють іконку, якщо змінився колір/значок. Раніше кожна зміна фільтра чи режиму
	 * знищувала й створювала всі ~300 маркерів (clearLayers) і заново кластеризувала мапу.
	 */
	function render() {
		if (!L || !map || !layer) return;
		const wave = !reduced && waveKey !== lastWave;
		lastWave = waveKey;
		const pts = items.filter((i) => i.lat != null && i.lon != null) as (SesItem & { lat: number; lon: number })[];
		const keep = new Set(pts.map((p) => p.id));
		const gone: Leaflet.Marker[] = [];
		for (const [id, m] of markers) {
			if (!keep.has(id)) {
				gone.push(m);
				markers.delete(id);
				byId.delete(id);
				lookKey.delete(id);
			}
		}
		const cl = layer as Leaflet.MarkerClusterGroup;
		if (gone.length) {
			if (typeof cl.removeLayers === 'function') cl.removeLayers(gone);
			else for (const m of gone) layer.removeLayer(m);
		}
		const c = map.getCenter();
		// Перша поява — «хвиля» від центру міста, розтягнута не більше ніж на 360 мс
		const far = wave ? Math.max(1e-6, ...pts.map((it) => Math.hypot(it.lat - c.lat, (it.lon - c.lng) * 0.65))) : 1;
		const fresh: Leaflet.Marker[] = [];
		for (const it of pts) {
			const key = keyOf(it);
			const old = markers.get(it.id);
			byId.set(it.id, it);
			const mute = colorBy === 'class' && (it.k_class === 'Без СЕС' || it.k_class === 'Немає даних');
			if (old) {
				if (lookKey.get(it.id) !== key) {
					old.setIcon(L.divIcon({ className: 'sm-icon', html: mkHtml(it, it.id === selectedId), iconSize: [22, 22], iconAnchor: [11, 11] }));
					a11y(old, it.id);
					(old.options as { kcls?: string }).kcls = clsKey(it);
					old.setZIndexOffset(it.id === selectedId ? 1000 : mute ? -500 : 0);
					lookKey.set(it.id, key);
				}
				continue;
			}
			const dist = Math.hypot(it.lat - c.lat, (it.lon - c.lng) * 0.65);
			const delay = wave ? Math.round((dist / far) * 360) : 0;
			const m = L.marker([it.lat, it.lon], {
				icon: L.divIcon({ className: 'sm-icon', html: mkHtml(it, it.id === selectedId, wave, delay), iconSize: [22, 22], iconAnchor: [11, 11] }),
				title: esc(title(it)),
				alt: title(it),
				keyboard: true,
				riseOnHover: true,
				zIndexOffset: it.id === selectedId ? 1000 : mute ? -500 : 0,
				kcls: clsKey(it)
			} as Leaflet.MarkerOptions);
			const id = it.id;
			m.on('click', () => onselect?.(id));
			m.on('add', () => a11y(m, id));
			markers.set(it.id, m);
			lookKey.set(it.id, key);
			fresh.push(m);
		}
		if (fresh.length) {
			if (typeof cl.addLayers === 'function') cl.addLayers(fresh);
			else for (const m of fresh) layer.addLayer(m);
		}
		// Кольори кластерів залежать від режиму — оновлюємо їхні іконки
		if (!fresh.length && !gone.length && typeof cl.refreshClusters === 'function') cl.refreshClusters();
		prevSel = selectedId;
		if (!fitted && pts.length) {
			fitted = true;
			fitAll(false);
		}
	}

	function renderZones() {
		if (!L || !map || !zoneGroup) return;
		zoneGroup.clearLayers();
		if (!showZones) return;
		const renderer = L.svg({ pane: 'zones' });
		for (const z of zones) {
			const color = ZONE_COLORS[z.status ?? 'no_ses'];
			const sel = z.id === selectedZoneId;
			const c = L.circle([z.lat, z.lon], {
				radius: z.radius_m,
				pane: 'zones',
				renderer,
				color,
				weight: sel ? 3 : 1.5,
				opacity: sel ? 0.95 : 0.6,
				fillColor: color,
				fillOpacity: sel ? 0.22 : 0.1,
				bubblingMouseEvents: false
			});
			c.on('click', () => onzone?.(z.id));
			c.bindTooltip(esc(z.name), { sticky: true, direction: 'top' });
			zoneGroup.addLayer(c);
			if ((z.shareable_kwh ?? 0) > 0) {
				const donors = z.members.filter((m) => m.role === 'donor');
				const takers = z.members.filter((m) => m.role === 'taker');
				for (const d of donors)
					for (const t of takers)
						zoneGroup.addLayer(
							L.polyline(
								[
									[d.lat, d.lon],
									[t.lat, t.lon]
								],
								{ pane: 'zones', renderer, color: ZONE_COLORS.surplus, weight: 2, opacity: 0.8, dashArray: '6 6', interactive: false }
							)
						);
			}
		}
	}

	function focusSelected(id: number | null) {
		if (!map || !L) return;
		for (const mid of new Set([prevSel, id])) {
			if (mid == null) continue;
			const it = byId.get(mid);
			const m = markers.get(mid);
			if (!it || !m) continue;
			const sel = mid === id;
			m.setIcon(L.divIcon({ className: 'sm-icon', html: mkHtml(it, sel), iconSize: [22, 22], iconAnchor: [11, 11] }));
			a11y(m, mid);
			m.setZIndexOffset(sel ? 1000 : isMute(it) ? -500 : 0);
		}
		prevSel = id;
		if (id == null) return;
		autoFit = false;
		const m = markers.get(id);
		if (!m) return;
		const z = Math.max(map.getZoom(), 15);
		let target = m.getLatLng();
		if (padBottom) target = map.unproject(map.project(target, z).add([0, padBottom / 2]), z);
		if (reduced) map.setView(target, z, { animate: false });
		else map.flyTo(target, z, { duration: 0.45, easeLinearity: 0.25 });
	}

	export function resetView() {
		autoFit = true;
		fitAll(true);
	}

	// ---- шари меж із ГІС міста ----
	const GIS_TILES = 'https://mbk.rada-poltava.gov.ua/api/gis-rtile';
	type BoundKey = 'districts' | 'starosta' | 'otg';
	const BOUNDS: { key: BoundKey; id: string; label: string; opacity: number }[] = [
		{ key: 'districts', id: '2272630265727681598', label: 'Райони міста', opacity: 0.22 },
		{ key: 'starosta', id: '2464582733746145100', label: 'Старостинські округи', opacity: 0.8 },
		{ key: 'otg', id: '2450807838365189461', label: 'Межа громади', opacity: 0.9 }
	];
	const BOUNDS_KEY = 'insight.bounds';
	function loadBounds(): Record<BoundKey, boolean> {
		const def = { districts: true, starosta: false, otg: true };
		try {
			const v = JSON.parse(localStorage.getItem(BOUNDS_KEY) || 'null');
			return v && typeof v === 'object' ? { ...def, ...v } : def;
		} catch {
			return def;
		}
	}
	let boundsOn = $state<Record<BoundKey, boolean>>(loadBounds());
	let boundsMenu = $state(false);
	const boundLayers: Partial<Record<BoundKey, Leaflet.TileLayer>> = {};
	function applyBounds() {
		if (!map) return;
		for (const b of BOUNDS) {
			const l = boundLayers[b.key];
			if (!l) continue;
			if (boundsOn[b.key] && !map.hasLayer(l)) l.addTo(map);
			if (!boundsOn[b.key] && map.hasLayer(l)) map.removeLayer(l);
		}
		try {
			localStorage.setItem(BOUNDS_KEY, JSON.stringify(boundsOn));
		} catch {
			/* приватний режим */
		}
	}
	function toggleBound(k: BoundKey) {
		boundsOn = { ...boundsOn, [k]: !boundsOn[k] };
		applyBounds();
	}

	onMount(() => {
		let alive = true;
		import('leaflet').then(async (mod) => {
			if (!alive) return;
			L = (mod as unknown as { default?: typeof Leaflet }).default ?? (mod as unknown as typeof Leaflet);
			// markercluster чекає глобальний L
			(window as unknown as { L: typeof Leaflet }).L = L;
			await import('leaflet.markercluster');
			if (!alive) return;
			map = L.map(el, { zoomControl: false, zoomSnap: 0.25, preferCanvas: false }).setView(POLTAVA, 12);
			map.attributionControl.setPrefix(false);
			L.control.zoom({ position: 'bottomright', zoomInTitle: 'Наблизити', zoomOutTitle: 'Віддалити' }).addTo(map);
			// Підкладка OSM, приглушена CSS-фільтром (.sm-tiles): кольорові точки на ній добре видно
			L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
				maxZoom: 19,
				className: 'sm-tiles',
				attribution:
					'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">учасники OpenStreetMap</a>'
			}).addTo(map);
			// Межі з ГІС Полтавської міської ради (растрові XYZ-тайли порталу mbk.rada-poltava.gov.ua)
			map.createPane('bounds').style.zIndex = '250';
			for (const b of BOUNDS) {
				boundLayers[b.key] = L.tileLayer(`${GIS_TILES}/${b.id}/{z}/{x}/{y}.png`, {
					pane: 'bounds',
					opacity: b.opacity,
					maxZoom: 19,
					maxNativeZoom: 18,
					attribution: '<a href="https://mbk.rada-poltava.gov.ua/maps/otg_map" target="_blank" rel="noopener">ГІС Полтавської міської ради</a>'
				});
			}
			applyBounds();
			map.on('dragstart', () => (autoFit = false));
			el.addEventListener('wheel', () => (autoFit = false), { passive: true });
			map.createPane('zones').style.zIndex = '380';
				zoneGroup = L.layerGroup().addTo(map);
				layer = L.markerClusterGroup({
				showCoverageOnHover: false,
				maxClusterRadius: 48,
				disableClusteringAtZoom: 15,
				spiderfyOnMaxZoom: false,
				animate: !reduced,
				iconCreateFunction: clusterIcon
			}).addTo(map);
			map.on('click', () => {
					onselect?.(null);
					onzone?.(null);
				});
			ready = true;
		});
		const ro = new ResizeObserver(() => {
			map?.invalidateSize();
			if (autoFit && selectedId == null) fitAll(false);
		});
		ro.observe(el);
		return () => {
			alive = false;
			ro.disconnect();
			map?.remove();
			map = null;
		};
	});

	$effect(() => {
		// залежності: items, colorBy, waveKey
		void items;
		void colorBy;
		void waveKey;
		if (ready) untrack(render);
	});

	$effect(() => {
		void zones;
		void showZones;
		void selectedZoneId;
		if (ready) untrack(renderZones);
	});

	$effect(() => {
		const id = selectedId;
		if (ready) focusSelected(id);
	});
</script>

<div class="sm-root" bind:this={el} role="region" aria-label="Мапа комунальних об’єктів"></div>
<div class="bt-wrap">
	<button type="button" class="zt" class:on={BOUNDS.some((b) => boundsOn[b.key])} aria-expanded={boundsMenu}
		title="Межі районів і округів (ГІС міста)" onclick={() => (boundsMenu = !boundsMenu)}
		><span class="bd" aria-hidden="true"></span>Межі</button
	>
	{#if boundsMenu}
		<div class="bmenu" role="group" aria-label="Шари меж">
			{#each BOUNDS as b (b.key)}
				<label><input type="checkbox" checked={boundsOn[b.key]} onchange={() => toggleBound(b.key)} /> {b.label}</label>
			{/each}
			<small>ГІС Полтавської міської ради</small>
		</div>
	{/if}
</div>
{#if ontogglezones && zones.length}
	<button
		type="button"
		class="zt"
		class:on={showZones}
		aria-pressed={showZones}
		title={showZones && zoneSummary ? zoneSummary : 'Показати зони обміну надлишком'}
		onclick={ontogglezones}><span class="zd" aria-hidden="true"></span>Зони</button
	>
{/if}

<style>
	.sm-root {
		position: absolute;
		inset: 0;
		background: #e8edf2;
		z-index: 0;
	}
	.sm-root :global(.sm-tiles) {
		filter: grayscale(1) brightness(1.12) contrast(0.72);
	}
	.sm-root :global(.sm-icon) {
		background: none;
		border: 0;
	}
	.sm-root :global(.sm-icon:focus-visible) {
		outline: none;
	}
	.sm-root :global(.sm-icon:focus-visible .sm-mk) {
		box-shadow: 0 0 0 3px #fff, 0 0 0 6px var(--focus, #ffbf47);
	}
	.sm-root :global(.sm-mk) {
		position: relative;
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--c);
		border: 2.5px solid #fff;
		box-sizing: border-box;
		box-shadow:
			0 0 0 1px rgba(15, 35, 65, 0.25),
			0 2px 5px rgba(15, 35, 65, 0.35);
		transition: transform var(--dur-fast) var(--ease-out);
	}
	.sm-root :global(.sm-mk svg) {
		width: 9px;
		height: 9px;
		fill: #fff;
	}
	/* без СЕС / без даних — дрібна сіра точка, щоб не заважала */
	.sm-root :global(.sm-mk.mute) {
		width: 13px;
		height: 13px;
		margin: 4.5px;
		border-width: 2px;
		box-shadow: 0 0 0 1px rgba(15, 35, 65, 0.2);
	}
	.sm-root :global(.sm-mk.mute svg) {
		display: none;
	}
	/* кластер: темне коло з числом, кольорове кільце — частки класів */
	.sm-root :global(.sm-cl) {
		display: grid;
		place-items: center;
		border-radius: 50%;
		box-shadow: 0 2px 6px rgba(15, 35, 65, 0.35);
	}
	.sm-root :global(.sm-cl b) {
		display: grid;
		place-items: center;
		width: calc(100% - 8px);
		height: calc(100% - 8px);
		border-radius: 50%;
		background: var(--navy, #0f2f52);
		border: 2px solid #fff;
		box-sizing: border-box;
		color: #fff;
		font-size: 0.8rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.sm-root :global(.sm-icon:hover .sm-mk) {
		transform: scale(1.25);
	}
	.sm-root :global(.sm-mk.sel) {
		transform: scale(1.5);
		box-shadow:
			0 0 0 3px var(--c),
			0 0 0 9px color-mix(in srgb, var(--c) 25%, transparent),
			0 4px 12px rgba(15, 35, 65, 0.4);
	}
	/* Вибраний маркер: одне кільце-імпульс у момент вибору (елемент створюється заново при виборі) */
	.sm-root :global(.sm-mk.sel::after) {
		content: '';
		position: absolute;
		inset: -3px;
		border-radius: 50%;
		border: 2px solid var(--c);
		pointer-events: none;
		opacity: 0;
		animation: sm-ping 600ms var(--ease-out) 1;
	}
	@keyframes -global-sm-ping {
		from {
			opacity: 0.8;
			transform: scale(1);
		}
		to {
			opacity: 0;
			transform: scale(2.2);
		}
	}
	.sm-root :global(.sm-mk.wave) {
		/* Єдиний «момент» мапи: перша поява маркерів хвилею від центру (≤ 360 мс затримки + 240 мс) */
		animation: sm-in 240ms var(--ease-emph) backwards;
		animation-delay: var(--d);
	}
	@keyframes -global-sm-in {
		from {
			opacity: 0;
			transform: scale(0.4);
		}
		to {
			opacity: 1;
			transform: scale(1);
		}
	}
	.zt {
		position: absolute;
		z-index: 500;
		right: 10px;
		bottom: 92px;
		display: inline-flex;
		align-items: center;
		gap: 6px;
		border: 0;
		border-radius: var(--r-card);
		padding: 8px 12px;
		background: #fff;
		box-shadow: 0 2px 10px rgba(15, 35, 65, 0.18);
		font: inherit;
		font-size: 0.82rem;
		font-weight: 700;
		color: #1a2433;
		cursor: pointer;
	}
	.zt.on {
		background: #e3eefb;
		box-shadow: 0 2px 10px rgba(15, 35, 65, 0.18), inset 0 0 0 2px #1f6fd1;
	}
	.zd {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		border: 2px solid #1f6fd1;
		background: rgba(31, 111, 209, 0.18);
	}
	.bt-wrap {
		position: absolute;
		z-index: 501;
		right: 10px;
		bottom: 140px;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 6px;
	}
	.bt-wrap .zt {
		position: static;
	}
	.bd {
		width: 12px;
		height: 12px;
		border-radius: var(--r-sm);
		border: 2px dashed #6a4fb3;
	}
	.bmenu {
		order: -1;
		display: grid;
		gap: 6px;
		padding: 10px 12px;
		background: #fff;
		border-radius: var(--r-card);
		box-shadow: 0 2px 10px rgba(15, 35, 65, 0.18);
		font-size: 0.82rem;
		font-weight: 600;
		color: #1a2433;
	}
	.bmenu label {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		white-space: nowrap;
	}
	.bmenu small {
		color: #6b7686;
		font-weight: 500;
		font-size: 0.7rem;
	}
	.zt:focus-visible {
		outline: 3px solid var(--focus, #ffbf47);
		outline-offset: 2px;
	}
	.sm-root :global(.leaflet-control-zoom) {
		border: 0;
		box-shadow: 0 2px 10px rgba(15, 35, 65, 0.18);
		border-radius: var(--r-btn);
		overflow: hidden;
	}
	.sm-root :global(.leaflet-control-attribution) {
		font-size: 0.65rem;
	}
	@media (prefers-reduced-motion: reduce) {
		.sm-root :global(.sm-mk) {
			animation: none !important;
			transition: none;
		}
	}
</style>
