// Прожарка.AI — презентация v3 (11 слайдов). Спека: DESIGN.md
const pptxgen = require("../.pytest_tmp/node_modules/pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "Белиевский Давид";
pres.title = "Прожарка.AI — тренажёр для абитуриента и стажёра";

// ---------- palette ----------
const NAVY = "0E2A47";
const CARD_DK = "16324F";
const TEAL = "00A896";
const TEAL_LT = "E3F3F1";
const BG = "F6F8FA";
const WHITE = "FFFFFF";
const MUT = "5B7286";
const ICE = "BFD5E4";
const LINE = "E3EAF0";

const F = "Calibri";
const W = 13.33, MX = 0.6;
const CW = W - MX * 2;

const shadow = () => ({ type: "outer", color: "0E2A47", opacity: 0.14, blur: 7, offset: 2, angle: 90 });

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape("roundRect", {
    x, y, w, h,
    rectRadius: opts.r ?? 0.09,
    fill: { color: opts.fill ?? BG },
    line: opts.border ? { color: opts.border, width: 1 } : { type: "none" },
    shadow: opts.noShadow ? undefined : shadow(),
  });
}

function text(slide, str, x, y, w, h, opts = {}) {
  slide.addText(str, {
    x, y, w, h,
    fontFace: F,
    fontSize: opts.size ?? 14,
    color: opts.color ?? NAVY,
    bold: opts.bold ?? false,
    italic: opts.italic ?? false,
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    lineSpacingMultiple: opts.lh ?? 1.12,
    margin: 0,
    charSpacing: opts.spacing,
  });
}

function title(slide, str, opts = {}) {
  text(slide, str, MX, 0.88, opts.w ?? CW, 0.8, {
    size: opts.size ?? 30, bold: true, color: opts.color ?? NAVY, lh: 1.05,
  });
}

function kicker(slide, str, color = TEAL) {
  text(slide, str.toUpperCase(), MX, 0.42, CW, 0.3, { size: 11, bold: true, color, spacing: 1.5 });
}

function badge(slide, x, y, d, glyph, opts = {}) {
  slide.addShape("ellipse", { x, y, w: d, h: d, fill: { color: opts.fill ?? TEAL }, line: { type: "none" } });
  text(slide, glyph, x, y, d, d, {
    size: opts.size ?? 15, bold: true, color: opts.color ?? WHITE, align: "center", valign: "middle",
  });
}

function row(slide, x, y, w, glyph, head, desc, opts = {}) {
  const d = opts.d ?? 0.46;
  badge(slide, x, y + 0.03, d, glyph, opts);
  text(slide, head, x + d + 0.22, y, w - d - 0.22, 0.34, { size: opts.headSize ?? 16, bold: true });
  text(slide, desc, x + d + 0.22, y + 0.34, w - d - 0.22, opts.descH ?? 0.55, {
    size: opts.descSize ?? 12.5, color: MUT, lh: 1.15,
  });
}

// ---------- media ----------
const MEDIA = "media/";
const imgMenu  = { path: MEDIA + "menu.jpeg",   ar: 1584 / 1597 };
const imgInfo  = { path: MEDIA + "info.png",    ar: 1647 / 2619 };
const imgExam  = { path: MEDIA + "exam.png",    ar: 1647 / 2664 };
const imgReview= { path: MEDIA + "review.png",  ar: 1647 / 2619 };
const imgWeak  = { path: MEDIA + "weak.png",    ar: 1647 / 2619 };

function screenshot(slide, img, x, y, h) {
  const w = h * img.ar;
  card(slide, x - 0.07, y - 0.07, w + 0.14, h + 0.14, { fill: WHITE, r: 0.06 });
  slide.addImage({ path: img.path, x, y, w, h });
  return w;
}

