# Module 2 comparison

## Full comparison table

| Question | LangGraph | CrewAI |
|---|---|---|
| Lines of code to first result | 55 lines in `hello_langgraph.py` | 46 lines in `hello_crewai.py` |
| Where did control flow live? | Explicitly in the graph: `define -> format_output -> END` with state flowing between nodes | In the `Crew` process and the task/agent descriptions; the runtime orchestrates the flow behind the scenes |
| What felt verbose? | Wiring nodes, edges, state typing, and graph compilation | Configuring roles, goals, and task metadata, plus the hidden runtime behavior |
| What felt "magical" / hidden? | The actual model call is clear, but the graph orchestration is still somewhat abstract until the edges are visible | The task execution and scheduling feel more hidden because the workflow is described more declaratively |
| When would you choose this one? | For precise control flow, branching, loops, state transitions, and orchestration-heavy systems | For fast prototypes, role-based collaboration, and lightweight multi-agent team tasks |

## Actual line counts

- `hello_langgraph.py`: 55 lines
- `hello_crewai.py`: 46 lines
- `requirements.txt`: 5 lines
- `requirements.lock.txt`: 67 lines

## Multi-agent preference

For the multi-agent module later, I would reach for LangGraph first because its explicit nodes, edges, and state transitions make it easier to reason about routing, retries, and orchestration when the workflow is non-trivial. CrewAI is excellent for quick role-based collaboration, but LangGraph is better when we need precise control over how agents hand off work and what state moves between steps.
