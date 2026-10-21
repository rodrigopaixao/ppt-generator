import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import type { Project, SlideScene } from "@pptx/contracts";
import { ProjectStore } from "../app/services/project_store.js";

const scene: SlideScene = {
  number: 5,
  title: "Original",
  hidden: false,
  width: 13.33,
  height: 7.5,
  elements: [
    {
      id: "e5",
      name: "Title",
      text: "Original",
      originalText: "Original",
      editable: true,
      box: { x: 1, y: 1, w: 10, h: 1 },
      rotation: 0,
      role: "title",
      style: {
        fontFamily: "Arial",
        fontSize: 22,
        color: "#000000",
        bold: false,
        italic: false,
        align: "left",
        vertical: "top",
        margins: [0, 0, 0, 0],
      },
    },
    {
      id: "e9",
      name: "Rich text",
      text: "Rich",
      originalText: "Rich",
      editable: false,
      box: { x: 1, y: 2, w: 10, h: 1 },
      rotation: 0,
      role: "paragraph",
      style: {
        fontFamily: "Arial",
        fontSize: 12,
        color: "#000000",
        bold: false,
        italic: false,
        align: "left",
        vertical: "top",
        margins: [0, 0, 0, 0],
      },
    },
  ],
};

async function fixture(
  fn: (store: ProjectStore, project: Project) => Promise<void>,
) {
  const folder = await mkdtemp(join(tmpdir(), "editor-store-"));
  const store = new ProjectStore(folder);
  const now = new Date().toISOString();
  const project: Project = {
    id: randomUUID(),
    name: "Test",
    mode: "fidelity",
    revision: 0,
    createdAt: now,
    updatedAt: now,
    overrides: {},
    history: [],
    cursor: 0,
  };
  try {
    await store.write(project);
    await fn(store, project);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
}

test("commits survive reopening; undo/redo restores original and branching discards redo", async () => {
  await fixture(async (store, project) => {
    const edited = await store.edit(
      project.id,
      0,
      scene,
      "e5",
      "Hello <script> & 😀",
    );
    assert.equal(edited.revision, 1);
    assert.equal(
      (await new ProjectStore(store.directory).read(project.id)).overrides[
        "5.e5"
      ],
      "Hello <script> & 😀",
    );
    const undone = await store.history(project.id, 1, "undo", [scene]);
    assert.deepEqual(undone.overrides, {});
    const redone = await store.history(project.id, 2, "redo", [scene]);
    assert.equal(redone.overrides["5.e5"], "Hello <script> & 😀");
    await store.history(project.id, 3, "undo", [scene]);
    const branch = await store.edit(project.id, 4, scene, "e5", "New edit");
    assert.equal(branch.history.length, 1);
    await assert.rejects(store.history(project.id, 5, "redo", [scene]), {
      code: "EMPTY_HISTORY",
    });
  });
});

test("two concurrent writes at the same revision cannot overwrite each other", async () => {
  await fixture(async (store, project) => {
    const results = await Promise.allSettled([
      store.edit(project.id, 0, scene, "e5", "Tab A"),
      store.edit(project.id, 0, scene, "e5", "Tab B"),
    ]);
    assert.equal(results.filter((r) => r.status === "fulfilled").length, 1);
    const rejected = results.find(
      (r) => r.status === "rejected",
    ) as PromiseRejectedResult;
    assert.equal(rejected.reason.code, "REVISION_CONFLICT");
    assert.equal((await store.read(project.id)).revision, 1);
  });
});

test("rejects unsupported elements, invalid revisions and unsafe paths", async () => {
  await fixture(async (store, project) => {
    for (const [element, value, code] of [
      ["e9", "Plain", "NOT_EDITABLE"],
      ["missing", "Text", "NOT_EDITABLE"],
      ["e5", "\0", "INVALID_TEXT"],
      ["e5", "a".repeat(20001), "INVALID_TEXT"],
    ] as const) {
      await assert.rejects(store.edit(project.id, 0, scene, element, value), {
        code,
      });
    }
    await assert.rejects(store.edit(project.id, -1, scene, "e5", "Text"), {
      code: "REVISION_CONFLICT",
    });
    await assert.rejects(store.read("../project"), { code: "NOT_FOUND" });
    assert.equal((await store.read(project.id)).revision, 0);
  });
});

test("clearing a text box is persisted and can be undone", async () => {
  await fixture(async (store, project) => {
    const empty = await store.edit(project.id, 0, scene, "e5", "");
    assert.equal(empty.overrides["5.e5"], "");
    const restored = await store.history(project.id, 1, "undo", [scene]);
    assert.deepEqual(restored.overrides, {});
  });
});

test("multiline titles are saved without flattening line breaks", async () => {
  await fixture(async (store, project) => {
    const edited = await store.edit(
      project.id,
      0,
      scene,
      "e5",
      "First\nSecond",
    );
    assert.equal(edited.overrides["5.e5"], "First\nSecond");
  });
});
