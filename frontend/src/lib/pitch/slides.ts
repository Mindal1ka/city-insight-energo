// Презентація /pitch — увесь текст і всі цифри тут. Редагуйте цей файл, сторінка перемальовується сама.
// Цифри звірені з API 20.11.2026 (джерело — у коментарі біля кожного блоку). «ДЕМО» = змодельовані дані.

export const BRAND = 'City Insight Map';
export const FOOTER = 'City Insight Map · Полтавська громада · 2026';

export type Bar = { label: string; value: number; display: string };
export type Fig = { value: string; unit?: string; label: string; demo?: boolean };
export type IconName =
	| 'bolt' | 'book' | 'cross' | 'wallet' | 'building' | 'sun' | 'coin' | 'clock'
	| 'gov' | 'culture' | 'sport' | 'house';

// Хто користується платформою (список від команди): слайд 2 і слайд 4
export const USERS: { label: string; icon: IconName }[] = [
	{ label: 'Виконавчий комітет', icon: 'gov' },
	{ label: 'Управління освіти', icon: 'book' },
	{ label: 'Управління охорони здоров’я', icon: 'cross' },
	{ label: 'Управління культури', icon: 'culture' },
	{ label: 'Управління молоді та спорту', icon: 'sport' },
	{ label: 'Департамент ЖКГ', icon: 'house' },
	{ label: 'Фінансове управління', icon: 'wallet' },
	{ label: 'Керівники закладів', icon: 'building' }
];

export type Slide =
	| {
			kind: 'title';
			logos: { banner: string; bannerAlt: string; partners: string; gerb: string; emblem: string };
			title: string;
			tagline: string;
			subtitle: string;
			lead: string;
			track: string;
			direction: string;
			teamTitle: string;
			team: { name: string; role: string }[];
	  }
	| {
			kind: 'problem';
			title: string;
			stats: Fig[];
			problemTitle: string;
			problems: string[];
			valueTitle: string;
			values: string[];
			usersTitle: string;
			users: { label: string; icon: IconName }[];
	  }
	| {
			kind: 'profile';
			title: string;
			lead: string;
			figures: Fig[];
			chartTitle: string;
			bars: Bar[];
			defectsTitle: string;
			defects: { value: string; label: string }[];
	  }
	| {
			kind: 'flow';
			title: string;
			sources: { name: string; detail: string }[];
			coreTitle: string;
			core: string[];
			stats: Fig[];
			rolesTitle: string;
			rolesSub: string;
			roles: { label: string; icon: IconName }[];
	  }
	| {
			kind: 'finance';
			title: string;
			lead: string;
			years: { year: string; plan: number; fact: number; planText: string; factText: string; factNote: string }[];
			figures: Fig[];
			note: string;
	  }
	| {
			kind: 'solar';
			title: string;
			kTitle: string;
			kFormula: string;
			figures: Fig[];
			months: { m: string; k: number }[];
			threshold: number;
			shot: string;
			shotCaption: string;
			autonomy: {
				title: string;
				value: string;
				label: string;
				bars: { label: string; hours: number; display: string }[];
				target: string;
				outage: string;
			};
	  }
	| {
			kind: 'econ';
			title: string;
			params: { name: string; value: string; source: string }[];
			result: Fig[];
			plainTitle: string;
			plain: { icon: IconName; big: string; text: string }[];
	  }
	| {
			kind: 'poc';
			title: string;
			subtitle: string;
			realTitle: string;
			real: string[];
			demoTitle: string;
			demo: string[];
			legendReal: string;
			legendDemo: string;
	  }
	| {
			kind: 'plan';
			title: string;
			lead: string;
			steps: { when: string; title: string; text: string }[];
			closing: string;
	  }
	| {
			kind: 'growth';
			title: string;
			items: { title: string; text: string; value: string[] }[];
	  };

