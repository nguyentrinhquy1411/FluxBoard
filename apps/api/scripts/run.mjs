import { spawn } from "node:child_process"
import { mkdirSync, writeFileSync } from "node:fs"

const tasks = {
  dev: ["-m", "uvicorn", "app.api:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
  build: ["-c", "import app.api; print('api build ok')"],
  test: ["-m", "pytest"],
  lint: ["-m", "ruff", "check", "."],
}

const task = process.argv[2]
const args = tasks[task]

if (!args) {
  console.error(`Unknown API task: ${task}`)
  process.exit(1)
}

const child = spawn("uv", ["run", "python", ...args], {
  cwd: process.cwd(),
  env: process.env,
  shell: false,
  stdio: "inherit",
})

child.on("exit", (code) => {
  if (code === 0 && task === "build") {
    mkdirSync("dist", { recursive: true })
    writeFileSync("dist/build-ok.txt", "api build ok\n")
  }
  process.exit(code ?? 1)
})