/* ================= SLIDE 1 — title (dark) ================= */
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape("ellipse", { x: 9.9, y: -1.6, w: 5.4, h: 5.4, fill: { color: "12385E", transparency: 55 }, line: { type: "none" } });
  s.addShape("ellipse", { x: -1.4, y: 5.6, w: 4.2, h: 4.2, fill: { color: TEAL, transparency: 82 }, line: { type: "none" } });

  kicker(s, "SK Kids Challenge · кейс «Софтлайн Решения»");
  text(s, "«Прожарка.AI»", MX, 1.15, CW, 1.0, { size: 44, bold: true, color: WHITE });
  text(s, "тренажёр для абитуриента и стажёра", MX, 2.02, CW, 0.6, { size: 26, color: TEAL, bold: true });
  text(s, "Чат-бот в Telegram: отвечает по базе знаний с источниками, гоняет по заданиям\nи объясняет, где ты ошибся.", MX, 2.95, 9.4, 0.85, { size: 15, color: ICE, lh: 1.3 });

  const cw3 = (CW - 0.6) / 3;
  const cards = [
    ["Демо-живой бот", "@prozharka_softline_robot", "можно проверить прямо на защите"],
    ["Автор", "Белиевский Давид\nСергеевич", "категория Senior (15–17 лет)"],
    ["Открытый код", "github.com/Kot3loy/Softline", "промпты, тесты и база — в репозитории"],
  ];
  cards.forEach(([head, val, sub], i) => {
    const x = MX + i * (cw3 + 0.3);
    card(s, x, 4.35, cw3, 1.95, { fill: CARD_DK, r: 0.07 });
    text(s, head, x + 0.28, 4.6, cw3 - 0.5, 0.3, { size: 11.5, bold: true, color: TEAL, spacing: 0.5 });
    text(s, val, x + 0.28, 4.95, cw3 - 0.5, 0.72, { size: val.startsWith("github") ? 13.5 : 15.5, bold: true, color: WHITE, lh: 1.05 });
    text(s, sub, x + 0.28, 5.75, cw3 - 0.5, 0.4, { size: 10.5, color: ICE });
  });
  text(s, "Этапы 1–3 + этап 4 уровня Lead: адаптивность, аналитика, PDF-отчёт", MX, 6.75, CW, 0.3, { size: 11, color: ICE, align: "center" });
}

/* ================= SLIDE 2 — problem ================= */
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  kicker(s, "Зачем это нужно", MUT);
  title(s, "Перед поступлением и первой работой негде ошибиться");

  const cw3 = (CW - 0.56) / 3;
  const probs = [
    ["1", "Один шанс на ответ", "Проверяют один раз и без объяснений — непонятно, что именно подтянуть."],
    ["2", "Советы противоречат друг другу", "Общие фразы из интернета не учитывают твой вуз и твою ситуацию."],
    ["3", "Простой вопрос неловко задать", "Наставник есть не у каждого, а спросить живого человека стеснительно."],
  ];
  probs.forEach(([n, head, desc], i) => {
    const x = MX + i * (cw3 + 0.28);
    card(s, x, 1.55, cw3, 1.95);
    badge(s, x + 0.28, 1.83, 0.44, n);
    text(s, head, x + 0.28, 2.42, cw3 - 0.56, 0.6, { size: 15.5, bold: true, lh: 1.05 });
    text(s, desc, x + 0.28, 3.02, cw3 - 0.56, 0.75, { size: 12, color: MUT, lh: 1.15 });
  });

  const y = 4.05;
  card(s, MX, y, 5.5, 2.35, { fill: BG });
  text(s, "СЕЙЧАС", MX + 0.35, y + 0.3, 3.0, 0.3, { size: 12, bold: true, color: MUT, spacing: 1.5 });
  text(s, "Одна попытка, ноль обратной связи —\nошибка закрепляется.", MX + 0.35, y + 0.75, 4.9, 1.1, { size: 15, color: NAVY, lh: 1.25 });

  text(s, "→", 6.28, y + 0.7, 0.7, 0.9, { size: 30, bold: true, color: TEAL, align: "center" });

  card(s, 7.1, y, 5.63, 2.35, { fill: TEAL_LT, noShadow: true, border: "BFE3DE" });
  text(s, "С «ПРОЖАРКОЙ»", 7.45, y + 0.3, 4.0, 0.3, { size: 12, bold: true, color: TEAL, spacing: 1.5 });
  ["Оценки 0–10 за каждую попытку", "Честный разбор: что верно, что улучшить", "Пример хорошего ответа из практики"].forEach((t, i) => {
    badge(s, 7.45, y + 0.72 + i * 0.52, 0.26, "✓", { size: 11 });
    text(s, t, 7.85, y + 0.7 + i * 0.52, 4.7, 0.35, { size: 13.5, color: NAVY });
  });
  text(s, "Ошибка в тренажёре не стоит ничего — в жизни стоит поступления или стажировки.", MX, 6.75, CW, 0.35, { size: 11.5, color: MUT, align: "center", italic: true });
}

