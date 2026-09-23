export interface AppConfig {
  modelId: string;
  awsRegion: string;
  awsProfile?: string;
}

export function loadConfig(): AppConfig {
  const awsRegion = process.env.AWS_REGION;
  if (!awsRegion) {
    console.error("ERROR: AWS_REGION environment variable is required.");
    process.exit(1);
  }

  return {
    modelId: process.env.MODEL_ID || "us.anthropic.claude-sonnet-4-6",
    awsRegion,
    awsProfile: process.env.AWS_PROFILE,
  };
}

/**
 * Retry a function up to `retries` times with a delay between attempts.
 * Useful for transient failures like Bedrock model timeouts.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  retries: number = 1,
  delayMs: number = 2000
): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    if (retries > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      return withRetry(fn, retries - 1, delayMs);
    }
    throw error;
  }
}
