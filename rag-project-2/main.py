import os, httpx, chromadb
from sentence_transformers import SentenceTransformer
from tracelens_sdk import TraceLens
API=os.getenv("TRACELENS_API_URL","http://127.0.0.1:8000")
QUESTION="How long must an employee password be?"
DOCS=[
 {"id":"policy-a","text":"The minimum length for employee passwords is fourteen characters."},
 {"id":"policy-b","text":"All remote sessions must use multi-factor authentication."},
 {"id":"policy-c","text":"Never disclose account credentials to another person."},
]
class ChromaRAG:
 def __init__(self):
  self.client=chromadb.Client()
  self.collection=self.client.get_or_create_collection("tracelens_policy_demo")
  self.embedder=SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
  self.collection.upsert(ids=[d["id"] for d in DOCS],documents=[d["text"] for d in DOCS],
    embeddings=self.embedder.encode([d["text"] for d in DOCS]).tolist())
 def retrieve(self,question,broken=False):
  result=self.collection.query(query_embeddings=self.embedder.encode([question]).tolist(),n_results=3)
  found=[{"id":i,"text":t,"distance":float(dist)} for i,t,dist in zip(result["ids"][0],result["documents"][0],result["distances"][0])]
  return [] if broken else found[:2]
def answer(docs):
 return docs[0]["text"] if docs else "No relevant evidence was retrieved."
def main():
 rag=ChromaRAG()
 with httpx.Client(base_url=API,timeout=10) as c:
  c.get("/health").raise_for_status()
  r=c.post("/api/projects",json={"name":"RAG Project 2 - ChromaDB","description":"Standalone semantic RAG","framework":"chromadb-sentence-transformers"})
  r.raise_for_status(); project_id=r.json()["project_id"]
 def execute(tracer,name,version,broken,baseline=None):
  with tracer.start_run(name,version=version,baseline_run_id=baseline,metadata={"project":"rag-project-2","vector_store":"chroma"}) as run:
   rp={"query":QUESTION,"vector_store":"chroma","version":version}
   with run.trace_step("retrieve_documents",event_type="retrieval",payload=rp):
    docs=rag.retrieve(QUESTION,broken)
    rp.update({"relevant_chunk_count":len(docs),"chunk_ids":[d["id"] for d in docs],"distances":[round(d["distance"],4) for d in docs]})
   gp={}
   with run.trace_step("generate_answer",event_type="generation",payload=gp):
    result=answer(docs); gp.update({"answer_supported":bool(docs),"output_summary":result[:160]})
   print(name+": "+result); return run.run_id
 with TraceLens(project_id,api_url=API,strict=True) as tracer:
  baseline=execute(tracer,"baseline-success","chroma-v1",False)
  current=execute(tracer,"retrieval-regression","chroma-v2-buggy-filter",True,baseline)
 with httpx.Client(base_url=API,timeout=10) as c:
  r=c.post("/api/runs/compare",json={"baseline_run_id":baseline,"current_run_id":current}); r.raise_for_status()
  print("TraceLens comparison:",r.text)
 print("Project:",project_id,"Baseline:",baseline,"Current:",current)
if __name__=="__main__": main()
