import router from "@adonisjs/core/services/router";

const ProjectsController = () => import("#controllers/projects_controller");
router.get("/api/health", () => ({ status: "ok" }));
router
  .group(() => {
    router.get("/projects", [ProjectsController, "index"]);
    router.post("/projects", [ProjectsController, "create"]);
    router.get("/projects/:id", [ProjectsController, "show"]);
    router.get("/projects/:id/slides/:number", [ProjectsController, "slide"]);
    router.patch("/projects/:id/slides/:number/text", [
      ProjectsController,
      "update",
    ]);
    router.post("/projects/:id/history", [ProjectsController, "history"]);
    router.get("/projects/:id/slides/:number/background", [
      ProjectsController,
      "background",
    ]);
    router.post("/projects/:id/exports", [ProjectsController, "export"]);
    router.get("/projects/:id/exports/:jobId", [ProjectsController, "job"]);
    router.get("/projects/:id/exports/:jobId/download", [
      ProjectsController,
      "download",
    ]);
  })
  .prefix("/api");
