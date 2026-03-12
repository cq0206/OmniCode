import chalk from "chalk";
import ora from "ora";

import type { RendererEvent } from "./types.js";

export class UiRenderer {
  private readonly spinner = ora({
    discardStdin: false,
  });

  render(event: RendererEvent): void {
    switch (event.event) {
      case "planning":
        this.spinner.start(chalk.yellow(event.message ?? "Planning workflow..."));
        return;
      case "dispatch":
        if (this.spinner.isSpinning) {
          this.spinner.succeed(chalk.yellow("Planning complete"));
        }
        console.log(
          chalk.cyan(
            `[dispatch:${event.target ?? "agent"}] ${event.message ?? "Starting sub-agent"}`,
          ),
        );
        return;
      case "review":
        if (this.spinner.isSpinning) {
          this.spinner.stop();
        }
        this.spinner.start(chalk.magenta(event.message ?? "Reviewing result..."));
        return;
      case "sub_agent_log":
        console.log(chalk.dim(event.message ?? ""));
        return;
      case "done":
        if (this.spinner.isSpinning) {
          this.spinner.succeed(chalk.green(event.result ?? event.message ?? "Workflow complete"));
        } else {
          console.log(chalk.green(event.result ?? event.message ?? "Workflow complete"));
        }
        return;
      case "error":
        if (this.spinner.isSpinning) {
          this.spinner.fail(chalk.red(event.message ?? "Workflow failed"));
        } else {
          console.error(chalk.red(event.message ?? "Workflow failed"));
        }
        return;
      case "info":
      default:
        console.log(event.message ?? "");
    }
  }
}
