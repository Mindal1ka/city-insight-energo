// Ролі користувачів (PLAN_v3, розділ «Ролі»). Правила дзеркалять бекенд —
// бекенд усе одно перевіряє роль сам, тут лише вирішуємо, що показувати в інтерфейсі.
// Використання: import { canSeeSensitive, canEdit, isInternal } from '#lib/roles.ts';

export type RoleId = 'public' | 'energy_manager' | 'data_admin' | 'department' | 'facility_head' | 'finance';
export type Department = 'освіта' | "здоров'я";

export interface RoleInfo {
	id: RoleId;
	name: string;
	description: string;
	needs_building: boolean;
	needs_department: boolean;
}

/** Мінімум полів користувача, потрібний для перевірок (сумісно з User з auth.svelte.ts) */
export interface RoleUser {
	role?: RoleId | string | null;
	building_id?: number | string | null;
	department?: Department | string | null;
}

/** Запасний список ролей — якщо GET /api/auth/roles ще недоступний */
export const ROLES: RoleInfo[] = [
	{ id: 'energy_manager', name: 'Провідний фахівець з енергозабезпечення', description: 'Усі дані, редагування СЕС, завантаження UMUNI', needs_building: false, needs_department: false },
	{ id: 'data_admin', name: 'Адміністратор даних UMUNI', description: 'Перегляд усього, завантаження й якість даних', needs_building: false, needs_department: false },
	{ id: 'department', name: 'Управління (освіта / охорона здоров’я)', description: 'Повні дані закладів свого управління', needs_building: false, needs_department: true },
	{ id: 'facility_head', name: 'Керівник закладу', description: 'Повні дані й редагування СЕС свого закладу', needs_building: true, needs_department: false },
	{ id: 'finance', name: 'Фінансовий орган', description: 'Фінанси й окупність усіх об’єктів', needs_building: false, needs_department: false }
];

export const PUBLIC_ROLE_NAME = 'Публічний перегляд';

export const DEPARTMENTS: { id: Department; label: string; categories: string[] }[] = [
	{ id: 'освіта', label: 'Управління освіти', categories: ['Заклади освіти', 'Дошкільні заклади'] },
	{ id: "здоров'я", label: 'Управління охорони здоров’я', categories: ["Охорона здоров'я"] }
];

export function roleName(role: string | null | undefined): string {
	if (!role || role === 'public') return PUBLIC_ROLE_NAME;
	return ROLES.find((r) => r.id === role)?.name ?? role;
}

/** Підпис ролі для чипа в шапці: «Провідний фахівець з енергозабезпечення», «Управління освіти», «Публічний перегляд» */
export function roleLabel(user: (RoleUser & { role_name?: string | null }) | null | undefined): string {
	if (!user || !user.role || user.role === 'public') return PUBLIC_ROLE_NAME;
	if (user.role === 'department') {
		const d = DEPARTMENTS.find((x) => x.id === user.department);
		if (d) return d.label;
	}
	return roleName(user.role) !== user.role ? roleName(user.role) : user.role_name || user.role;
}

function roleOf(user: RoleUser | null | undefined): string {
	return user?.role || 'public';
}

/** Увійшов під будь-якою службовою роллю (не публічний перегляд) */
export function isInternal(user: RoleUser | null | undefined): boolean {
	return roleOf(user) !== 'public';
}

/** Повний доступ до всього міста: енергоменеджер і адміністратор даних */
export function isCityWide(user: RoleUser | null | undefined): boolean {
	const r = roleOf(user);
	return r === 'energy_manager' || r === 'data_admin';
}

/** Витрати на резервне живлення (/api/generators): енергоменеджер, адміністратор даних, фінанси.
 *  Дзеркало перевірки бекенду — щоб інші ролі не робили заздалегідь приречений запит (403). */
export function canSeeGenerators(user: RoleUser | null | undefined): boolean {
	const r = roleOf(user);
	return r === 'energy_manager' || r === 'data_admin' || r === 'finance';
}

/** Може завантажувати файли UMUNI (сторінка «Оновити дані») */
export function canUpload(user: RoleUser | null | undefined): boolean {
	return isCityWide(user);
}

/** Чи належить категорія (category_short) до управління користувача */
export function inDepartment(user: RoleUser | null | undefined, category: string | null | undefined): boolean {
	if (roleOf(user) !== 'department' || !category) return false;
	const d = DEPARTMENTS.find((x) => x.id === user?.department);
	return !!d && d.categories.includes(category);
}

function sameId(a: unknown, b: unknown): boolean {
	return a !== null && a !== undefined && b !== null && b !== undefined && String(a) === String(b);
}

/**
 * Чутливі дані конкретного об'єкта: акумулятори, автономність, відключення, СЕС по об'єкту
 * (= backend auth.can_see_sensitive).
 * - energy_manager, data_admin — усе;
 * - department — об'єкти своїх категорій (освіта: школи+садочки; здоров'я: медзаклади);
 * - facility_head — лише свій об'єкт;
 * - finance, public — ні.
 * @param cat category_short об'єкта (напр. «Заклади освіти»)
 * @param id  id об'єкта
 */
export function canSeeSensitive(
	user: RoleUser | null | undefined,
	cat: string | null | undefined,
	id: number | string | null | undefined
): boolean {
	const r = roleOf(user);
	if (r === 'energy_manager' || r === 'data_admin') return true;
	if (r === 'department') return inDepartment(user, cat);
	if (r === 'facility_head') return sameId(user?.building_id, id);
	return false;
}

/** Синонім canSeeSensitive: акумулятори, автономність, відключення */
export const canSeeBattery = canSeeSensitive;

/** Наявність СЕС, K, капвитрати по об'єкту — як canSeeSensitive + фінансовий орган (= can_see_ses) */
export function canSeeSes(
	user: RoleUser | null | undefined,
	cat: string | null | undefined,
	id: number | string | null | undefined
): boolean {
	return roleOf(user) === 'finance' || canSeeSensitive(user, cat, id);
}

/** Фінанси й окупність об'єкта (= can_see_finance) */
export function canSeeFinance(
	user: RoleUser | null | undefined,
	cat: string | null | undefined,
	id: number | string | null | undefined
): boolean {
	return roleOf(user) === 'finance' || canSeeSensitive(user, cat, id);
}

/** Редагування даних СЕС і вартості: провідний фахівець з енергозабезпечення — будь-який, керівник закладу — лише свій */
export function canEdit(user: RoleUser | null | undefined, id: number | string | null | undefined): boolean {
	const r = roleOf(user);
	if (r === 'energy_manager') return true;
	if (r === 'facility_head') return sameId(user?.building_id, id);
	return false;
}
