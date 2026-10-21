import server from "@adonisjs/core/services/server";
import router from "@adonisjs/core/services/router";

server.errorHandler(() => import("#exceptions/handler"));
router.use([() => import("@adonisjs/core/bodyparser_middleware")]);
