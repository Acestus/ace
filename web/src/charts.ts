type ChartDataset = {
  label: string;
  data: number[];
  borderColor?: string;
  backgroundColor?: string;
  fill?: boolean;
};

type ChartSpec = {
  title?: string;
  type?: "bar" | "line" | "radar" | "pie" | "doughnut";
  labels: string[];
  datasets: ChartDataset[];
  options?: Record<string, unknown>;
};

function setStatus(host: HTMLElement, message: string): void {
  const status = host.querySelector<HTMLElement>("[data-chart-status]");
  if (status) {
    status.textContent = message;
  }
}

async function loadSpec(host: HTMLElement): Promise<ChartSpec> {
  const source = host.dataset.source;
  if (!source) {
    throw new Error("Missing chart source");
  }

  const response = await fetch(source);
  if (!response.ok) {
    throw new Error(`Chart data request failed with ${response.status}`);
  }

  return (await response.json()) as ChartSpec;
}

export async function renderCharts(): Promise<void> {
  const hosts = Array.from(document.querySelectorAll<HTMLElement>("[data-chart]"));
  if (hosts.length === 0) {
    return;
  }

  const { default: Chart } = await import("chart.js/auto");

  for (const host of hosts) {
    const canvas = host.querySelector<HTMLCanvasElement>("canvas");
    if (!canvas) {
      continue;
    }

    try {
      setStatus(host, "Loading chart...");
      const spec = await loadSpec(host);
      new Chart(canvas, {
        type: spec.type ?? "bar",
        data: {
          labels: spec.labels,
          datasets: spec.datasets,
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          ...spec.options,
        },
      });
      setStatus(host, spec.title ? `${spec.title} rendered.` : "Chart rendered.");
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Unknown chart error";
      host.dataset.state = "error";
      setStatus(host, `Chart unavailable: ${reason}`);
    }
  }
}
