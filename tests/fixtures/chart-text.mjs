import pptxgen from "pptxgenjs";

const presentation = new pptxgen();
presentation.layout = "LAYOUT_WIDE";
for (let index = 0; index < 2; index++) {
  const slide = presentation.addSlide();
  slide.addChart(
    presentation.ChartType.bar,
    [
      {
        name: "Northern region",
        labels: ["Jan", "Feb", "Mar"],
        values: [12, 25, 35],
      },
      {
        name: "Southern region",
        labels: ["Jan", "Feb", "Mar"],
        values: [20, 30, 15],
      },
    ],
    {
      x: 1,
      y: 1,
      w: 10,
      h: 5,
      objectName: "Revenue chart",
      showLegend: true,
      showTitle: true,
      title: "Quarterly revenue",
      showValue: true,
      showCatName: false,
      showSerName: false,
      catAxisTitle: "Month",
      valAxisTitle: "Revenue",
      showValAxisTitle: true,
      showCatAxisTitle: true,
      catAxisLabelFontFace: "Arial",
      valAxisLabelFontFace: "Arial",
      legendFontFace: "Arial",
      dataLabelFontFace: "Arial",
      titleFontFace: "Arial",
      titleFontSize: 18,
      legendFontSize: 12,
    },
  );
}
await presentation.writeFile({ fileName: process.argv[2] });
