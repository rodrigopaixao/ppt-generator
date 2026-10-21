import { test, expect } from "@playwright/test";
import JSZip from "jszip";

const backend = "http://127.0.0.1:3344/api";

test("inline edit preserves typing, cancel, history, reopening and failed-save draft recovery", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.getByLabel("Project name").fill("Inline editing test");
  await page.getByRole("button", { name: "Create presentation" }).click();
  await expect(page).toHaveURL(/\/projects\/[\w-]+\/slides\/1$/);
  const projectId = page.url().split("/projects/")[1].split("/")[0];
  await page.locator(`a[href="/projects/${projectId}/slides/5"]`).click();
  const heading = page.getByRole("button", {
    name: "Edit Title 4",
    exact: true,
  });
  await heading.dblclick();
  const textbox = page.getByRole("textbox", {
    name: "Editing Title 4",
    exact: true,
  });
  await textbox.fill("Edited ");
  await textbox.pressSequentially("title 😀");
  await expect(textbox).toHaveText("Edited title 😀");
  await textbox.press("Enter");
  await expect(page.getByText("All changes saved")).toBeVisible();
  await expect(heading).toHaveText("Edited title 😀");
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(heading).toHaveText("Executive Summary");
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(heading).toHaveText("Edited title 😀");
  await heading.dblclick();
  await textbox.fill("Discard this text");
  await textbox.press("Escape");
  await expect(heading).toHaveText("Edited title 😀");
  await page.reload();
  await expect(heading).toHaveText("Edited title 😀");
  await page.route("**/api/projects/*/slides/5/text", (route) =>
    route.fulfill({
      status: 503,
      json: { error: "Simulated network failure" },
    }),
  );
  await heading.dblclick();
  await textbox.fill("Recoverable draft");
  await textbox.press("Enter");
  await expect(
    page.getByRole("alert").filter({ hasText: "Simulated network failure" }),
  ).toBeVisible();
  await expect(textbox).toHaveText("Recoverable draft");
  // A full refresh retains the draft locally; the server still holds the committed value.
  page.on("dialog", (dialog) => dialog.accept());
  await page.unroute("**/api/projects/*/slides/5/text");
  await page.reload();
  await page
    .getByRole("button", { name: "Recover draft", exact: true })
    .click();
  await expect(textbox).toHaveText("Recoverable draft");
  await textbox.press("Enter");
  await expect(heading).toHaveText("Recoverable draft");
  await expect(page.getByText("Full preview", { exact: true })).toBeVisible({
    timeout: 100_000,
  });
  await page.screenshot({
    path: "output/editor-e2e/editor.png",
    fullPage: true,
  });
  // Browser history can bypass sidebar guards; the abandoned draft must not
  // leave the shared workspace permanently stuck in editing mode.
  await page.locator(`a[href="/projects/${projectId}/slides/4"]`).click();
  await expect(page.getByLabel("Slide 4", { exact: true })).toBeVisible();
  const nextHeading = page
    .locator(".text-element.editable .inline-text")
    .first();
  await nextHeading.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("textbox").fill("Draft before going back");
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/slides/5$`));
  await expect(
    page.getByRole("button", { name: "Export PowerPoint" }),
  ).toBeEnabled();
  await page.locator(`a[href="/projects/${projectId}/slides/4"]`).click();
  await expect(page.getByLabel("Slide 4", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Recover draft", exact: true })
    .click();
  await expect(page.getByRole("textbox")).toHaveText("Draft before going back");
  await page.getByRole("textbox").press("Escape");
});

test("API enforces revisions and export uses an immutable text snapshot", async ({
  request,
}) => {
  const created = await request.post(`${backend}/projects`, {
    data: { name: "Snapshot test", mode: "fidelity" },
  });
  expect(created.status()).toBe(201);
  const { project } = await created.json();
  const url = `${backend}/projects/${project.id}`;
  const first = await request.patch(`${url}/slides/5/text`, {
    data: { revision: 0, elementId: "e5", text: "Export snapshot <&> 😀" },
  });
  expect(first.status()).toBe(200);
  const conflict = await request.patch(`${url}/slides/5/text`, {
    data: { revision: 0, elementId: "e5", text: "Stale tab" },
  });
  expect(conflict.status()).toBe(409);
  const unsupported = await request.patch(`${url}/slides/5/text`, {
    data: { revision: 1, elementId: "missing", text: "Unknown element" },
  });
  expect(unsupported.status()).toBe(422);
  const queued = await request.post(`${url}/exports`);
  expect(queued.status()).toBe(202);
  const job = await queued.json();
  await request.patch(`${url}/slides/5/text`, {
    data: { revision: 1, elementId: "e5", text: "Later edit" },
  });
  await expect
    .poll(
      async () =>
        (await (await request.get(`${url}/exports/${job.id}`)).json()).status,
      { timeout: 120_000, intervals: [1000] },
    )
    .toBe("complete");
  const download = await request.get(`${url}/exports/${job.id}/download`);
  expect(download.status()).toBe(200);
  const archive = await JSZip.loadAsync(await download.body());
  const slide = await archive.file("ppt/slides/slide5.xml")!.async("string");
  expect(slide).toContain("Export snapshot &lt;&amp;&gt; 😀");
  expect(slide).not.toContain("Later edit");
});

test("responsive semantic IDs export the edited text through the responsive generator", async ({
  request,
}) => {
  const created = await request.post(`${backend}/projects`, {
    data: { name: "Responsive test", mode: "responsive" },
  });
  expect(created.status()).toBe(201);
  const { project, slides } = await created.json();
  expect(slides.map((s: { number: number }) => s.number)).toEqual([
    5, 10, 21, 38, 50, 64, 68,
  ]);
  const url = `${backend}/projects/${project.id}`;
  const scene = await (await request.get(`${url}/slides/50`)).json();
  const heading = scene.elements.find(
    (e: { editable: boolean; role: string }) =>
      e.editable && e.role === "title",
  );
  expect(heading).toBeTruthy();
  const saved = await request.patch(`${url}/slides/50/text`, {
    data: { revision: 0, elementId: heading.id, text: "Adaptive headline" },
  });
  expect(saved.status()).toBe(200);
  const projected = await (
    await request.get(`${url}/slides/50?revision=1`)
  ).json();
  expect(projected.layoutError).toBeUndefined();
  expect(
    projected.elements.find((e: { id: string }) => e.id === heading.id).text,
  ).toBe("Adaptive headline");
  const job = await (await request.post(`${url}/exports`)).json();
  await expect
    .poll(
      async () =>
        (await (await request.get(`${url}/exports/${job.id}`)).json()).status,
      { timeout: 120_000, intervals: [1000] },
    )
    .toBe("complete");
  const archive = await JSZip.loadAsync(
    await (await request.get(`${url}/exports/${job.id}/download`)).body(),
  );
  const slide = await archive.file("ppt/slides/slide5.xml")!.async("string");
  expect(slide).toContain("Adaptive headline");
});

test("paragraphs accept plain-text paste, render line breaks and save on blur", async ({
  page,
  request,
}) => {
  const { project } = await (
    await request.post(`${backend}/projects`, {
      data: { name: "Paragraph test" },
    })
  ).json();
  await page.goto(`/projects/${project.id}/slides/5`);
  await page
    .getByRole("button", { name: "Edit Text Placeholder 2", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  const editor = page.getByRole("textbox", {
    name: "Editing Text Placeholder 2",
    exact: true,
  });
  await editor.fill("");
  await editor.evaluate((element) => {
    const data = new DataTransfer();
    data.setData("text/plain", "First <b>text</b>\nSecond paragraph 😀");
    data.setData("text/html", "<b>First</b><img src=x onerror=alert(1)>");
    element.dispatchEvent(
      new ClipboardEvent("paste", {
        clipboardData: data,
        bubbles: true,
        cancelable: true,
      }),
    );
  });
  await expect(editor).toHaveText("First <b>text</b>\nSecond paragraph 😀", {
    useInnerText: true,
  });
  expect(await editor.locator("b,img").count()).toBe(0);
  await page.locator(".canvas-toolbar h1").click();
  await expect(page.getByText("All changes saved")).toBeVisible();
  const stored = await (
    await request.get(`${backend}/projects/${project.id}`)
  ).json();
  expect(stored.project.overrides["5.e3"]).toBe(
    "First <b>text</b>\nSecond paragraph 😀",
  );
  const committed = page.getByRole("button", {
    name: "Edit Text Placeholder 2",
    exact: true,
  });
  await expect(committed).toHaveText("First <b>text</b>\nSecond paragraph 😀", {
    useInnerText: true,
  });
  await expect(
    page.getByText("Some text exceeds its box.", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(committed).toHaveText("First <b>text</b>\nSecond paragraph 😀", {
    useInnerText: true,
  });
});

for (const mode of ["fidelity", "responsive"] as const) {
  test(`${mode} table cells edit inline, survive reopening, history and PPTX export`, async ({
    page,
    request,
  }) => {
    const { project } = await (
      await request.post(`${backend}/projects`, {
        data: { name: "Editable table test", mode },
      })
    ).json();
    const url = `${backend}/projects/${project.id}`;
    const number = mode === "fidelity" ? 21 : 10;
    const scene = await (await request.get(`${url}/slides/${number}`)).json();
    const cell = scene.elements.find(
      (e: any) => e.target?.kind === "tableCell" && e.text.length > 0,
    );
    expect(cell).toBeTruthy();
    await page.goto(`/projects/${project.id}/slides/${number}`);
    const container = page.locator(`[data-element-id="${cell.id}"]`);
    await container.locator(".inline-text").dblclick();
    const textbox = page.getByRole("textbox");
    await textbox.fill("Updated cell 😀");
    await textbox.press("Control+Enter");
    await expect(page.getByText("All changes saved")).toBeVisible();
    await expect(container).toContainText("Updated cell 😀");
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(container).toContainText(cell.text);
    await page.getByRole("button", { name: "Redo", exact: true }).click();
    await expect(container).toContainText("Updated cell 😀");
    await page.reload();
    await expect(container).toContainText("Updated cell 😀");
    const job = await (await request.post(`${url}/exports`)).json();
    await expect
      .poll(
        async () =>
          (await (await request.get(`${url}/exports/${job.id}`)).json()).status,
        { timeout: 120_000, intervals: [1000] },
      )
      .toBe("complete");
    const archive = await JSZip.loadAsync(
      await (await request.get(`${url}/exports/${job.id}/download`)).body(),
    );
    const part =
      mode === "fidelity" ? "ppt/slides/slide21.xml" : "ppt/slides/slide2.xml";
    const xml = await archive.file(part)!.async("string");
    expect(xml).toContain("Updated cell 😀");
    expect(xml).toContain("<a:tbl");
    expect(xml).toContain("<a:tblGrid");
  });
}

for (const mode of ["fidelity", "responsive"] as const) {
  test(`${mode} chart labels edit inline, reopen and export without changing chart data`, async ({
    page,
    request,
  }) => {
    const { project } = await (
      await request.post(`${backend}/projects`, {
        data: { name: "Editable chart test", mode },
      })
    ).json();
    const url = `${backend}/projects/${project.id}`;
    const scene = await (await request.get(`${url}/slides/68`)).json();
    expect(scene.chartTextError).toBeUndefined();
    const labels = scene.elements.filter(
      (element: any) => element.target?.kind === "chartText",
    );
    // Responsive doughnuts already draw legends as ordinary editable text.
    // Native charts require the measured-label adapter.
    const label =
      mode === "responsive"
        ? scene.elements.find((element: any) =>
            element.id.endsWith(".chart.legend"),
          )
        : (labels.find((element: any) => element.text === "Complete") ??
          labels[0]);
    expect(label).toBeTruthy();
    await page.goto(`/projects/${project.id}/slides/68`);
    const container = page.locator(`[data-element-id="${label.id}"]`);
    await container.locator(".inline-text").dblclick();
    const textbox = page.getByRole("textbox");
    await textbox.fill("Done");
    await textbox.press("Control+Enter");
    await expect(page.getByText("All changes saved")).toBeVisible();
    await expect(container).toContainText("Done");
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(container).toContainText(label.text);
    await page.getByRole("button", { name: "Redo", exact: true }).click();
    await expect(container).toContainText("Done");
    await page.reload();
    await expect(container).toContainText("Done");
    await expect(page.getByText("Full preview", { exact: true })).toBeVisible({
      timeout: 100_000,
    });
    await page.screenshot({
      path: `output/editor-e2e/chart-${mode}.png`,
      fullPage: true,
    });
    const job = await (await request.post(`${url}/exports`)).json();
    await request.patch(`${url}/slides/68/text`, {
      data: { revision: 3, elementId: label.id, text: "Later chart label" },
    });
    await expect
      .poll(
        async () =>
          (await (await request.get(`${url}/exports/${job.id}`)).json()).status,
        { timeout: 120_000, intervals: [1000] },
      )
      .toBe("complete");
    const archive = await JSZip.loadAsync(
      await (await request.get(`${url}/exports/${job.id}/download`)).body(),
    );
    const slide = await archive
      .file(
        mode === "fidelity"
          ? "ppt/slides/slide68.xml"
          : "ppt/slides/slide7.xml",
      )!
      .async("string");
    expect(slide).toContain("Done");
    expect(slide).not.toContain("Later chart label");
    if (mode === "fidelity") expect(slide).toContain("editor-chart:");
    expect(slide).toContain("<c:chart");
    expect(
      Object.keys(archive.files).some(
        (name) => name.startsWith("ppt/embeddings/") && name.endsWith(".xlsx"),
      ),
    ).toBeTruthy();
  });
}
