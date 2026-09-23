// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { createCoordinatorAgent } from "./coordinator.js";
import { loadConfig, withRetry } from "./utils/config.js";
import readline from "readline";
import type { Agent } from "@mariozechner/pi-agent-core";

const HELPFUL_MESSAGE = `I'm the Luminara Travel Planner! I can help you plan trips to our fictional city.

Try something like:
  • "Plan a 2-day trip focusing on history and food, arriving Monday"
  • "What attractions are open on weekends?"
  • "Suggest a day itinerary with the museum and botanical gardens"
`;

/**
 * Check if a prompt is empty or too short to be meaningful.
 */
function isEmptyOrNonsensical(prompt: string): boolean {
  return prompt.trim().length < 3;
}

/**
 * Check if an error is related to invalid/expired AWS credentials.
 */
function isCredentialError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return (
    msg.includes("credential") ||
    msg.includes("unauthorizedexception") ||
    msg.includes("expiredtoken") ||
    msg.includes("expired token") ||
    msg.includes("invalid identity token") ||
    msg.includes("security token") ||
    msg.includes("accessdenied")
  );
}

/**
 * Extract the text content from the last assistant message in the agent's state.
 */
function getLastAssistantText(agent: Agent): string {
  const messages = agent.state.messages;
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg && "role" in msg && msg.role === "assistant") {
      const textParts = msg.content
        .filter((c): c is { type: "text"; text: string } => c.type === "text")
        .map((c) => c.text);
      return textParts.join("");
    }
  }
  return "";
}

/**
 * Single-Shot Mode: process the prompt, print response to stdout, exit code 0.
 */
async function runSingleShot(agent: Agent, prompt: string): Promise<void> {
  if (isEmptyOrNonsensical(prompt)) {
    console.log(HELPFUL_MESSAGE);
    process.exit(0);
  }

  try {
    await withRetry(() => agent.prompt(prompt));
    const response = getLastAssistantText(agent);
    if (!response) {
      // Debug: check if there's an error in state or messages
      const errorMsg = (agent.state as any).errorMessage;
      if (errorMsg) {
        console.error(`Agent error: ${errorMsg}`);
        process.exit(1);
      }
      // Check messages for debugging
      const messages = agent.state.messages;
      if (messages.length === 0) {
        console.error("Error: Agent returned no messages. Check AWS credentials and model access.");
        process.exit(1);
      }
      // Try to find any text in any assistant message
      for (let i = messages.length - 1; i >= 0; i--) {
        const msg = messages[i] as any;
        if (msg?.role === "assistant" && msg.content) {
          for (const c of msg.content) {
            if (c.type === "text" && c.text) {
              console.log(c.text);
              process.exit(0);
            }
          }
          // If we have an assistant message but no text, check for error
          if (msg.stopReason === "error" || msg.errorMessage) {
            console.error(`Agent error: ${msg.errorMessage || "Unknown error (stopReason: " + msg.stopReason + ")"}`);
            process.exit(1);
          }
        }
      }
      console.error("Error: Agent produced no text response. Ensure your AWS credentials are valid and the model is accessible.");
      process.exit(1);
    }
    console.log(response);
    process.exit(0);
  } catch (error) {
    if (isCredentialError(error)) {
      console.error(
        "Error: AWS credentials are invalid or expired. Please check your AWS_PROFILE and credentials configuration."
      );
      process.exit(1);
    }
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error(`Error: ${message}`);
    process.exit(1);
  }
}

/**
 * Interactive Mode: REPL loop with conversation history maintained across turns.
 */
async function runInteractive(agent: Agent): Promise<void> {
  console.log("Welcome to the Luminara Travel Planner!");
  console.log(
    'Plan your trip to the fictional city of Luminara. Ask about attractions, routes, and dining.'
  );
  console.log('Type "exit" or "quit" to end the session.\n');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const promptUser = (): void => {
    rl.question("You> ", async (input: string) => {
      const trimmed = input.trim();

      if (trimmed.toLowerCase() === "exit" || trimmed.toLowerCase() === "quit") {
        console.log("\nGoodbye! Happy travels!");
        rl.close();
        return;
      }

      if (!trimmed) {
        promptUser();
        return;
      }

      try {
        await withRetry(() => agent.prompt(trimmed));
        const response = getLastAssistantText(agent);
        console.log(`\nAgent> ${response}\n`);
      } catch (error) {
        if (isCredentialError(error)) {
          console.error(
            "\nError: AWS credentials are invalid or expired. Please check your AWS_PROFILE and credentials configuration.\n"
          );
        } else {
          const message =
            error instanceof Error ? error.message : "An unexpected error occurred";
          console.error(`\nError: ${message}\n`);
        }
      }

      promptUser();
    });
  };

  promptUser();
}

/**
 * Main entry point: detects mode from CLI args and bootstraps the agent.
 */
async function main(): Promise<void> {
  const config = loadConfig();
  const agent = createCoordinatorAgent(config);
  const args = process.argv.slice(2);

  if (args.length > 0) {
    // Single-Shot Mode: join all args as the prompt
    await runSingleShot(agent, args.join(" "));
  } else {
    // Interactive Mode: REPL
    await runInteractive(agent);
  }
}

main().catch((error) => {
  console.error("Fatal error:", error instanceof Error ? error.message : error);
  process.exit(1);
});
