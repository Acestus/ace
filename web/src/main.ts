import { renderCharts } from "./charts";

export function bootAceWeb(): void {
  console.info("Ace web scaffold loaded.");
  void renderCharts();
}

bootAceWeb();
