# Vendored RAG core

These modules are byte-identical copies of Project 3's (`docchat`) `src/`
package: `config`, `pdf_reader`, `chunker`, `embeddings`, `store`, `rag`,
`llm`, `costs`.

Project 6 is about everything *around* the model — auth, guardrails,
observability, deployment — so the pipeline itself is frozen as the
measured 6/6 artifact. Any RAG change belongs in Project 3, then gets
re-vendored here.
