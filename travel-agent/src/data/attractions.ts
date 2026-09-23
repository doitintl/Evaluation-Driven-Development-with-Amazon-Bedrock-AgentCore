import type { Attraction } from "./types.js";

export const attractions: Attraction[] = [
  {
    name: "Grand Museum of Luminara",
    description:
      "A sprawling museum housing centuries of Luminaran history, from ancient artifacts to modern art installations.",
    openTime: "09:00",
    closeTime: "18:00",
    closureDays: ["Monday"],
    visitDurationMinutes: 120,
    ticketPrice: 25,
    advanceBookingRequired: false,
    category: "history",
  },
  {
    name: "Royal Palace",
    description:
      "The former seat of the Luminaran monarchy, featuring opulent throne rooms and manicured courtyards.",
    openTime: "10:00",
    closeTime: "17:00",
    closureDays: ["Tuesday"],
    visitDurationMinutes: 90,
    ticketPrice: 35,
    advanceBookingRequired: true,
    category: "history",
  },
  {
    name: "Skyline Tower",
    description:
      "A 360-degree observation deck offering panoramic views of the city and surrounding coastline.",
    openTime: "08:00",
    closeTime: "22:00",
    closureDays: [],
    visitDurationMinutes: 60,
    ticketPrice: 20,
    advanceBookingRequired: false,
    category: "entertainment",
  },
  {
    name: "Botanical Gardens",
    description:
      "Lush tropical and temperate gardens spread across 30 acres with rare plant species from around the world.",
    openTime: "07:00",
    closeTime: "19:00",
    closureDays: [],
    visitDurationMinutes: 90,
    ticketPrice: 12,
    advanceBookingRequired: false,
    category: "nature",
  },
  {
    name: "Old Quarter Walking Tour",
    description:
      "A guided stroll through cobblestone streets lined with historic buildings, local shops, and street performers.",
    openTime: "09:00",
    closeTime: "16:00",
    closureDays: ["Sunday"],
    visitDurationMinutes: 150,
    ticketPrice: 18,
    advanceBookingRequired: false,
    category: "culture",
  },
  {
    name: "Luminara Art Gallery",
    description:
      "A contemporary gallery showcasing rotating exhibitions from local and international artists.",
    openTime: "10:00",
    closeTime: "18:00",
    closureDays: ["Monday", "Wednesday"],
    visitDurationMinutes: 75,
    ticketPrice: 15,
    advanceBookingRequired: false,
    category: "art",
  },
  {
    name: "Harbor Cruise",
    description:
      "A scenic boat tour along the Luminaran coastline with views of sea cliffs and the historic lighthouse.",
    openTime: "10:00",
    closeTime: "15:00",
    closureDays: [],
    visitDurationMinutes: 60,
    ticketPrice: 40,
    advanceBookingRequired: true,
    category: "entertainment",
  },
  {
    name: "Night Market",
    description:
      "A vibrant open-air market with street food stalls, live music, and handcrafted souvenirs under lantern light.",
    openTime: "18:00",
    closeTime: "23:00",
    closureDays: ["Monday", "Tuesday", "Wednesday", "Thursday"],
    visitDurationMinutes: 90,
    ticketPrice: 0,
    advanceBookingRequired: false,
    category: "culture",
  },
  {
    name: "Science Discovery Center",
    description:
      "An interactive science museum with hands-on exhibits covering physics, biology, and space exploration.",
    openTime: "09:00",
    closeTime: "17:00",
    closureDays: [],
    visitDurationMinutes: 90,
    ticketPrice: 22,
    advanceBookingRequired: false,
    category: "science",
  },
  {
    name: "Ancient Temple Ruins",
    description:
      "Well-preserved ruins of a 2,000-year-old temple complex set on a hillside overlooking the harbor.",
    openTime: "06:00",
    closeTime: "18:00",
    closureDays: [],
    visitDurationMinutes: 45,
    ticketPrice: 10,
    advanceBookingRequired: false,
    category: "history",
  },
];