/* ================= SLIDE 3 — modes ================= */
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  kicker(s, "Что умеет бот", MUT);
  title(s, "Один чат закрывает весь путь: вопрос, тренировка, отчёт", { size: 28 });

  const rows = [
    ["?", "Инфо-режим", "Отвечает по базе знаний своими словами, под ответом — блок «📚 Источники»."],
    ["✓", "Экзаменатор", "3, 5 или 10 заданий: тесты с кнопками A–D и открытые вопросы с разбором."],
    ["↑", "Прогресс и отчёт", "Показывает слабые темы, средний балл и выгружает PDF-отчёт."],
  ];
  rows.forEach(([g, head, desc], i) => {
    const y = 1.85 + i * 1.18;
    row(s, MX, y, 6.7, g, head, desc, { headSize: 17, descH: 0.6 });
  });

  screenshot(s, imgMenu, 7.85, 1.5, 4.4);

  const y = 6.2;
  card(s, MX, y, CW, 0.95, { fill: BG });
  text(s, "СЦЕНАРИИ", MX + 0.3, y + 0.32, 1.3, 0.3, { size: 11, bold: true, color: TEAL, spacing: 1.5 });
  const sc = ["🎓  Выбор вуза", "💼  Поиск работы", "🤝  Адаптация в компании", "👑  Лидерство · этап 4"];
  const sw = (CW - 1.9 - 3 * 0.22) / 4;
  sc.forEach((t, i) => {
    const x = MX + 1.75 + i * (sw + 0.22);
    card(s, x, y + 0.16, sw, 0.64, { fill: WHITE, noShadow: true, border: LINE, r: 0.3 });
    text(s, t, x + 0.12, y + 0.16, sw - 0.2, 0.64, { size: 12, bold: true, align: "center", valign: "middle" });
  });
}

/* ============ helper for screenshot feature slides ============ */
function featureSlide(kick, ti, img, side, checkRows) {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  kicker(s, kick, MUT);
  title(s, ti, { size: 28 });

  const imgH = 5.35, imgY = 1.5;
  let imgX, tw, tx;
  if (side === "right") {
    const w = screenshot(s, img, W - MX - imgH * img.ar, imgY, imgH);
    tx = MX; tw = W - MX * 2 - w - 0.75;
  } else {
    const w = screenshot(s, img, MX, imgY, imgH);
    tx = MX + w + 0.75; tw = W - MX - tx;
  }

  checkRows.forEach(([head, desc], i) => {
    const y = 1.85 + i * 1.28;
    badge(s, tx, y + 0.02, 0.46, "✓", { size: 15 });
    text(s, head, tx + 0.68, y - 0.02, tw - 0.68, 0.4, { size: 15.5, bold: true, lh: 1.05 });
    text(s, desc, tx + 0.68, y + 0.38, tw - 0.68, 0.72, { size: 12.5, color: MUT, lh: 1.18 });
  });
  return s;
}

/* ================= SLIDE 4 — info mode ================= */
featureSlide(
  "Инфо-режим", "Ответ по базе знаний, а не из головы модели", imgInfo, "right",
  [
    ["Блок «📚 Источники» под каждым ответом", "Название материала и ссылка на сайт — без путей к файлам на диске."],
    ["Поиск TF-IDF со стеммингом", "Находит похожие формулировки, а не только точные совпадения слов."],
    ["Поиск ограничен сценарием", "Вопрос про вуз не подтянет статью про лидерство — ответ не уводит в сторону."],
    ["Ключевые факты, приятная подача", "Отвечает своими словами, а не копирует статью целиком."],
  ],
);

