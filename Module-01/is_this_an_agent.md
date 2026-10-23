# Is this an agent?

- (a) A program that takes a support email and returns a drafted reply in one LLM call.  
  Classification: single LLM call. It does one model invocation with no runtime choice or loop, so it is not an autonomous agent.

- (b) A program that, given "research topic X," repeatedly searches, reads, and decides whether it has enough to write a summary — stopping when satisfied.  
  Classification: agent. The model chooses actions over multiple steps based on what it learns from results, which is the defining behavior of an agent.

- (c) A nightly job that fetches sales data, asks an LLM to summarize it, then always posts the summary to a channel.  
  Classification: workflow. The steps are fixed in advance and the program does not decide alternate actions at runtime, so it is a pipeline rather than an autonomous agent.
