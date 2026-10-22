// Графики дашборда. Один ряд данных на график: один цвет, без легенды,
// одна ось Y, подсказка при наведении. Таблица с теми же числами — под графиком.
(function () {
  if (!window.Chart) return;
  const data = JSON.parse(document.getElementById("chart-data").textContent);

  const css = getComputedStyle(document.documentElement);
  const color = {
    bar: css.getPropertyValue("--color-accent").trim(),
    barHover: css.getPropertyValue("--color-accent-dark").trim(),
    grid: css.getPropertyValue("--color-border").trim(),
    text: css.getPropertyValue("--color-text-soft").trim(),
  };
  const money = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
  const compact = new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 });

  Chart.defaults.font.family = css.getPropertyValue("--font").trim();
  Chart.defaults.color = color.text;

  function barChart(canvasId, labels, values, { tooltipLabel, tickFormat, extraTooltip }) {
    return new Chart(document.getElementById(canvasId), {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: color.bar,
            hoverBackgroundColor: color.barHover,
            borderRadius: 4,
            borderSkipped: "bottom",
            maxBarThickness: 28,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            displayColors: false,
            callbacks: {
              label: (ctx) => tooltipLabel(ctx.parsed.y),
              afterLabel: extraTooltip || (() => ""),
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { autoSkip: true, maxRotation: 0 } },
          y: {
            beginAtZero: true,
            border: { display: false },
            grid: { color: color.grid },
            ticks: { callback: tickFormat, precision: 0 },
          },
        },
      },
    });
  }

  barChart("revenue-chart", data.revenue.labels, data.revenue.values, {
    tooltipLabel: (value) => `Выручка: ${money.format(value)} сум`,
    tickFormat: (value) => compact.format(value),
    extraTooltip: (ctx) => `Заказов: ${data.revenue.orders[ctx.dataIndex]}`,
  });

  barChart("hourly-chart", data.hourly.labels, data.hourly.values, {
    tooltipLabel: (value) => `Заказов: ${value}`,
    tickFormat: (value) => value,
  });
})();
