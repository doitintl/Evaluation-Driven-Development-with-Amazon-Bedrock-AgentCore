export interface Attraction {
  name: string;
  description: string;
  openTime: string; // HH:MM format
  closeTime: string; // HH:MM format
  closureDays: string[]; // e.g., ["Monday", "Tuesday"]
  visitDurationMinutes: number; // 30-180
  ticketPrice: number; // USD
  advanceBookingRequired: boolean;
  category: string; // e.g., "history", "art", "nature"
}

export interface Restaurant {
  name: string;
  cuisineType: string;
  mealTypes: ("breakfast" | "lunch" | "dinner")[];
  priceRange: "budget" | "moderate" | "upscale";
  nearAttractions: { attractionName: string; travelTimeMinutes: number }[];
}

export interface DistanceMatrix {
  [from: string]: { [to: string]: number }; // minutes of travel time
}

export interface RoutePlanRequest {
  attractions: string[];
  numDays: number;
  startDay: string;
  dayStartTime: string; // default "09:00"
  dayEndTime: string; // default "21:00"
}

export interface RouteResult {
  success: boolean;
  itinerary?: Itinerary;
  conflicts?: ClosureConflict[];
  overflow?: TimeOverflow;
  adjustments?: string[];
}

export interface Itinerary {
  days: DayPlan[];
  totalCost: number;
  totalAttractions: number;
  adjustments: string[];
}

export interface DayPlan {
  dayNumber: number;
  dayOfWeek: string;
  entries: ItineraryEntry[];
}

export interface ItineraryEntry {
  startTime: string; // HH:MM
  endTime: string; // HH:MM
  name: string;
  activityType: "visit" | "meal" | "travel";
  durationMinutes: number;
  notes?: string;
}

export interface ClosureConflict {
  attractionName: string;
  requestedDay: string;
  closureDays: string[];
  suggestion: string;
}

export interface TimeOverflow {
  requestedMinutes: number;
  availableMinutes: number;
  suggestion: string;
}

export interface DiningRecommendation {
  restaurant: Restaurant;
  travelTimeFromAttraction: number;
  matchReason: string;
}
