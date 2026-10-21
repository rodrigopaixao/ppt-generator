import { randomBytes } from "node:crypto";
import { Secret } from "@adonisjs/core/helpers";
import { defineConfig } from "@adonisjs/core/http";

export const appKey = new Secret(
  process.env.APP_KEY || randomBytes(32).toString("hex"),
);
export const http = defineConfig({
  generateRequestId: true,
  allowMethodSpoofing: false,
  useAsyncLocalStorage: false,
  cookie: {
    domain: "",
    path: "/",
    maxAge: "2h",
    httpOnly: true,
    secure: false,
    sameSite: "lax",
  },
});
