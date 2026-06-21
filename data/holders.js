// holders.js — Распределение Bitcoin по категориям владельцев
// Версия: v1.0 · Создан: 2026-06-21
// Источники: River Financial, BitcoinTreasuries.net, Bitbo.io, Glassnode, Chainalysis

const HOLDERS_DATA = {

  meta: {
    source:       "River Financial, BitcoinTreasuries.net, Bitbo.io, Glassnode, Chainalysis",
    updated:      "2026-06-21",
    total_supply: 21000000,
    video:        "TFTC — Who Holds the Bitcoin?"
  },

  // ── Исторические снэпшоты ──────────────────────────────────────────────
  snapshots: [
    {
      date:        "Nov 2009",
      event:       "Genesis Block Mined",
      total_mined: 1984688,
      categories: {
        individuals:  { pct: 5.4,  btc: 1132837  },
        lost_satoshi: { pct: 4.1,  btc: 851850   },
        governments:  null,
        companies:    null,
        etfs:         null,
        not_mined:    { pct: 90.5, btc: 19015312 }
      }
    },
    {
      date:        "Dec 2011",
      event:       "Silk Road Launches",
      total_mined: 7824533,
      categories: {
        individuals:  { pct: 30.9, btc: 6478820  },
        lost_satoshi: { pct: 6.4,  btc: 1345713  },
        governments:  null,
        companies:    null,
        etfs:         null,
        not_mined:    { pct: 62.7, btc: 13175467 }
      }
    },
    {
      date:        "Feb 2014",
      event:       "FBI Seizes 144K BTC · Mt. Gox Freezes Withdrawals",
      total_mined: 11856903,
      categories: {
        individuals:  { pct: 46.5, btc: 9768614 },
        lost_satoshi: { pct: 9.3,  btc: 1944289 },
        governments:  { pct: 0.7,  btc: 144000  },
        companies:    null,
        etfs:         null,
        not_mined:    { pct: 43.5, btc: 9143097 }
      }
    },
    {
      date:        "Apr 2016",
      event:       "Mt. Gox Files Bankruptcy",
      total_mined: 14671552,
      categories: {
        individuals:  { pct: 58.6, btc: 12308378 },
        lost_satoshi: { pct: 10.8, btc: 2263174  },
        governments:  { pct: 0.5,  btc: 100000   },
        companies:    null,
        etfs:         null,
        not_mined:    { pct: 30.1, btc: 6328448  }
      }
    },
    {
      date:        "May 2018",
      event:       "Lightning Network Launches",
      total_mined: 16247262,
      categories: {
        individuals:  { pct: 65.6, btc: 13777090 },
        lost_satoshi: { pct: 11.3, btc: 2370172  },
        governments:  { pct: 0.5,  btc: 100000   },
        companies:    null,
        etfs:         null,
        not_mined:    { pct: 22.6, btc: 4752738  }
      }
    },
    {
      date:        "Jul 2020",
      event:       "Third Halving (12.5 → 6.25 BTC)",
      total_mined: 17593274,
      categories: {
        individuals:  { pct: 70.6, btc: 14832930 },
        lost_satoshi: { pct: 11.6, btc: 2436318  },
        governments:  { pct: 1.5,  btc: 324026   },
        companies:    null,
        etfs:         null,
        not_mined:    { pct: 16.2, btc: 3406726  }
      }
    },
    {
      date:        "Sep 2022",
      event:       "Celsius / 3AC Collapse",
      total_mined: 18296917,
      categories: {
        individuals:  { pct: 72.7, btc: 15259675 },
        lost_satoshi: { pct: 11.9, btc: 2490541  },
        governments:  { pct: 1.7,  btc: 362311   },
        companies:    { pct: 0.9,  btc: 184390   },
        etfs:         null,
        not_mined:    { pct: 12.9, btc: 2703083  }
      }
    },
    {
      date:        "Oct 2024",
      event:       "Germany Sells 50K BTC",
      total_mined: 18913830,
      categories: {
        individuals:  { pct: 68.9, btc: 14478326 },
        lost_satoshi: { pct: 12.1, btc: 2536489  },
        governments:  { pct: 2.4,  btc: 510864   },
        companies:    { pct: 2.0,  btc: 421313   },
        etfs:         { pct: 4.6,  btc: 966839   },
        not_mined:    { pct: 9.9,  btc: 2086170  }
      }
    }
  ],

  // ── Нарратив: ключевые события ────────────────────────────────────────
  narratives: [
    {
      date:     "Nov 2009",
      event:    "Genesis Block Mined",
      category: "mining",
      category_label: "⛏️ Майнинг",
      effect:   "Старт: 90.5% ещё не добыто, первые individuals появляются"
    },
    {
      date:     "Dec 2011",
      event:    "Silk Road Launches",
      category: "narrative",
      category_label: "📰 Нарратив",
      effect:   "Первый реальный use case → individuals: 5.4% → 30.9%"
    },
    {
      date:     "Feb 2014",
      event:    "FBI Seizes 144K BTC from Silk Road",
      category: "institutional",
      category_label: "🏦 Институционалы",
      effect:   "Государство впервые входит как холдер: 0.7% · 144,000 BTC"
    },
    {
      date:     "Feb 2014",
      event:    "Mt. Gox Freezes Withdrawals",
      category: "narrative",
      category_label: "📰 Нарратив",
      effect:   "Монеты заморожены → Lost & Satoshi начинает расти: 6.4% → 9.3%"
    },
    {
      date:     "May 2018",
      event:    "Lightning Network Launches",
      category: "narrative",
      category_label: "📰 Нарратив",
      effect:   "Технологический нарратив → individuals достигают 65.6%"
    },
    {
      date:     "Jul 2020",
      event:    "Third Halving (12.5 → 6.25 BTC)",
      category: "mining",
      category_label: "⛏️ Майнинг",
      effect:   "Эмиссия замедляется, дефицитный нарратив усиливается"
    },
    {
      date:     "Sep 2022",
      event:    "Celsius / 3AC Collapse",
      category: "institutional",
      category_label: "🏦 Институционалы",
      effect:   "Companies впервые фиксируются как категория: 0.9% · 184,390 BTC"
    },
    {
      date:     "Oct 2024",
      event:    "Germany Sells 50K BTC",
      category: "institutional",
      category_label: "🏦 Институционалы",
      effect:   "Государство продаёт → ETFs поглощают: 4.6% · 966,839 BTC"
    }
  ],

  // ── Эмиссионная кривая ────────────────────────────────────────────────
  emission: [
    { period: "2009→2011", drop_pct: 27.8, years: 2 },
    { period: "2011→2014", drop_pct: 19.2, years: 3 },
    { period: "2014→2016", drop_pct: 13.4, years: 2 },
    { period: "2016→2018", drop_pct: 7.5,  years: 2 },
    { period: "2018→2020", drop_pct: 6.4,  years: 2 },
    { period: "2020→2022", drop_pct: 3.3,  years: 2 },
    { period: "2022→2024", drop_pct: 3.0,  years: 2 }
  ],

  // ── Институционалы: три волны ─────────────────────────────────────────
  institutional_waves: [
    {
      wave:     1,
      year:     2014,
      label:    "Государства",
      event:    "FBI изымает BTC у Silk Road",
      note:     "Вход через изъятие — не добровольный"
    },
    {
      wave:     2,
      year:     2022,
      label:    "Публичные компании",
      event:    "Celsius / 3AC Collapse",
      note:     "Кризис DeFi → институционалы ищут альтернативу"
    },
    {
      wave:     3,
      year:     2024,
      label:    "ETFs & Funds",
      event:    "Спот Bitcoin ETF запущены в США",
      note:     "Самая быстрая и крупная волна"
    }
  ]

};
