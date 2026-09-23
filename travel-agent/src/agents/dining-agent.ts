// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { Type, type Static } from "@sinclair/typebox";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";
import type { DiningRecommendation } from "../data/types.js";
import { restaurants } from "../data/restaurants.js";

const DiningQuerySchema = Type.Object({
  attraction_name: Type.String({ description: "Current or next attraction to find dining near" }),
  meal_type: Type.Union([
    Type.Literal("breakfast"),
    Type.Literal("lunch"),
    Type.Literal("dinner"),
  ], { description: "Type of meal" }),
  cuisine_preference: Type.Optional(Type.String({ description: "Preferred cuisine type" })),
});

type DiningQuery = Static<typeof DiningQuerySchema>;

export function createDiningAgentTool(): AgentTool<typeof DiningQuerySchema, DiningRecommendation[]> {
  return {
    name: "suggest_dining",
    label: "Dining Suggestions",
    description:
      "Suggest restaurants near a planned attraction appropriate for the specified meal type. Returns options with cuisine, price range, and travel time from the attraction.",
    parameters: DiningQuerySchema,
    execute: async (toolCallId, args, signal, onUpdate) => {
      return suggestDining(args);
    },
  };
}

export function suggestDining(args: DiningQuery): AgentToolResult<DiningRecommendation[]> {
  const { attraction_name, meal_type, cuisine_preference } = args;

  // 1. Filter restaurants that serve the specified meal_type
  const mealFiltered = restaurants.filter((r) =>
    r.mealTypes.includes(meal_type)
  );

  // 2. Filter restaurants that are near the specified attraction
  const nearbyFiltered = mealFiltered.filter((r) =>
    r.nearAttractions.some((na) => na.attractionName === attraction_name)
  );

  // 3. Build recommendations with travel time from the attraction
  let recommendations: DiningRecommendation[] = nearbyFiltered.map((r) => {
    const nearEntry = r.nearAttractions.find(
      (na) => na.attractionName === attraction_name
    )!;

    const reasons: string[] = [];
    reasons.push(`Serves ${meal_type}`);
    reasons.push(`${nearEntry.travelTimeMinutes} minutes from ${attraction_name}`);
    reasons.push(`${r.cuisineType} cuisine`);

    return {
      restaurant: r,
      travelTimeFromAttraction: nearEntry.travelTimeMinutes,
      matchReason: reasons.join(", "),
    };
  });

  // 4. If cuisine_preference is provided, prioritize matching cuisine first
  if (cuisine_preference) {
    const preferred = recommendations.filter(
      (rec) =>
        rec.restaurant.cuisineType.toLowerCase() ===
        cuisine_preference.toLowerCase()
    );
    const others = recommendations.filter(
      (rec) =>
        rec.restaurant.cuisineType.toLowerCase() !==
        cuisine_preference.toLowerCase()
    );
    recommendations = [...preferred, ...others];
  }

  // 5. Sort by travel time (closest first), preserving cuisine preference grouping
  // Within each group (preferred/others), sort by travel time
  if (cuisine_preference) {
    const preferred = recommendations.filter(
      (rec) =>
        rec.restaurant.cuisineType.toLowerCase() ===
        cuisine_preference.toLowerCase()
    );
    const others = recommendations.filter(
      (rec) =>
        rec.restaurant.cuisineType.toLowerCase() !==
        cuisine_preference.toLowerCase()
    );
    preferred.sort((a, b) => a.travelTimeFromAttraction - b.travelTimeFromAttraction);
    others.sort((a, b) => a.travelTimeFromAttraction - b.travelTimeFromAttraction);
    recommendations = [...preferred, ...others];
  } else {
    recommendations.sort((a, b) => a.travelTimeFromAttraction - b.travelTimeFromAttraction);
  }

  // 6. Build text content for the model
  const textContent =
    recommendations.length > 0
      ? recommendations
          .map(
            (rec, i) =>
              `${i + 1}. ${rec.restaurant.name} (${rec.restaurant.cuisineType}, ${rec.restaurant.priceRange}) - ${rec.travelTimeFromAttraction} min from ${attraction_name}. ${rec.matchReason}`
          )
          .join("\n")
      : `No restaurants found serving ${meal_type} near ${attraction_name}.`;

  return {
    content: [{ type: "text", text: textContent }],
    details: recommendations,
  };
}