/* ================= SLIDE 5 — examiner ================= */
featureSlide(
  "Экзаменатор", "Каждое второе задание — тест с кнопками", imgExam, "right",
  [
    ["Тесты A–D и открытые вопросы", "Тест отвечает кнопкой за секунду, открытый вопрос заставляет формулировать."],
    ["Сломанный тест не тормозит сессию", "Модель прислала заглушки «вариант A»? Бот вытащит варианты из текста или заменит тест открытым вопросом."],
    ["Отвечать можно текстом и голосом", "Голосовое распознаётся всегда — озвучивает или печатает, как удобнее."],
    ["Индикатор загрузки", "Пока генерируются задания, показывается стикер — не похоже, что бот завис."],
  ],
);

/* ================= SLIDE 6 — review ================= */
featureSlide(
  "Разбор", "Каждый ответ разбирается по одной честной схеме", imgReview, "left",
  [
    ["Единая схема разбора", "Оценка 0–10, что сделано верно, что улучшить, пример хорошего ответа из практики."],
    ["Выбранный и верный варианты помечены", "И ✅ и ❌ показываются прямо в задании — видно, где промахнулся."],
    ["Переписка остаётся чистой", "Следующее задание убирает прошлое, итоговый отчёт всегда остаётся в чате."],
    ["Бросить на нулях нельзя", "Завершить экзамен без ответов не получится — отчёт всегда честный."],
  ],
);

/* ================= SLIDE 7 — weak topics ================= */
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  kicker(s, "Адаптивность · этап 3", MUT);
  title(s, "Бот помнит слабые темы");

  const imgH = 4.75, imgY = 1.5;
  const w = screenshot(s, imgWeak, W - MX - imgH * imgWeak.ar, imgY, imgH);
  const tx = MX, tw = W - MX * 2 - w - 0.7;

  const steps = [
    ["1", "Записывает", "Тему, баллы и число попыток по каждому кейсу."],
    ["2", "Помечает слабую", "Слабая = больше одной попытки и средний балл ниже 7."],
    ["3", "Возвращается", "Новая сессия начинается с задания по слабому месту."],
    ["4", "Добивает", "В конце задаёт уточняющий вопрос по самой проваленной теме."],
  ];
  steps.forEach(([n, head, desc], i) => {
    const y = 1.85 + i * 1.12;
    badge(s, tx, y + 0.02, 0.46, n);
    text(s, head, tx + 0.68, y, tw - 0.68, 0.34, { size: 15.5, bold: true });
    text(s, desc, tx + 0.68, y + 0.36, tw - 0.68, 0.45, { size: 12.5, color: MUT, lh: 1.15 });
  });

  card(s, tx, 6.35, tw, 0.75, { fill: TEAL_LT, noShadow: true, r: 0.35 });
  text(s, "Пример: два раза промолчал про ограничение ЕГЭ по информатике — третья сессия начнётся с запасных вариантов.", tx + 0.3, 6.35, tw - 0.6, 0.75, { size: 11, color: TEAL, bold: true, valign: "middle", lh: 1.15 });
}

/* ================= SLIDE 8 — PDF & voices ================= */
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  kicker(s, "Результат всегда с собой", MUT);
  title(s, "Результат остаётся с тобой: PDF, голос и два языка");

  const cw2 = (CW - 0.35) / 2, ch = 2.35;
  const blocks = [
    ["PDF-отчёт", "Задания, ответы, баллы, разбор, рекомендации, источники и дисклеймер — один файл со всей сессией."],
    ["Кнопка или /export", "Выгрузка в любой момент, файл приходит прямо в чат. Отчёт остаётся в переписке."],
    ["Голосовые всегда", "Вход — всегда, без настройки. Озвучка ответов нейроголосом включается тумблером «Голос»."],
    ["RU/EN и inline-поиск", "Интерфейс переключается на английский, а базу можно искать прямо из поля ввода чата."],
  ];
  blocks.forEach(([head, desc], i) => {
    const x = MX + (i % 2) * (cw2 + 0.35);
    const y = 1.7 + Math.floor(i / 2) * (ch + 0.4);
    card(s, x, y, cw2, ch);
    badge(s, x + 0.32, y + 0.32, 0.46, ["📄", "📤", "🎙", "🌐"][i], { fill: WHITE, color: NAVY, size: 17 });
    text(s, head, x + 0.95, y + 0.35, cw2 - 1.3, 0.4, { size: 16.5, bold: true });
    text(s, desc, x + 0.32, y + 1.05, cw2 - 0.64, 1.1, { size: 12.5, color: MUT, lh: 1.22 });
  });
  text(s, "Проверяющему: достаточно пройти 5 шагов — /start → сценарий → вопрос в инфо-режиме → 3 задания в экзаменаторе → выгрузка PDF.", MX, 6.85, CW, 0.35, { size: 11.5, color: MUT, align: "center", italic: true });
}

