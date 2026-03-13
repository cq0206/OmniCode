#!/usr/bin/env node

import { randomUUID } from "node:crypto";
import process from "node:process";

import { Command } from "commander";

import { resumeWorkflow, runWorkflow } from "./processManager.js";
import { UiRenderer } from "./uiRenderer.js";

function withPrompt(parts: string[]): string {
  return parts.join(" ").trim();
}

async function main(): Promise<void> {
  const program = new Command();
  program
    .name("omnicode")
    .description("OmniCode multi-agent orchestration shell")
    .version("0.1.0");

  program
    .command("run")
    .alias("chat")
    .argument("<prompt...>", "Task prompt to orchestrate")
    .option("-C, --cwd <cwd>", "Working directory to run against", process.cwd())
    .option("--session-id <sessionId>", "Reuse an existing session")
    .option("--yolo", "Skip confirmations in downstream tools", false)
    .action(async (promptParts: string[], options) => {
      const renderer = new UiRenderer();
      const sessionId = options.sessionId || randomUUID().slice(0, 8);

      try {
        await runWorkflow(
          {
            prompt: withPrompt(promptParts),
            workingDir: options.cwd,
            sessionId,
            yolo: options.yolo,
          },
          (event) => renderer.render(event),
        );
      } catch (error) {
        const alreadyReported =
          error instanceof Error &&
          "alreadyReported" in error &&
          error.alreadyReported === true;
        if (!alreadyReported) {
          renderer.render({
            event: "error",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        process.exitCode = 1;
      }
    });

  program
    .command("resume")
    .argument("<sessionId>", "Session identifier to resume")
    .argument("[prompt...]", "Optional continuation instruction")
    .option("-C, --cwd <cwd>", "Working directory to run against", process.cwd())
    .option("--yolo", "Skip confirmations in downstream tools", false)
    .action(async (sessionId: string, promptParts: string[], options) => {
      const renderer = new UiRenderer();
      const prompt = withPrompt(promptParts) || "Resume the prior workflow and continue from the tape.";

      try {
        await resumeWorkflow(
          {
            prompt,
            workingDir: options.cwd,
            sessionId,
            yolo: options.yolo,
          },
          (event) => renderer.render(event),
        );
      } catch (error) {
        const alreadyReported =
          error instanceof Error &&
          "alreadyReported" in error &&
          error.alreadyReported === true;
        if (!alreadyReported) {
          renderer.render({
            event: "error",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        process.exitCode = 1;
      }
    });

  await program.parseAsync(process.argv);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
