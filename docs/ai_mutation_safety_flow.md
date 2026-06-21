# LLM Mutation Safety Flow & Guardrails

This document explains the security architecture of the AI-driven task modifications (create, edit, remove) in the backend.

```mermaid
flowchart TD
    UserReq([User Request\n'create task: write tests']) --> Context[Query DB for Project Context\n- Active columns/statuses\n- Active task IDs & priorities]
    Context --> SystemPrompt[Construct System Prompt\n- DB schema constraints\n- Inject current state\n- Enforce structured JSON schema]
    
    SystemPrompt --> Groq[Call Groq LLM\nLlama-3.3-70b-versatile]
    
    Groq -- Raw Text JSON --> ParseJSON[Strict JSON Parser\nClean markdown code blocks]
    ParseJSON -- Valid Schema --> SafetyCheck[Safety Guardrails\n- Match status_id to valid project columns\n- Only extract known fields]
    
    subgraph Secure Database Layer
        SafetyCheck -- action: 'create_task' --> RepoCreate[TaskRepository.create_task\n- Automatically assigns LOCAL_USER\n- Computes next position fraction\n- Commits inside transaction]
        SafetyCheck -- action: 'update_task' --> RepoUpdate[TaskRepository.update_task\n- Builds explicit TaskUpdate patch\n- Updates only provided fields]
        SafetyCheck -- action: 'archive_task' --> RepoArchive[TaskRepository.update_task\n- Sets archived = true]
    end
    
    RepoCreate --> DB[(TiDB Database)]
    RepoUpdate --> DB
    RepoArchive --> DB
    
    DB -- Success --> Response([API Response JSON\n- status: 200\n- Refresh Frontend])
```

## Why this Flow is 100% Safe

1. **No Raw SQL Generation for Mutations**: 
   Unlike the Read-Only orchestrator which compiles raw SQL queries dynamically, the AI mutation engine **never** generates or executes raw SQL queries (`INSERT`, `UPDATE`, `DELETE`). The LLM only generates a structured instructions payload (`"action": "create_task"`, etc.).
   
2. **Schema and Project Isolation**: 
   The backend restricts actions to the current `project_id`. When creating or updating a task, the code verifies that the requested `status_id` actually belongs to the active project's columns. If the LLM generates an invalid `status_id`, it is automatically ignored or defaulted to the first column.

3. **No Direct System Access**: 
   The database changes are run through the pre-audited, type-safe Python repository (`TaskRepository` built with SQLAlchemy). This means standard application logic, like sanitization, audit/activity logging (`self._activity()`), and creation timestamps, is fully preserved.

4. **Transactional Security**: 
   All changes are run within the current database transaction context (`self.session.commit()`). If any repository validation fails, the entire transaction is automatically rolled back, leaving the database clean.