export const SLIDES: Slide[] = [
	// 1 — повний банер хакатону (вже містить смугу партнерів) + назва і команда
	{
		kind: 'title',
		logos: {
			banner: '/pitch/hackathon-banner.webp',
			bannerAlt: 'Poltava Open Data Hackathon, 19–20 листопада',
			// смуга партнерів окремо на титулі не показується — вона вже є на банері
			partners: '/pitch/partners-poltava.png',
			gerb: '/pitch/gerb-poltava.svg',
			emblem: '/pitch/emblema-poltava-mr.png'
		},
		title: 'CITY INSIGHT MAP',
		tagline: 'Energy Intelligence & Decision Support Platform',
		subtitle: 'Інтегрована аналітична платформа енергетичної стійкості громади',
		lead: 'Від розрізнених енергетичних даних — до обґрунтованих управлінських рішень.',
		track: 'Енергетичний менеджмент та енергетична стійкість',
		direction: 'Сонячна генерація — потенціал і моніторинг СЕС',
		teamTitle: 'Команда Insight',
		team: [
			{ name: 'Іван Мендєлєєв', role: 'Фронтенд і бекенд платформи' },
			{ name: 'Галина Михайленко', role: 'Продукт і бізнес-аналітика' },
			{ name: 'Дмитро Лєщин', role: 'Веб-розробка, менеджмент проєкту' },
			{ name: 'Дмитро Василенко', role: 'Технічна консультація, тестування' },
			{ name: 'Микола Фесік', role: 'Кібербезпека' }
		]
	},
	// 2 — цифри: /api/summary (311, 4 874 090 кВт·год, 896 дефектів), 7 джерел — слайд 4
	{
		kind: 'problem',
		title: 'Аналітика та моделювання енергетичних ресурсів',
		stats: [
			{ value: '311', label: 'будівель громади' },
			{ value: '4,87', unit: 'млн кВт·год', label: 'електроенергії за 2025 рік' },
			{ value: '896', label: 'дефектів і аномалій у даних' },
			{ value: '7', label: 'розрізнених джерел даних' }
		],
		problemTitle: 'Проблема',
		problems: [
			'Немає цілісної аналітичної інформації про енергетичні об’єкти громади',
			'Невідомі реальні обсяги генерації та споживання енергії',
			'Дані розподілені між різними інформаційними системами',
			'Складно комплексно оцінити енергетичний потенціал',
			'Важко ухвалювати обґрунтовані управлінські рішення'
		],
		valueTitle: 'Ключова цінність',
		values: [
			'Об’єднання розрізнених енергетичних даних у цілісну аналітичну картину.',
			'Перетворення даних на практичну цінність для громади.',
			'Виявлення потенціалу оптимізації генерації та споживання енергії.',
			'Моделювання сценаріїв і підтримка обґрунтованих управлінських та інвестиційних рішень.',
			'Трансформація цифрових рішень на дієвий інструмент сталого розвитку та енергетичної стійкості громади.',
			'Внесок у досягнення енергетичних та кліматичних цілей Полтави до 2030 року: скорочення викидів CO₂ на 23%, зменшення споживання первинної енергії на 8,5% та збільшення частки ВДЕ до 12,3%.'
		],
		usersTitle: 'Хто користується',
		users: USERS
	},
	// 3 — /api/summary, /api/ses?period=year (споживання по категоріях), /api/defects
	{
		kind: 'profile',
		title: 'Енергетичний профіль будівель',
		lead: 'Реальні дані UMUNI за 2025 рік: реєстр, річне споживання, лічильники.',
		figures: [
			{ value: '311', label: 'будівель громади в одному реєстрі' },
			{ value: '4,87', unit: 'млн кВт·год', label: 'електроенергії спожито у 2025 році' },
			{ value: '154', unit: 'кВт·год/м²', label: 'медіана питомого споживання садків; громадських будівель — 55 (усі ресурси)' },
			{ value: '896', label: 'дефектів і аномалій даних знайдено у 304 будівлях' }
		],
		chartTitle: 'Електроенергія 2025 за категоріями, тис. кВт·год',
		bars: [
			{ label: 'Заклади освіти', value: 2513, display: '2 513' },
			{ label: 'Дошкільні заклади', value: 904, display: '904' },
			{ label: 'Охорона здоров’я', value: 829, display: '829' },
			{ label: 'Громадські будівлі', value: 577, display: '577' },
			{ label: 'Спортивні споруди', value: 44, display: '44' },
			{ label: 'Житлові будинки', value: 6, display: '6' }
		],
		defectsTitle: 'Що виправити в UMUNI — список формується автоматично',
		defects: [
			{ value: '277', label: 'будівель без координат' },
			{ value: '181', label: 'без року забудови' },
			{ value: '65', label: 'лічильник є, споживання немає' }
		]
	},
	// 4 — /api/summary (1 097 лічильників)
	{
		kind: 'flow',
		title: 'Від розрізнених систем — до єдиного центру енергетичної аналітики',
		sources: [
			{ name: 'UMUNI', detail: 'будівлі, споживання, лічильники' },
			{ name: 'СЕнМ', detail: 'стан системи енергоменеджменту' },
			{ name: 'openbudget', detail: 'КЕКВ 2273, план і касові видатки' },
			{ name: 'spending.gov.ua', detail: 'договори й оплати' },
			{ name: 'PVGIS', detail: 'сонячний ресурс Полтави' },
			{ name: 'Полтаваобленерго', detail: 'графіки відключень' },
			{ name: 'ГІС', detail: 'межі громади й районів' }
		],
		coreTitle: 'City Insight Map',
		core: ['Імпорт XLSX без розробника', 'Перевірка якості даних', 'Розрахунок індексу K'],
		stats: [
			{ value: '7', label: 'джерел' },
			{ value: '311', label: 'будівель' },
			{ value: '1 097', label: 'лічильників' },
			{ value: '8', label: 'груп користувачів' }
		],
		rolesTitle: 'Хто користується',
		rolesSub: 'У кожного — індивідуальний доступ до даних',
		roles: USERS
	},
	// 5 — /api/budget-real (openbudget), /api/departments
	{
		kind: 'finance',
		title: 'Фінансовий контроль: планові та фактичні показники',
		lead: 'Видатки на електроенергію (КЕКВ 2273), бюджет Полтавської громади, openbudget.gov.ua.',
		years: [
			{ year: '2025', plan: 72.3, fact: 63.3, planText: '72,3 млн грн', factText: '63,3 млн грн', factNote: '88 % плану' },
			{ year: '2026', plan: 92.5, fact: 41.9, planText: '92,5 млн грн', factText: '41,9 млн грн', factNote: 'сплачено за січень–вересень' }
		],
		figures: [
			{ value: '11,57', unit: 'грн/кВт·год', label: 'фактична ціна 2025: касові видатки ÷ споживання UMUNI' },
			{ value: '63,5 %', label: 'річних лімітів використано станом на листопад', demo: true },
			{ value: '48', label: 'об’єктів уже перевищили місячний ліміт', demo: true }
		],
		note: 'План і факт — реальні дані openbudget. Ліміти по закладах — модель (ДЕМО) до отримання лімітів від фінансового управління.'
	},
	// 6 — /api/ses?period=year|month; автономність — /api/independence (community, categories)
	{
		kind: 'solar',
		title: 'Сонячна генерація, графіки відключень та енергетична карта громади',
		kTitle: 'Індекс K',
		kFormula: 'K = згенеровано ÷ спожито. K ≥ 0,8 — ефективно, менше — не вистачає.',
		figures: [
			{ value: '56', label: 'об’єктів із СЕС', demo: true },
			{ value: '26 / 30', label: 'ефективно / не вистачає за рік', demo: true },
			{ value: '0,80', label: 'K за рік; червень 1,73, листопад 0,28', demo: true }
		],
		months: [
			{ m: 'січ', k: 0.28 },
			{ m: 'лют', k: 0.42 },
			{ m: 'бер', k: 0.71 },
			{ m: 'кві', k: 0.91 },
			{ m: 'тра', k: 1.1 },
			{ m: 'чер', k: 1.73 },
			{ m: 'лип', k: 2.28 },
			{ m: 'сер', k: 2.12 },
			{ m: 'вер', k: 0.91 },
			{ m: 'жов', k: 0.62 },
			{ m: 'лис', k: 0.28 },
			{ m: 'гру', k: 0.19 }
		],
		threshold: 0.8,
		shot: '/pitch/shot-map.png',
		shotCaption: 'Енергетична карта: 311 будівель, колір — клас K',
		autonomy: {
			title: 'Час автономності',
			value: '3,5',
			label: 'години протримається типовий заклад на акумуляторі',
			bars: [
				{ label: 'Охорона здоров’я', hours: 8.6, display: '8,6 год' },
				{ label: 'Дошкільні заклади', hours: 3.5, display: '3,5 год' },
				{ label: 'Заклади освіти', hours: 2.5, display: '2,5 год' }
			],
			target: 'ціль для лікарень — 8 год',
			outage: 'Щодня беремо графіки відключень Полтаваобленерго і бачимо, хто протримається, а кому потрібна допомога.'
		}
	},
	// 7 — backend/app/solar.py (/api/solar params), /api/ses?period=year totals, METHODOLOGY.md
	{
		kind: 'econ',
		title: 'Економічні параметри та розрахункові коефіцієнти',
		params: [
			{ name: 'Тариф', value: '12,0 грн/кВт·год', source: 'Полтаваенергозбут, Prozorro, факт 2025' },
			{ name: 'Виробіток 1 кВт за рік', value: '1 151 кВт·год', source: 'PVGIS, Полтава' },
			{ name: 'Втрати', value: '8 %', source: 'коефіцієнт 0,92' },
			{ name: 'Пороги K', value: '0,8 / 1,2', source: 'не вистачає / ефективно / надлишок' },
			{ name: 'Вартість нової СЕС', value: '22 000 грн/кВт', source: '+ 60 000 грн на об’єкт' }
		],
		result: [
			{ value: '40,0', unit: 'млн грн', label: 'вкладено в 56 станцій', demo: true },
			{ value: '10,5', unit: 'млн грн/рік', label: 'економія на оплаті електроенергії', demo: true },
			{ value: '≈ 3,8', unit: 'року', label: 'окупність', demo: true }
		],
		plainTitle: 'Простими словами',
		plain: [
			{ icon: 'sun', big: '≈ 1 150 кВт·год', text: 'дає 1 кВт сонячних панелей за рік у Полтаві' },
			{ icon: 'coin', big: '12 грн', text: 'коштує 1 кВт·год з мережі — стільки економить кожна власна' },
			{ icon: 'clock', big: 'Окупність', text: 'за скільки років економія повертає вкладені гроші' }
		]
	},
	// 8
	{
		kind: 'poc',
		title: 'Концепт-прототип',
		subtitle: 'Що змодельовано на етапі Proof of Concept та дані',
		realTitle: 'Реальні дані',
		real: [
			'UMUNI: 311 будівель',
			'Споживання 2025–2026',
			'1 097 лічильників',
			'СЕнМ: 209 будівель',
			'openbudget, КЕКВ 2273',
			'spending.gov.ua',
			'PVGIS: сонячний ресурс',
			'Графіки відключень ПОЕ',
			'ГІС: межі громади'
		],
		demoTitle: 'Змодельовано (ДЕМО)',
		demo: ['Реєстр СЕС', 'Акумулятори', 'Генератори', 'Погодинна телеметрія', 'Вартість станцій'],
		legendReal: 'зелений — реальні дані',
		legendDemo: 'жовтий — змодельовано'
	},
	// 9
	{
		kind: 'plan',
		title: 'Перехід від DEMO до реальної аналітики',
		lead: 'Кожен крок замінює змодельований шар справжніми даними — без переробки системи.',
		steps: [
			{ when: 'Місяць 1', title: 'Реєстр СЕС від закладів', text: 'Форма вже є: заклад вносить панелі, інвертор, акумулятори.' },
			{ when: 'Місяці 1–2', title: 'Підключення інверторів', text: 'Deye і Huawei OpenAPI — генерація без ручного введення.' },
			{ when: 'Місяці 2–3', title: 'Погодинні лічильники', text: 'Дані комерційного обліку замість сезонного профілю.' },
			{ when: 'Місяці 3–4', title: 'Пілот на 10 закладах', text: 'Звірка моделі з фактом, налаштування порогів.' },
			{ when: 'Місяць 5', title: 'Публічна сторінка громади', text: 'Зведені цифри для мешканців — без адрес і резервного живлення.' },
			{
				when: 'Після пілоту',
				title: 'ТЕО і закупівлі СЕС',
				text: 'Можливість використання платформи для техніко-економічного обґрунтування та формування закупівель обладнання для СЕС.'
			}
		],
		closing: 'City Insight Map — від точних даних до енергетичної стійкості громади.'
	},
	// 10
	{
		kind: 'growth',
		title: 'Потенціал розвитку та масштабування City Insight Map',
		items: [
			{
				title: 'Корпоративний сектор: енергетична аналітика для великого бізнесу',
				text: 'Адаптація платформи для великих енергоспоживачів — торговельних мереж (АТБ, «Маркетопт» та інших), логістичних комплексів, виробничих підприємств і комерційної нерухомості.',
				value: ['Єдиний моніторинг', 'Менші витрати на енергію', 'Потенціал сонячної генерації', 'Сценарії енергозабезпечення']
			},
			{
				title: 'Енергетична автономність: інтелектуальне управління взаємопов’язаними об’єктами',
				text: 'Розвиток функціональності для комплексів об’єктів зі спільною інфраструктурою, які можуть координувати власну генерацію, накопичення та споживання електроенергії.',
				value: ['Розподіл ресурсів', 'Автономність', 'Стійкість об’єктів']
			},
			{
				title: 'Міжнародне масштабування: Energy Independence as a Service',
				text: 'Розвиток City Insight Map як масштабованого ІТ-продукту для міжнародних ринків із фокусом на енергетичну незалежність, децентралізовану генерацію та інтелектуальне управління енергетичними ресурсами.',
				value: ['Різні енергоринки', 'Муніципалітети й бізнес', 'Гнучка інфраструктура']
			}
		]
	}
];
