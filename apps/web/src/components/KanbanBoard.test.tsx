import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { KanbanBoard } from "@/components/KanbanBoard"

vi.mock("@/lib/api", () => ({
  api: {
    board: async () => ({
      project: {
        id: 1,
        name: "Platform",
        key: "PLAT",
        created_at: "",
        updated_at: "",
      },
      columns: [
        {
          status: { id: 1, name: "Backlog", category: "todo", color: "slate", position: "0" },
          tasks: [
            {
              id: 10,
              project_id: 1,
              status_id: 1,
              title: "Wire TiDB board",
              priority: "high",
              assignee: "Local User",
              archived: false,
              rank: "1000",
              position: "1000",
              labels: [],
              created_at: "",
              updated_at: "",
            },
          ],
        },
      ],
    }),
    createTask: vi.fn(),
    moveTask: vi.fn(),
    updateTask: vi.fn(),
    archivedTasks: async () => [],
    archiveTask: vi.fn(),
    restoreTask: vi.fn(),
    aiQuery: vi.fn(),
    aiSuggestions: async () => ({ suggestions: [] }),
    listMembers: async () => [
      {
        id: 1,
        project_id: 1,
        email: "local-user@example.com",
        display_name: "Local User",
        role: "admin",
        created_at: "",
      },
    ],
  },
}))

describe("KanbanBoard", () => {
  it("renders board columns and tasks", async () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <KanbanBoard projectId={1} />
      </QueryClientProvider>,
    )

    expect(await screen.findByText("Backlog")).toBeTruthy()
    expect(await screen.findByText("Wire TiDB board")).toBeTruthy()
  })
})
