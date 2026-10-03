// Runs the Gradle wrapper of android/ with the given task, on Windows or POSIX shells alike.
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const android = resolve(dirname(fileURLToPath(import.meta.url)), "..", "android");
const windows = process.platform === "win32";
const wrapper = join(android, windows ? "gradlew.bat" : "gradlew");
const result = spawnSync(wrapper, process.argv.slice(2), { cwd: android, stdio: "inherit", shell: windows });
process.exit(result.status ?? 1);
