import type { Restaurant } from "./types.js";

export const restaurants: Restaurant[] = [
  {
    name: "Sunrise Terrace Café",
    cuisineType: "Mediterranean",
    mealTypes: ["breakfast", "lunch"],
    priceRange: "budget",
    nearAttractions: [
      { attractionName: "Botanical Gardens", travelTimeMinutes: 4 },
      { attractionName: "Skyline Tower", travelTimeMinutes: 8 },
      { attractionName: "Science Discovery Center", travelTimeMinutes: 10 },
    ],
  },
  {
    name: "Dragon Bowl Noodle House",
    cuisineType: "Asian",
    mealTypes: ["lunch", "dinner"],
    priceRange: "budget",
    nearAttractions: [
      { attractionName: "Night Market", travelTimeMinutes: 3 },
      { attractionName: "Old Quarter Walking Tour", travelTimeMinutes: 6 },
      { attractionName: "Ancient Temple Ruins", travelTimeMinutes: 9 },
    ],
  },
  {
    name: "Palazzo Dining Room",
    cuisineType: "Italian",
    mealTypes: ["lunch", "dinner"],
    priceRange: "upscale",
    nearAttractions: [
      { attractionName: "Royal Palace", travelTimeMinutes: 5 },
      { attractionName: "Grand Museum of Luminara", travelTimeMinutes: 7 },
      { attractionName: "Luminara Art Gallery", travelTimeMinutes: 11 },
    ],
  },
  {
    name: "Harbor Fresh Kitchen",
    cuisineType: "Seafood",
    mealTypes: ["lunch", "dinner"],
    priceRange: "moderate",
    nearAttractions: [
      { attractionName: "Harbor Cruise", travelTimeMinutes: 3 },
      { attractionName: "Skyline Tower", travelTimeMinutes: 10 },
      { attractionName: "Night Market", travelTimeMinutes: 12 },
      { attractionName: "Old Quarter Walking Tour", travelTimeMinutes: 14 },
    ],
  },
  {
    name: "The Golden Croissant",
    cuisineType: "French",
    mealTypes: ["breakfast", "lunch"],
    priceRange: "moderate",
    nearAttractions: [
      { attractionName: "Grand Museum of Luminara", travelTimeMinutes: 4 },
      { attractionName: "Luminara Art Gallery", travelTimeMinutes: 6 },
      { attractionName: "Royal Palace", travelTimeMinutes: 12 },
    ],
  },
  {
    name: "Ember & Vine Steakhouse",
    cuisineType: "American",
    mealTypes: ["dinner"],
    priceRange: "upscale",
    nearAttractions: [
      { attractionName: "Skyline Tower", travelTimeMinutes: 5 },
      { attractionName: "Science Discovery Center", travelTimeMinutes: 8 },
      { attractionName: "Botanical Gardens", travelTimeMinutes: 13 },
      { attractionName: "Harbor Cruise", travelTimeMinutes: 15 },
    ],
  },
];