/* ================= SLIDE 9 — engineering ================= */
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  kicker(s, "Под капотом", MUT);
  title(s, "Инженерное качество проверено 406 автотестами");

  const flow = ["Telegram", "aiogram 3", "поиск TF-IDF", "GigaChat-2", "SQLite и PDF"];
  const fw = 1.92, gap = 0.5, y = 1.55, fh = 0.62;
  const total = flow.length * fw + (flow.length - 1) * gap;
  const x0 = MX + (CW - total) / 2;
  flow.forEach((t, i) => {
    const x = x0 + i * (fw + gap);
    card(s, x, y, fw, fh, { fill: BG, noShadow: true, border: TEAL, r: 0.16 });
    text(s, t, x, y, fw, fh, { size: 13, bold: true, align: "center", valign: "middle" });
    if (i < flow.length - 1) text(s, "→", x + fw + 0.02, y, gap, fh, { size: 16, bold: true, color: TEAL, align: "center", valign: "middle" });
  });

  const sw3 = (CW - 0.56) / 3, sy = 2.7, sh = 2.7;
  const stats = [
    ["76", "файлов в базе знаний", "30 кейсов, 22 вуза, 16 компаний, 4 разбора интервью и 4 материала по лидерству."],
    ["70 из 76", "файлов с источником", "Прямые рабочие ссылки на официальные сайты вузов, компаний, hh.ru, habr, vc.ru, РИА."],
    ["406", "автотестов на pytest", "Все проходят, а CI на каждом коммите гоняет ещё ruff и mypy."],
  ];
  stats.forEach(([num, head, desc], i) => {
    const x = MX + i * (sw3 + 0.28);
    card(s, x, sy, sw3, sh);
    text(s, num, x + 0.3, sy + 0.25, sw3 - 0.6, 1.0, { size: 52, bold: true, color: TEAL });
    text(s, head, x + 0.3, sy + 1.35, sw3 - 0.6, 0.35, { size: 14.5, bold: true });
    text(s, desc, x + 0.3, sy + 1.75, sw3 - 0.6, 0.8, { size: 11.5, color: MUT, lh: 1.2 });
  });

  card(s, MX, 5.85, CW, 0.95, { fill: BG, noShadow: true });
  text(s, [
    { text: "Python 3.12 · aiogram 3 · GigaChat (Сбер) · SQLite v5 · ", options: { color: NAVY } },
    { text: "SpeechRecognition + edge-tts", options: { color: NAVY, bold: true } },
    { text: " · fpdf2 · версионируемый реестр промптов в YAML · ruff + CI", options: { color: NAVY } },
  ], MX + 0.35, 5.85, CW - 0.7, 0.95, { size: 12.5, valign: "middle", lh: 1.25 });
}

