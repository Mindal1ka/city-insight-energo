/**
 * Глобальний темп анімацій: усі програмні анімації (Web Animations API, а отже й переходи Svelte,
 * animate:flip та дії з motion.ts) сповільнюються в MOTION_SCALE раз. Короткі відгуки на натискання
 * (≤ 100 мс) лишаються як є, щоб інтерфейс не здавався загальмованим.
 */
export const MOTION_SCALE = 2;
const PRESS_MS = 100;

if (typeof Element !== 'undefined' && !(Element.prototype as unknown as { __motionScaled?: boolean }).__motionScaled) {
	const orig = Element.prototype.animate;
	Element.prototype.animate = function (keyframes, options) {
		if (typeof options === 'number') {
			options = options > PRESS_MS ? options * MOTION_SCALE : options;
		} else if (options && typeof options === 'object') {
			const o = { ...options } as KeyframeAnimationOptions;
			const d = typeof o.duration === 'number' ? o.duration : 0;
			if (d > PRESS_MS && Number.isFinite(d) && o.iterations !== Infinity) {
				o.duration = d * MOTION_SCALE;
				if (typeof o.delay === 'number') o.delay *= MOTION_SCALE;
			} else if (d === 0 && typeof o.delay === 'number' && o.delay > 0) {
				o.delay *= MOTION_SCALE; // «порожня» анімація-затримка перед основною (так робить Svelte)
			}
			options = o;
		}
		return orig.call(this, keyframes, options);
	};
	(Element.prototype as unknown as { __motionScaled?: boolean }).__motionScaled = true;
}
