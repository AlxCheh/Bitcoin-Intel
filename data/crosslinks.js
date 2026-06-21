// crosslinks.js — Перекрёстные связи между блоками данных
// Версия: v1.0 · Создан: 2026-06-21
// Используется: MACRO (визуализация) + ANALYSIS (AI-анализатор)

const CROSSLINKS = {

  // ── Приоритеты при конфликте данных ───────────────────────────────────
  priorities: ["onchain", "mining", "institutional", "narrative"],

  // ── Связи по снэпшотам ────────────────────────────────────────────────
  by_snapshot: {
    "Nov 2009": {
      blocks:  ["mining"],
      note:    "Старт эмиссионной кривой — 90.5% не добыто"
    },
    "Dec 2011": {
      blocks:  ["onchain", "narrative"],
      note:    "Silk Road → individuals 5.4% → 30.9% — прямой эффект use case"
    },
    "Feb 2014": {
      blocks:  ["onchain", "institutional", "narrative"],
      note:    "Двойное событие: FBI (governments появляются) + Mt. Gox (lost растёт)"
    },
    "Apr 2016": {
      blocks:  ["onchain", "narrative"],
      note:    "Mt. Gox банкротство оформлено — lost стабилизируется на 10.8%"
    },
    "May 2018": {
      blocks:  ["onchain", "narrative"],
      note:    "Lightning → технологический нарратив → individuals 65.6%"
    },
    "Jul 2020": {
      blocks:  ["mining", "narrative"],
      note:    "3-й халвинг — скорость сокращения эмиссии: −6.4% → −3.3%"
    },
    "Sep 2022": {
      blocks:  ["onchain", "institutional", "narrative"],
      note:    "Celsius/3AC → companies впервые видимы как категория"
    },
    "Oct 2024": {
      blocks:  ["onchain", "institutional", "narrative"],
      note:    "Германия продаёт → ETFs поглощают — демонстрация глубины спроса"
    }
  },

  // ── Связи по категориям владельцев ────────────────────────────────────
  by_category: {
    individuals: {
      related_blocks:  ["narrative"],
      key_events:      ["Dec 2011", "May 2018"],
      note:            "Каждый скачок individuals совпадает с нарративным событием"
    },
    lost_satoshi: {
      related_blocks:  ["narrative"],
      key_events:      ["Feb 2014"],
      note:            "Основной приток потерянных монет — Mt. Gox (Feb 2014)"
    },
    governments: {
      related_blocks:  ["narrative", "institutional"],
      key_events:      ["Feb 2014", "Oct 2024"],
      note:            "Государство входит через изъятие (2014), выходит через продажу (2024)"
    },
    companies: {
      related_blocks:  ["institutional", "narrative"],
      key_events:      ["Sep 2022"],
      note:            "Кризис DeFi → компании ищут альтернативу"
    },
    etfs: {
      related_blocks:  ["institutional", "onchain"],
      key_events:      ["Oct 2024"],
      note:            "ETFs поглощают продажу Германии — новый структурный игрок"
    },
    not_mined: {
      related_blocks:  ["mining"],
      key_events:      ["Jul 2020"],
      note:            "Те же данные что в эмиссионной кривой — разный угол зрения"
    }
  },

  // ── Сильнейшие связки для AI-анализатора ──────────────────────────────
  strong_pairs: [
    {
      pair:  ["onchain", "narrative"],
      note:  "Каждое нарративное событие оставляет след в структуре владения — анализировать вместе всегда"
    },
    {
      pair:  ["mining", "institutional"],
      note:  "Дефицит эмиссии — главный двигатель институционального входа. Причина и следствие"
    },
    {
      pair:  ["narrative", "institutional"],
      note:  "Каждый кризис рождал новый тип держателя: Mt.Gox → lost, Celsius → companies, Германия → ETFs"
    }
  ]

};