/* ================= SLIDE 10 — ethics & safety (new) ================= */
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  kicker(s, "Безопасность", MUT);
  title(s, "Бот безопасен для школьника");

  const cw3 = (CW - 0.56) / 3;
  const cards = [
    ["1", "Не собирает личные данные", "Не просит телефон, адрес и ФИО прямо предупреждает: их присылать не нужно."],
    ["2", "Защита от prompt-injection", "Ввод очищается: «ignore previous instructions» и русские аналоги вырезаются, лимит — 2000 символов."],
    ["3", "Честный дисклеймер", "В каждом разборе и в PDF-отчёте: рекомендации информационного характера."],
  ];
  cards.forEach(([n, head, desc], i) => {
    const x = MX + i * (cw3 + 0.28);
    card(s, x, 1.7, cw3, 2.6);
    badge(s, x + 0.3, 2.0, 0.46, n);
    text(s, head, x + 0.3, 2.6, cw3 - 0.6, 0.6, { size: 15.5, bold: true, lh: 1.05 });
    text(s, desc, x + 0.3, 3.2, cw3 - 0.6, 0.95, { size: 12, color: MUT, lh: 1.18 });
  });

  card(s, MX, 4.75, CW, 1.0, { fill: TEAL_LT, noShadow: true, border: "BFE3DE" });
  text(s, "Данные берутся только из открытых источников, источник указывается рядом с фактами.", MX + 0.4, 4.75, CW - 0.8, 1.0, { size: 15, bold: true, color: NAVY, align: "center", valign: "middle" });

  text(s, "Персональные данные школьника не нужны боту ни на одном этапе — от /start до PDF-отчёта.", MX, 6.4, CW, 0.35, { size: 11.5, color: MUT, align: "center", italic: true });
}

/* ================= SLIDE 11 — finale (dark) ================= */
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape("ellipse", { x: 10.6, y: 4.9, w: 4.6, h: 4.6, fill: { color: "12385E", transparency: 55 }, line: { type: "none" } });

  kicker(s, "Честно о проблемах и решениях");
  text(s, "Проблемы демо-хостинга уже решены", MX, 0.95, CW, 0.7, { size: 30, bold: true, color: WHITE });

  const cw3 = (CW - 0.56) / 3, y = 2.0, h = 2.75;
  const blocks = [
    ["Хостинг засыпает, база обнуляется", "Бесплатный Render пересоздаёт контейнер при редеплое, без трафика сервис спит."],
    ["SSL GigaChat не проходил проверку", "Сберский сертификат отклонялся — часть запросов не уходила."],
    ["Модель может ошибаться", "ИИ врёт уверенно — поверивший пользователь ошибается дорого."],
  ];
  const solutions = [
    "Монитор UptimeRobot пингует /health каждые 5 минут — сервис не засыпает.",
    "Настройка GIGACHAT_VERIFY_SSL_CERTS возвращает рабочие запросы.",
    "Бот валидирует ответы и добавляет дисклеймер в каждом разборе.",
  ];
  blocks.forEach(([head, prob], i) => {
    const x = MX + i * (cw3 + 0.28);
    card(s, x, y, cw3, h, { fill: CARD_DK, r: 0.07 });
    text(s, head, x + 0.3, y + 0.3, cw3 - 0.6, 0.65, { size: 14.5, bold: true, color: WHITE, lh: 1.1 });
    text(s, "ПРОБЛЕМА", x + 0.3, y + 1.0, cw3 - 0.6, 0.25, { size: 9.5, bold: true, color: "7E97AC", spacing: 1.5 });
    text(s, prob, x + 0.3, y + 1.27, cw3 - 0.6, 0.75, { size: 11.5, color: ICE, lh: 1.18 });
    text(s, "РЕШЕНИЕ", x + 0.3, y + 2.0, cw3 - 0.6, 0.25, { size: 9.5, bold: true, color: TEAL, spacing: 1.5 });
    text(s, solutions[i], x + 0.3, y + 2.27, cw3 - 0.6, 0.9, { size: 11.5, color: WHITE, lh: 1.18 });
  });

  card(s, MX, 5.3, CW, 0.85, { fill: "0F324D", noShadow: true, r: 0.42 });
  text(s, "Итог: отвечает с источниками, разбирает ошибки и помнит слабые темы", MX + 0.4, 5.3, CW - 0.8, 0.85, { size: 15.5, bold: true, color: WHITE, align: "center", valign: "middle" });

  const lin3 = ["Открытый код · github.com/Kot3loy/Softline", "Демо · @prozharka_softline_robot в Telegram", "Полностью рабочий демонстрационный режим"];
  lin3.forEach((t, i) => {
    const x = MX + i * ((CW - 0.56) / 3 + 0.28);
    text(s, t, x, 6.55, (CW - 0.56) / 3, 0.35, { size: 11.5, color: i === 1 ? TEAL : ICE, align: "center" });
  });
}

pres.writeFile({ fileName: "Softlinebot.pptx" }).then(() => console.log("written Softlinebot.pptx"));
